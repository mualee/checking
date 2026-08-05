"""User management: Firebase Auth users + Firestore users/{uid} profile docs."""
from __future__ import annotations

from firebase_admin import firestore

from app.core.constants import COL_USERS
from app.core.firebase import get_auth, get_firestore_client
from app.models.user import UserCreate, UserOut, UserUpdate


def _to_out(uid: str, data: dict) -> UserOut:
    return UserOut(
        uid=uid,
        name=data.get("name", ""),
        email=data.get("email", ""),
        role=data["role"],
        department=data.get("department", ""),
        is_active=bool(data.get("isActive", True)),
        created_at=data.get("createdAt"),
    )


def list_users() -> list[UserOut]:
    db = get_firestore_client()
    return [_to_out(doc.id, doc.to_dict() or {}) for doc in db.collection(COL_USERS).stream()]


def get_user(uid: str) -> UserOut | None:
    snap = get_firestore_client().collection(COL_USERS).document(uid).get()
    return _to_out(uid, snap.to_dict() or {}) if snap.exists else None


def create_user(payload: UserCreate) -> UserOut:
    auth = get_auth()
    db = get_firestore_client()
    record = auth.create_user(email=payload.email, password=payload.password,
                              display_name=payload.name)
    data = {
        "name": payload.name,
        "email": payload.email,
        "role": payload.role.value,
        "department": payload.department,
        "isActive": True,
        "createdAt": firestore.SERVER_TIMESTAMP,
    }
    db.collection(COL_USERS).document(record.uid).set(data)
    # Return with a concrete created_at rather than the sentinel.
    saved = db.collection(COL_USERS).document(record.uid).get().to_dict() or data
    return _to_out(record.uid, saved)


def update_user(uid: str, payload: UserUpdate) -> UserOut:
    db = get_firestore_client()
    ref = db.collection(COL_USERS).document(uid)
    snap = ref.get()
    if not snap.exists:
        raise KeyError(uid)
    updates: dict = {}
    if payload.role is not None:
        updates["role"] = payload.role.value
    if payload.is_active is not None:
        updates["isActive"] = payload.is_active
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.department is not None:
        updates["department"] = payload.department
    if updates:
        ref.update(updates)
        # Keep the Auth account's disabled flag in sync with isActive.
        if payload.is_active is not None:
            get_auth().update_user(uid, disabled=not payload.is_active)
    return _to_out(uid, ref.get().to_dict() or {})
