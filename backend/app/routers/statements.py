"""Statement endpoints: upload+process, detail, transactions, report, approve."""
from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from starlette.concurrency import run_in_threadpool

from app.core.constants import (
    COL_APPROVALS,
    AuditAction,
    AuditTargetType,
    ProcessingStatus,
    UserRole,
)
from app.core.firebase import get_firestore_client
from app.dependencies.access import assert_can_access_customer, assert_can_access_statement
from app.dependencies.auth import AuthUser, get_current_user, require_role
from app.models.approval import ApprovalCreate, ApprovalOut
from app.models.statement import StatementOut
from app.services import statement_service
from app.services.audit_service import write_audit_log
from app.services.pipeline import run_statement_pipeline
from app.services.storage_service import (
    download_bytes,
    download_json,
    signed_url,
    upload_bytes,
)
from app.core.config import get_settings
from firebase_admin import firestore

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

router = APIRouter(prefix="/customers/{customer_id}/statements", tags=["statements"])

CurrentUser = Annotated[AuthUser, Depends(get_current_user)]


def _load_statement_or_404(customer_id: str, statement_id: str):
    snap = statement_service.get_statement_raw(customer_id, statement_id)
    if not snap.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="statement not found")
    return snap


@router.get("", response_model=list[StatementOut])
async def list_statements(customer_id: str, user: CurrentUser) -> list[StatementOut]:
    db = get_firestore_client()
    customer_snap = assert_can_access_customer(db, user, customer_id)
    statements = statement_service.list_statements(customer_id)
    if user.role == UserRole.OFFICER:
        # Officer sees only statements they uploaded or under a customer they created.
        created = (customer_snap.to_dict() or {}).get("createdBy") == user.uid
        if not created:
            statements = [s for s in statements if s.uploaded_by == user.uid]
    return statements


@router.post("", response_model=StatementOut, status_code=status.HTTP_201_CREATED)
async def upload_statement(
    customer_id: str,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    opening_balance: Annotated[str | None, Form()] = None,
) -> StatementOut:
    db = get_firestore_client()
    customer_snap = assert_can_access_customer(db, user, customer_id)
    customer_data = customer_snap.to_dict() or {}

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty file")

    # Steps 1-2: persist original.pdf + create doc (processingStatus 'processing').
    statement_id = statement_service.create_statement_doc(
        customer_id, file_name=file.filename or "statement.pdf",
        storage_path=f"statements/{customer_id}/__pending__/original.pdf",
        uploaded_by=user.uid,
    )
    storage_path = f"statements/{customer_id}/{statement_id}/original.pdf"
    upload_bytes(storage_path, pdf_bytes, "application/pdf")
    statement_service.get_statement_raw(customer_id, statement_id)  # ensure exists
    db.collection("customers").document(customer_id).collection("statements") \
        .document(statement_id).update({"storagePath": storage_path})

    write_audit_log(user_id=user.uid, user_email=user.email, action=AuditAction.UPLOAD,
                    target_type=AuditTargetType.STATEMENT, target_id=statement_id,
                    details={"fileName": file.filename})

    ob = Decimal(opening_balance) if opening_balance else None

    # Step 3-9: run synchronously off the event loop (Cloud Run-safe; see plan §3).
    await run_in_threadpool(
        run_statement_pipeline,
        customer_id, statement_id, pdf_bytes, user.uid,
        customer_name=customer_data.get("fullName", ""),
        account_no=customer_data.get("accountNo", ""),
        opening_balance=ob,
        actor_email=user.email,
    )

    snap = _load_statement_or_404(customer_id, statement_id)
    return statement_service.doc_to_out(customer_id, statement_id, snap.to_dict() or {})


@router.get("/{statement_id}", response_model=StatementOut)
async def get_statement(customer_id: str, statement_id: str, user: CurrentUser) -> StatementOut:
    db = get_firestore_client()
    customer_snap = assert_can_access_customer(db, user, customer_id)
    snap = _load_statement_or_404(customer_id, statement_id)
    data = snap.to_dict() or {}
    assert_can_access_statement(db, user, customer_id, data, customer_snap)
    return statement_service.doc_to_out(customer_id, statement_id, data)


@router.get("/{statement_id}/transactions")
async def get_transactions(customer_id: str, statement_id: str, user: CurrentUser) -> list[dict]:
    db = get_firestore_client()
    customer_snap = assert_can_access_customer(db, user, customer_id)
    snap = _load_statement_or_404(customer_id, statement_id)
    data = snap.to_dict() or {}
    assert_can_access_statement(db, user, customer_id, data, customer_snap)
    prefix = f"statements/{customer_id}/{statement_id}"
    try:
        return download_json(f"{prefix}/transactions.json")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="transactions not available (not processed?)") from exc


@router.get("/{statement_id}/report")
async def get_report(customer_id: str, statement_id: str, user: CurrentUser) -> dict:
    db = get_firestore_client()
    customer_snap = assert_can_access_customer(db, user, customer_id)
    snap = _load_statement_or_404(customer_id, statement_id)
    data = snap.to_dict() or {}
    assert_can_access_statement(db, user, customer_id, data, customer_snap)
    report_path = data.get("reportStoragePath")
    if not report_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report not available")

    # In prod, hand back a short-lived signed GCS URL. In dev, the client downloads
    # the bytes via the auth-protected /report/file endpoint (below).
    if get_settings().env == "prod":
        return {"url": signed_url(report_path), "mode": "signed"}
    return {"url": None, "mode": "stream"}


@router.get("/{statement_id}/report/file")
async def download_report_file(customer_id: str, statement_id: str, user: CurrentUser) -> Response:
    db = get_firestore_client()
    customer_snap = assert_can_access_customer(db, user, customer_id)
    snap = _load_statement_or_404(customer_id, statement_id)
    data = snap.to_dict() or {}
    assert_can_access_statement(db, user, customer_id, data, customer_snap)
    report_path = data.get("reportStoragePath")
    if not report_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report not available")
    try:
        content = download_bytes(report_path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report file missing") from exc
    write_audit_log(user_id=user.uid, user_email=user.email, action=AuditAction.DOWNLOAD,
                    target_type=AuditTargetType.STATEMENT, target_id=statement_id,
                    details={"reportPath": report_path})
    filename = (data.get("fileName") or "report").rsplit(".", 1)[0] + ".docx"
    return Response(
        content=content,
        media_type=DOCX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{statement_id}/approvals", response_model=list[ApprovalOut])
async def list_approvals(customer_id: str, statement_id: str, user: CurrentUser) -> list[ApprovalOut]:
    db = get_firestore_client()
    customer_snap = assert_can_access_customer(db, user, customer_id)
    snap = _load_statement_or_404(customer_id, statement_id)
    assert_can_access_statement(db, user, customer_id, snap.to_dict() or {}, customer_snap)
    approvals_ref = (
        db.collection("customers").document(customer_id)
        .collection("statements").document(statement_id)
        .collection(COL_APPROVALS).order_by("decidedAt", direction=firestore.Query.DESCENDING)
    )
    out: list[ApprovalOut] = []
    for doc in approvals_ref.stream():
        d = doc.to_dict() or {}
        out.append(ApprovalOut(
            id=doc.id,
            decided_by=d.get("decidedBy", ""),
            decided_at=d.get("decidedAt"),
            decision=d.get("decision", "approved"),
            approved_amount=d.get("approvedAmount", 0.0),
            reason=d.get("reason", ""),
        ))
    return out


@router.post("/{statement_id}/approve", response_model=ApprovalOut,
             status_code=status.HTTP_201_CREATED)
async def approve_statement(
    customer_id: str,
    statement_id: str,
    payload: ApprovalCreate,
    manager: Annotated[AuthUser, Depends(require_role(UserRole.MANAGER, UserRole.ADMIN))],
) -> ApprovalOut:
    db = get_firestore_client()
    assert_can_access_customer(db, manager, customer_id)
    _load_statement_or_404(customer_id, statement_id)

    approvals_ref = (
        db.collection("customers").document(customer_id)
        .collection("statements").document(statement_id)
        .collection(COL_APPROVALS)
    )
    ref = approvals_ref.document()
    ref.set(
        {
            "decidedBy": manager.uid,
            "decidedAt": firestore.SERVER_TIMESTAMP,
            "decision": payload.decision.value,
            "approvedAmount": payload.approved_amount,
            "reason": payload.reason,
        }
    )
    action = AuditAction.APPROVE if payload.decision.value != "rejected" else AuditAction.REJECT
    write_audit_log(user_id=manager.uid, user_email=manager.email, action=action,
                    target_type=AuditTargetType.STATEMENT, target_id=statement_id,
                    details={"decision": payload.decision.value,
                             "approvedAmount": payload.approved_amount})
    saved = ref.get().to_dict() or {}
    return ApprovalOut(
        id=ref.id,
        decided_by=manager.uid,
        decided_at=saved.get("decidedAt"),
        decision=payload.decision,
        approved_amount=payload.approved_amount,
        reason=payload.reason,
    )
