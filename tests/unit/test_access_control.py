"""Access-control logic tests with a lightweight fake Firestore — no emulator required."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.constants import UserRole
from app.dependencies.access import (
    assert_can_access_customer,
    assert_can_access_statement,
    assert_can_write_customer,
)
from app.dependencies.auth import AuthUser


# --------------------------------------------------------------------------- #
# Minimal fake Firestore supporting only what access.py uses.
# --------------------------------------------------------------------------- #
class FakeSnap:
    def __init__(self, data: dict | None):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return self._data


class FakeQuery:
    def __init__(self, docs: list[dict], field=None, value=None):
        self._docs = docs
        self._field = field
        self._value = value

    def where(self, field, op, value):
        return FakeQuery(self._docs, field, value)

    def limit(self, n):
        return self

    def stream(self):
        for d in self._docs:
            if self._field is None or d.get(self._field) == self._value:
                yield FakeSnap(d)


class FakeStatements:
    def __init__(self, statements: list[dict]):
        self._statements = statements

    def where(self, field, op, value):
        return FakeQuery(self._statements, field, value)


class FakeCustomerDoc:
    def __init__(self, data: dict | None, statements: list[dict]):
        self._data = data
        self._statements = statements

    def get(self):
        return FakeSnap(self._data)

    def collection(self, name):
        return FakeStatements(self._statements)


class FakeCustomersCollection:
    def __init__(self, customers: dict[str, dict], statements: dict[str, list[dict]]):
        self._customers = customers
        self._statements = statements

    def document(self, cid):
        return FakeCustomerDoc(self._customers.get(cid), self._statements.get(cid, []))


class FakeDB:
    def __init__(self, customers, statements=None):
        self._col = FakeCustomersCollection(customers, statements or {})

    def collection(self, name):
        return self._col


OFFICER = AuthUser(uid="off1", email="o@x.com", role=UserRole.OFFICER, is_active=True)
OFFICER2 = AuthUser(uid="off2", email="o2@x.com", role=UserRole.OFFICER, is_active=True)
MANAGER = AuthUser(uid="mgr1", email="m@x.com", role=UserRole.MANAGER, is_active=True)
ADMIN = AuthUser(uid="adm1", email="a@x.com", role=UserRole.ADMIN, is_active=True)


# --------------------------------------------------------------------------- #
# assert_can_access_customer
# --------------------------------------------------------------------------- #
def test_officer_accesses_own_customer():
    db = FakeDB({"c1": {"createdBy": "off1"}})
    assert assert_can_access_customer(db, OFFICER, "c1").exists


def test_officer_denied_other_customer():
    db = FakeDB({"c1": {"createdBy": "off2"}})
    with pytest.raises(HTTPException) as e:
        assert_can_access_customer(db, OFFICER, "c1")
    assert e.value.status_code == 403


def test_officer_accesses_customer_via_uploaded_statement():
    # Customer created by someone else, but officer uploaded a statement under it.
    db = FakeDB(
        {"c1": {"createdBy": "mgr1"}},
        {"c1": [{"uploadedBy": "off1"}]},
    )
    assert assert_can_access_customer(db, OFFICER, "c1").exists


def test_manager_accesses_any_customer():
    db = FakeDB({"c1": {"createdBy": "off1"}})
    assert assert_can_access_customer(db, MANAGER, "c1").exists


def test_missing_customer_404():
    db = FakeDB({})
    with pytest.raises(HTTPException) as e:
        assert_can_access_customer(db, ADMIN, "nope")
    assert e.value.status_code == 404


# --------------------------------------------------------------------------- #
# assert_can_write_customer (manager CAN write per product decision)
# --------------------------------------------------------------------------- #
def test_post_customer_allowed_for_any_role():
    db = FakeDB({})
    assert assert_can_write_customer(db, OFFICER, None) is None
    assert assert_can_write_customer(db, MANAGER, None) is None


def test_put_customer_officer_owner_allowed():
    db = FakeDB({"c1": {"createdBy": "off1"}})
    assert assert_can_write_customer(db, OFFICER, "c1").exists


def test_put_customer_officer_non_owner_denied():
    db = FakeDB({"c1": {"createdBy": "off2"}})
    with pytest.raises(HTTPException) as e:
        assert_can_write_customer(db, OFFICER, "c1")
    assert e.value.status_code == 403


def test_put_customer_manager_allowed_any():
    db = FakeDB({"c1": {"createdBy": "off2"}})
    assert assert_can_write_customer(db, MANAGER, "c1").exists


# --------------------------------------------------------------------------- #
# assert_can_access_statement
# --------------------------------------------------------------------------- #
def test_officer_accesses_own_uploaded_statement():
    db = FakeDB({"c1": {"createdBy": "mgr1"}})
    cust_snap = FakeSnap({"createdBy": "mgr1"})
    assert_can_access_statement(db, OFFICER, "c1", {"uploadedBy": "off1"}, cust_snap)  # no raise


def test_officer_accesses_statement_via_created_customer():
    cust_snap = FakeSnap({"createdBy": "off1"})
    assert_can_access_statement(None, OFFICER, "c1", {"uploadedBy": "off2"}, cust_snap)  # no raise


def test_officer_denied_foreign_statement():
    cust_snap = FakeSnap({"createdBy": "mgr1"})
    with pytest.raises(HTTPException) as e:
        assert_can_access_statement(None, OFFICER2, "c1", {"uploadedBy": "off1"}, cust_snap)
    assert e.value.status_code == 403


def test_manager_accesses_any_statement():
    cust_snap = FakeSnap({"createdBy": "off1"})
    assert_can_access_statement(None, MANAGER, "c1", {"uploadedBy": "off1"}, cust_snap)  # no raise
