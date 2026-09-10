"""Statement endpoints: upload+process, detail, transactions, report, approve."""
from __future__ import annotations

import datetime as _dt
import re
import urllib.parse
from decimal import Decimal
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
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
from app.models.transaction import TransactionRow
from app.services.pipeline import process_transactions, run_statement_pipeline
from app.services.storage_service import (
    download_bytes,
    download_json,
    signed_url,
    upload_bytes,
    upload_json,
)
from app.core.config import get_settings
from app.core import sentinels

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
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    opening_balance: Annotated[str | None, Form()] = None,
    source: Annotated[str, Form()] = "auto",
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

    # Steps 3-9 run in the BACKGROUND so the upload returns immediately (the doc is
    # already 'processing'); the client polls the statement until it finishes.
    # A big statement (esp. OCR) can take minutes — no reason to block the request.
    background_tasks.add_task(
        run_statement_pipeline,
        customer_id, statement_id, pdf_bytes, user.uid,
        customer_name=customer_data.get("fullName", ""),
        account_no=customer_data.get("accountNo", ""),
        opening_balance=ob,
        actor_email=user.email,
        source=source if source in ("auto", "digital", "scan") else "auto",
    )

    snap = _load_statement_or_404(customer_id, statement_id)
    return statement_service.doc_to_out(customer_id, statement_id, snap.to_dict() or {})


@router.post("/{statement_id}/revalidate", response_model=StatementOut)
async def revalidate_statement(
    customer_id: str,
    statement_id: str,
    user: CurrentUser,
    payload: dict,
) -> StatementOut:
    """Re-run validation + report over human-corrected transactions (the OCR
    review flow). Body: {"transactions": [...], "opening_balance": "..."?}."""
    db = get_firestore_client()
    customer_snap = assert_can_access_customer(db, user, customer_id)
    snap = _load_statement_or_404(customer_id, statement_id)
    data = snap.to_dict() or {}
    assert_can_access_statement(db, user, customer_id, data, customer_snap)
    customer_data = customer_snap.to_dict() or {}

    rows = payload.get("transactions")
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="transactions required")
    try:
        transactions = [TransactionRow.from_json_dict(r) for r in rows]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"invalid transaction data: {exc}") from exc

    ob_raw = payload.get("opening_balance")
    ob = Decimal(str(ob_raw)) if ob_raw not in (None, "") else None

    # Persist the corrected rows, then re-run steps 4-9 off the event loop.
    upload_json(f"statements/{customer_id}/{statement_id}/transactions.json",
                [t.to_json_dict() for t in transactions])
    await run_in_threadpool(
        process_transactions,
        customer_id, statement_id, transactions, user.uid,
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

    # With real GCS, hand back a short-lived signed URL. Otherwise (local storage),
    # the client downloads the bytes via the auth-protected /report/file endpoint.
    settings = get_settings()
    if settings.env == "prod" and settings.storage_backend != "local":
        return {"url": signed_url(report_path), "mode": "signed"}
    return {"url": None, "mode": "stream"}


_REPORT_MEDIA = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get("/{statement_id}/report/file")
async def download_report_file(
    customer_id: str,
    statement_id: str,
    user: CurrentUser,
    format: str = "pdf",
) -> Response:
    """Download the report as PDF (default) or Word — `?format=pdf|docx`. Both are
    generated at processing time and share the storage prefix; if the requested one
    is missing (e.g. a statement processed before both formats existed) we fall back
    to whatever `reportStoragePath` points at."""
    db = get_firestore_client()
    customer_snap = assert_can_access_customer(db, user, customer_id)
    snap = _load_statement_or_404(customer_id, statement_id)
    data = snap.to_dict() or {}
    assert_can_access_statement(db, user, customer_id, data, customer_snap)
    stored = data.get("reportStoragePath")
    if not stored:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report not available")

    fmt = format.lower()
    if fmt not in _REPORT_MEDIA:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="format must be pdf or docx")
    # The sibling path in the requested format (same prefix, swapped extension).
    wanted = stored.rsplit(".", 1)[0] + "." + fmt
    for path in (wanted, stored):
        try:
            content = download_bytes(path)
            report_path = path
            break
        except Exception:  # noqa: BLE001, PERF203 — try the fallback next
            continue
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report file missing")

    write_audit_log(user_id=user.uid, user_email=user.email, action=AuditAction.DOWNLOAD,
                    target_type=AuditTargetType.STATEMENT, target_id=statement_id,
                    details={"reportPath": report_path})
    # Name the download <customer>_<date>.<ext>, by the file we actually serve.
    customer_data = customer_snap.to_dict() or {}
    ext = ".docx" if report_path.lower().endswith(".docx") else ".pdf"
    media_type = _REPORT_MEDIA["docx" if ext == ".docx" else "pdf"]
    filename = _report_filename(customer_data.get("fullName"),
                                data.get("reportGeneratedAt") or data.get("uploadedAt"))
    ascii_name = (re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("_") or "report") + ext
    disposition = (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{urllib.parse.quote(filename + ext)}"
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": disposition},
    )


def _report_filename(customer_name: str | None, dt_raw) -> str:
    """<customer name>_<DD-MM-YYYY> (no extension), sanitized for a filename."""
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', "", (customer_name or "report").strip()) or "report"
    try:
        date_str = _dt.datetime.fromisoformat(str(dt_raw).replace("Z", "+00:00")).strftime("%d-%m-%Y")
    except (ValueError, TypeError):
        date_str = _dt.date.today().strftime("%d-%m-%Y")
    return f"{name}_{date_str}"


@router.get("/{statement_id}/approvals", response_model=list[ApprovalOut])
async def list_approvals(customer_id: str, statement_id: str, user: CurrentUser) -> list[ApprovalOut]:
    db = get_firestore_client()
    customer_snap = assert_can_access_customer(db, user, customer_id)
    snap = _load_statement_or_404(customer_id, statement_id)
    assert_can_access_statement(db, user, customer_id, snap.to_dict() or {}, customer_snap)
    approvals_ref = (
        db.collection("customers").document(customer_id)
        .collection("statements").document(statement_id)
        .collection(COL_APPROVALS).order_by("decidedAt", direction=sentinels.DESCENDING)
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
            "decidedAt": sentinels.SERVER_TIMESTAMP,
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
