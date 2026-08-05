"""Ownership / access-control helpers, reused by all customer & statement routes.

Resolved rules (per product decisions):
- Officer sees a customer if they created it OR uploaded any statement under it
  (customer.createdBy == uid  OR  some statement.uploadedBy == uid).
- Officer sees a statement if they uploaded it OR they created the parent customer.
- Manager / admin see everything.
- Customer writes (POST/PUT): officer(own for PUT; any for POST, createdBy forced),
  manager (any), admin (any).
"""
from __future__ import annotations

from fastapi import HTTPException, status

from app.core.constants import COL_CUSTOMERS, COL_STATEMENTS, UserRole
from app.dependencies.auth import AuthUser


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="customer not found")


def _forbidden(detail: str = "not allowed") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _officer_uploaded_any_statement(db, customer_id: str, uid: str) -> bool:
    q = (
        db.collection(COL_CUSTOMERS)
        .document(customer_id)
        .collection(COL_STATEMENTS)
        .where("uploadedBy", "==", uid)
        .limit(1)
    )
    return any(True for _ in q.stream())


def assert_can_access_customer(db, user: AuthUser, customer_id: str):
    """Fetch the customer; 404 if missing, 403 if the officer may not see it.

    Returns the DocumentSnapshot so callers avoid a second read.
    """
    snap = db.collection(COL_CUSTOMERS).document(customer_id).get()
    if not snap.exists:
        raise _not_found()
    if user.role in (UserRole.MANAGER, UserRole.ADMIN):
        return snap
    data = snap.to_dict() or {}
    if data.get("createdBy") == user.uid:
        return snap
    if _officer_uploaded_any_statement(db, customer_id, user.uid):
        return snap
    raise _forbidden("officer may not access this customer")


def assert_can_write_customer(db, user: AuthUser, customer_id: str | None):
    """POST (customer_id is None): any authenticated role may create.
    PUT (customer_id given): officer must own the customer; manager/admin may edit any.
    Returns the existing snapshot for PUT, or None for POST.
    """
    if customer_id is None:
        return None
    snap = db.collection(COL_CUSTOMERS).document(customer_id).get()
    if not snap.exists:
        raise _not_found()
    if user.role in (UserRole.MANAGER, UserRole.ADMIN):
        return snap
    data = snap.to_dict() or {}
    if data.get("createdBy") == user.uid:
        return snap
    raise _forbidden("officer may only edit customers they created")


def assert_can_access_statement(db, user: AuthUser, customer_id: str, statement_snap_dict: dict,
                                customer_snap):
    """Officer statement access = uploaded it OR created the parent customer.

    `customer_snap` is the already-fetched parent customer snapshot (from
    assert_can_access_customer). Managers/admins are unrestricted.
    """
    if user.role in (UserRole.MANAGER, UserRole.ADMIN):
        return
    if statement_snap_dict.get("uploadedBy") == user.uid:
        return
    customer_data = customer_snap.to_dict() or {}
    if customer_data.get("createdBy") == user.uid:
        return
    raise _forbidden("officer may not access this statement")
