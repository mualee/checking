"""Customer API integration tests (require emulators)."""
from __future__ import annotations

import pytest

from tests.conftest import auth_headers, requires_emulators

pytestmark = [requires_emulators, pytest.mark.integration]


def _create_customer(client, token, name):
    return client.post("/customers", headers=auth_headers(token), json={"full_name": name})


def test_no_auth_is_401(app_client):
    assert app_client.get("/customers").status_code == 401


def test_officer_only_sees_own_customers(app_client, seeded_users):
    off = seeded_users["officer"]
    mgr = seeded_users["manager"]
    r = _create_customer(app_client, off["token"], "Officer Cust")
    assert r.status_code == 201, r.text
    off_cid = r.json()["id"]

    # Manager creates another customer.
    r2 = _create_customer(app_client, mgr["token"], "Manager Cust")
    assert r2.status_code == 201
    mgr_cid = r2.json()["id"]

    # Officer list excludes the manager-created customer.
    ids = {c["id"] for c in app_client.get("/customers", headers=auth_headers(off["token"])).json()}
    assert off_cid in ids
    assert mgr_cid not in ids

    # Manager sees all.
    mgr_ids = {c["id"] for c in app_client.get("/customers", headers=auth_headers(mgr["token"])).json()}
    assert {off_cid, mgr_cid} <= mgr_ids


def test_officer_cannot_get_foreign_customer(app_client, seeded_users):
    mgr = seeded_users["manager"]
    off = seeded_users["officer"]
    cid = _create_customer(app_client, mgr["token"], "Private").json()["id"]
    r = app_client.get(f"/customers/{cid}", headers=auth_headers(off["token"]))
    assert r.status_code == 403


def test_manager_can_edit_any_customer(app_client, seeded_users):
    off = seeded_users["officer"]
    mgr = seeded_users["manager"]
    cid = _create_customer(app_client, off["token"], "Editable").json()["id"]
    r = app_client.put(f"/customers/{cid}", headers=auth_headers(mgr["token"]),
                       json={"phone": "020-555"})
    assert r.status_code == 200
    assert r.json()["phone"] == "020-555"
