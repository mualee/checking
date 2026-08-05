"""End-to-end pipeline integration tests (require emulators)."""
from __future__ import annotations

import os

import pytest

from tests.conftest import auth_headers, requires_emulators

pytestmark = [requires_emulators, pytest.mark.integration]

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _upload(client, token, cid, filename):
    with open(os.path.join(FIXTURES, filename), "rb") as f:
        return client.post(
            f"/customers/{cid}/statements",
            headers=auth_headers(token),
            files={"file": (filename, f.read(), "application/pdf")},
        )


def test_pipeline_success_path(app_client, seeded_users):
    off = seeded_users["officer"]
    cid = app_client.post("/customers", headers=auth_headers(off["token"]),
                          json={"full_name": "Pipeline Cust", "account_no": "001-2"}).json()["id"]

    r = _upload(app_client, off["token"], cid, "sample_statement.pdf")
    assert r.status_code == 201, r.text
    body = r.json()
    sid = body["id"]
    assert body["processing_status"] == "completed", body

    # Table 1 total row matches the fixture ground truth.
    total = body["table1Summary"][-1]
    assert total["debit"] == 15000000.0
    assert total["credit"] == 28000000.0
    assert total["endBalance"] == 14000000.0
    assert [row["month"] for row in body["table2Summary"]] == ["07/2024", "06/2024", "05/2024"]
    assert body["validation"]["matched"] is True

    # transactions.json round-trips.
    tx = app_client.get(f"/customers/{cid}/statements/{sid}/transactions",
                        headers=auth_headers(off["token"]))
    assert tx.status_code == 200
    assert len(tx.json()) == 11

    # report is available.
    rep = app_client.get(f"/customers/{cid}/statements/{sid}/report",
                         headers=auth_headers(off["token"]))
    assert rep.status_code == 200 and rep.json()["url"]


def test_pipeline_validation_failure_writes_no_report(app_client, seeded_users):
    off = seeded_users["officer"]
    cid = app_client.post("/customers", headers=auth_headers(off["token"]),
                          json={"full_name": "Bad Cust"}).json()["id"]

    r = _upload(app_client, off["token"], cid, "sample_statement_mismatch.pdf")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["processing_status"] == "validation_failed"
    assert body["validation"]["matched"] is False
    assert body["validation"]["mismatchCount"] == 1
    # No tables, no report on a failed statement.
    assert body["table1Summary"] == []
    assert body["report_storage_path"] == ""


def test_manager_can_approve_officer_cannot(app_client, seeded_users):
    off = seeded_users["officer"]
    mgr = seeded_users["manager"]
    cid = app_client.post("/customers", headers=auth_headers(off["token"]),
                          json={"full_name": "Approve Cust"}).json()["id"]
    sid = _upload(app_client, off["token"], cid, "sample_statement.pdf").json()["id"]

    # Officer forbidden.
    r_off = app_client.post(f"/customers/{cid}/statements/{sid}/approve",
                            headers=auth_headers(off["token"]),
                            json={"decision": "approved", "approved_amount": 5000000})
    assert r_off.status_code == 403

    # Manager allowed.
    r_mgr = app_client.post(f"/customers/{cid}/statements/{sid}/approve",
                            headers=auth_headers(mgr["token"]),
                            json={"decision": "approved", "approved_amount": 5000000,
                                  "reason": "ok"})
    assert r_mgr.status_code == 201
    assert r_mgr.json()["decision"] == "approved"
