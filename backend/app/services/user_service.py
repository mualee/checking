"""User management: Firebase Auth users + Firestore users/{uid} profile docs."""
from __future__ import annotations

from app.core import sentinels
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.constants import COL_USERS, resolve_role
from app.core.firebase import get_auth, get_firestore_client
from app.models.user import UserCreate, UserOut, UserUpdate


def _to_out(uid: str, data: dict) -> UserOut:
    return UserOut(
        uid=uid,
        name=data.get("name", ""),
        email=data.get("email", ""),
        role=resolve_role(data["role"]),
        department=data.get("department", ""),
        is_active=bool(data.get("isActive", True)),
        created_at=data.get("createdAt"),
    )


def list_users() -> list[UserOut]:
    """Skip docs with no role mapping into this app's model (see resolve_role).

    users/{uid} is a directory shared with other internal apps, so it holds
    profiles this app has no equivalent for. Those shouldn't fail the whole
    listing.
    """
    db = get_firestore_client()
    out = []
    for doc in db.collection(COL_USERS).stream():
        try:
            out.append(_to_out(doc.id, doc.to_dict() or {}))
        except (ValidationError, KeyError):
            continue
    return out


def get_user(uid: str) -> UserOut | None:
    snap = get_firestore_client().collection(COL_USERS).document(uid).get()
    return _to_out(uid, snap.to_dict() or {}) if snap.exists else None


def create_user(payload: UserCreate) -> UserOut:
    db = get_firestore_client()
    data = {
        "name": payload.name,
        "email": payload.email,
        "role": payload.role.value,
        "department": payload.department,
        "isActive": True,
        "createdAt": sentinels.SERVER_TIMESTAMP,
    }
    if get_settings().local_mode:
        # No Firebase Auth: store a bcrypt hash and use a locally-generated uid.
        from app.core.local_auth import hash_password
        if any(db.collection(COL_USERS).where("email", "==", payload.email).stream()):
            raise ValueError("email already exists")
        data["passwordHash"] = hash_password(payload.password)
        ref = db.collection(COL_USERS).document()
        uid = ref.id
    else:
        record = get_auth().create_user(email=payload.email, password=payload.password,
                                        display_name=payload.name)
        uid = record.uid
        ref = db.collection(COL_USERS).document(uid)
    ref.set(data)
    # Return with a concrete created_at rather than the sentinel.
    saved = db.collection(COL_USERS).document(uid).get().to_dict() or data
    return _to_out(uid, saved)


def find_by_email(email: str) -> tuple[str, dict] | None:
    """Return (uid, raw_doc) for the user with this email, or None. Local mode."""
    db = get_firestore_client()
    for doc in db.collection(COL_USERS).where("email", "==", email).stream():
        return doc.id, (doc.to_dict() or {})
    return None


def set_password(uid: str, new_password: str) -> None:
    """Store a new bcrypt password hash for a user. Local mode."""
    from app.core.local_auth import hash_password
    db = get_firestore_client()
    ref = db.collection(COL_USERS).document(uid)
    if not ref.get().exists:
        raise KeyError(uid)
    ref.update({"passwordHash": hash_password(new_password)})


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
        # Keep the Auth account's disabled flag in sync with isActive (Firebase only;
        # local mode has no separate Auth account — isActive is enforced at request time).
        if payload.is_active is not None and not get_settings().local_mode:
            get_auth().update_user(uid, disabled=not payload.is_active)
    return _to_out(uid, ref.get().to_dict() or {})
