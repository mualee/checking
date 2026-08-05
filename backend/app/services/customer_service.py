"""Firestore CRUD for customers, with role-based list scoping."""
from __future__ import annotations

from firebase_admin import firestore

from app.core.constants import COL_CUSTOMERS, COL_STATEMENTS, CustomerStatus, UserRole
from app.core.firebase import get_firestore_client
from app.dependencies.auth import AuthUser
from app.models.customer import CustomerCreate, CustomerOut, CustomerUpdate


def _to_out(cid: str, data: dict) -> CustomerOut:
    return CustomerOut(
        id=cid,
        full_name=data.get("fullName", ""),
        national_id=data.get("nationalId", ""),
        phone=data.get("phone", ""),
        address=data.get("address", ""),
        account_no=data.get("accountNo", ""),
        status=data.get("status", CustomerStatus.ACTIVE.value),
        created_by=data.get("createdBy", ""),
        created_at=data.get("createdAt"),
        updated_at=data.get("updatedAt"),
    )


def list_customers(user: AuthUser) -> list[CustomerOut]:
    """Managers/admins see all customers. Officers see customers they created OR
    have uploaded a statement under (union, de-duplicated)."""
    db = get_firestore_client()
    col = db.collection(COL_CUSTOMERS)
    if user.role in (UserRole.MANAGER, UserRole.ADMIN):
        return [_to_out(d.id, d.to_dict() or {}) for d in col.stream()]

    result: dict[str, CustomerOut] = {}
    for d in col.where("createdBy", "==", user.uid).stream():
        result[d.id] = _to_out(d.id, d.to_dict() or {})
    # Customers where this officer uploaded a statement (collection-group query).
    stmt_group = db.collection_group(COL_STATEMENTS).where("uploadedBy", "==", user.uid)
    for s in stmt_group.stream():
        parent_customer = s.reference.parent.parent  # statements -> customer doc
        if parent_customer is None or parent_customer.id in result:
            continue
        csnap = parent_customer.get()
        if csnap.exists:
            result[parent_customer.id] = _to_out(csnap.id, csnap.to_dict() or {})
    return list(result.values())


def get_customer(cid: str) -> CustomerOut | None:
    snap = get_firestore_client().collection(COL_CUSTOMERS).document(cid).get()
    return _to_out(cid, snap.to_dict() or {}) if snap.exists else None


def create_customer(payload: CustomerCreate, created_by: str) -> CustomerOut:
    db = get_firestore_client()
    data = {
        "fullName": payload.full_name,
        "nationalId": payload.national_id,
        "phone": payload.phone,
        "address": payload.address,
        "accountNo": payload.account_no,
        "status": CustomerStatus.ACTIVE.value,
        "createdBy": created_by,  # forced to the acting user, ignoring any client value
        "createdAt": firestore.SERVER_TIMESTAMP,
        "updatedAt": firestore.SERVER_TIMESTAMP,
    }
    ref = db.collection(COL_CUSTOMERS).document()
    ref.set(data)
    return _to_out(ref.id, ref.get().to_dict() or data)


def update_customer(cid: str, payload: CustomerUpdate) -> CustomerOut:
    db = get_firestore_client()
    ref = db.collection(COL_CUSTOMERS).document(cid)
    field_map = {
        "full_name": "fullName", "national_id": "nationalId", "phone": "phone",
        "address": "address", "account_no": "accountNo",
    }
    updates: dict = {}
    for attr, fs_field in field_map.items():
        value = getattr(payload, attr)
        if value is not None:
            updates[fs_field] = value
    if payload.status is not None:
        updates["status"] = payload.status.value
    if updates:
        updates["updatedAt"] = firestore.SERVER_TIMESTAMP
        ref.update(updates)
    return _to_out(cid, ref.get().to_dict() or {})
