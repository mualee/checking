"""Unit tests for the in-memory Firestore shim — no emulator required."""
from __future__ import annotations

from firebase_admin import firestore

from app.core.fake_firestore import FakeFirestoreClient


def test_set_get_update_delete():
    db = FakeFirestoreClient()
    ref = db.collection("customers").document("c1")
    ref.set({"fullName": "A", "createdBy": "u1"})
    assert ref.get().exists
    assert ref.get().to_dict()["fullName"] == "A"
    ref.update({"phone": "123"})
    assert ref.get().to_dict()["phone"] == "123"
    assert ref.get().to_dict()["fullName"] == "A"  # merge, not replace
    ref.delete()
    assert not ref.get().exists


def test_auto_id_and_stream():
    db = FakeFirestoreClient()
    col = db.collection("customers")
    ids = {col.document().id for _ in range(3)}
    for i, cid in enumerate(ids):
        col.document(cid).set({"n": i})
    rows = list(col.stream())
    assert len(rows) == 3
    assert {r.id for r in rows} == ids


def test_where_filter():
    db = FakeFirestoreClient()
    col = db.collection("customers")
    col.document("a").set({"createdBy": "u1"})
    col.document("b").set({"createdBy": "u2"})
    col.document("c").set({"createdBy": "u1"})
    got = list(col.where("createdBy", "==", "u1").stream())
    assert {r.id for r in got} == {"a", "c"}


def test_subcollection_and_collection_group_parent_nav():
    db = FakeFirestoreClient()
    cust = db.collection("customers").document("c1")
    cust.set({"createdBy": "mgr"})
    cust.collection("statements").document("s1").set({"uploadedBy": "off1"})
    cust.collection("statements").document("s2").set({"uploadedBy": "off2"})

    # collection_group finds statements across customers, filtered by uploadedBy.
    hits = list(db.collection_group("statements").where("uploadedBy", "==", "off1").stream())
    assert len(hits) == 1
    parent_customer = hits[0].reference.parent.parent
    assert parent_customer.id == "c1"
    assert parent_customer.get().to_dict()["createdBy"] == "mgr"


def test_order_by_and_limit():
    db = FakeFirestoreClient()
    col = db.collection("auditLogs")
    for i in range(5):
        col.document(f"l{i}").set({"n": i})
    desc = list(col.order_by("n", direction=firestore.Query.DESCENDING).limit(2).stream())
    assert [r.to_dict()["n"] for r in desc] == [4, 3]


def test_server_timestamp_resolved():
    from datetime import datetime

    db = FakeFirestoreClient()
    ref = db.collection("x").document("y")
    ref.set({"createdAt": firestore.SERVER_TIMESTAMP,
             "nested": {"checkedAt": firestore.SERVER_TIMESTAMP}})
    data = ref.get().to_dict()
    assert isinstance(data["createdAt"], datetime)
    assert isinstance(data["nested"]["checkedAt"], datetime)


def test_add_returns_ref():
    db = FakeFirestoreClient()
    _, ref = db.collection("auditLogs").add({"action": "login"})
    assert ref.get().to_dict()["action"] == "login"
