"""End-to-end smoke test across the REAL process boundary (running uvicorn + emulators).

Prereqs (three terminals or background):
    1) firebase emulators:start --only auth,firestore,storage
    2) cd backend && ../.venv/Scripts/uvicorn app.main:app --port 8000
    3) .venv/Scripts/python.exe scripts/smoke_test_pipeline.py

Exercises: officer login -> create customer -> upload -> poll -> fetch
table1/table2/transactions/report -> manager approve -> read audit-logs.
Prints PASS/FAIL per step and exits non-zero on failure.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, "backend")

import httpx  # noqa: E402

API = os.environ.get("API_BASE", "http://localhost:8000")
AUTH_HOST = os.environ.get("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")
FIXTURE = os.path.join("tests", "fixtures", "sample_statement.pdf")

_failures = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global _failures
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {label}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        _failures += 1


def token_for(uid: str) -> str:
    from app.core.firebase import get_auth
    custom = get_auth().create_custom_token(uid).decode("utf-8")
    url = (f"http://{AUTH_HOST}/identitytoolkit.googleapis.com/v1/"
           f"accounts:signInWithCustomToken?key=fake")
    r = httpx.post(url, json={"token": custom, "returnSecureToken": True}, timeout=10)
    r.raise_for_status()
    return r.json()["idToken"]


def main() -> int:
    # Assumes scripts/seed_emulator_users.py has been run (officer-1, manager-1, admin-1).
    off = token_for("officer-1")
    mgr = token_for("manager-1")
    oh = {"Authorization": f"Bearer {off}"}
    mh = {"Authorization": f"Bearer {mgr}"}

    check("health", httpx.get(f"{API}/health", timeout=10).json().get("status") == "ok")

    r = httpx.post(f"{API}/customers", headers=oh, json={"full_name": "Smoke Cust",
                   "account_no": "001-9"}, timeout=30)
    check("create customer", r.status_code == 201, r.text)
    cid = r.json()["id"]

    with open(FIXTURE, "rb") as f:
        r = httpx.post(f"{API}/customers/{cid}/statements", headers=oh,
                       files={"file": ("sample.pdf", f.read(), "application/pdf")}, timeout=120)
    check("upload + process", r.status_code == 201, r.text)
    sid = r.json()["id"]
    check("status completed", r.json().get("processing_status") == "completed", r.text)

    # Poll (already synchronous, but demonstrates the polling contract).
    for _ in range(10):
        d = httpx.get(f"{API}/customers/{cid}/statements/{sid}", headers=oh, timeout=30).json()
        if d.get("processing_status") in ("completed", "validation_failed", "error"):
            break
        time.sleep(0.5)

    tx = httpx.get(f"{API}/customers/{cid}/statements/{sid}/transactions", headers=oh, timeout=30)
    check("transactions.json", tx.status_code == 200 and len(tx.json()) == 11, tx.text)

    rep = httpx.get(f"{API}/customers/{cid}/statements/{sid}/report", headers=oh, timeout=30)
    check("report url", rep.status_code == 200 and bool(rep.json().get("url")), rep.text)

    ap = httpx.post(f"{API}/customers/{cid}/statements/{sid}/approve", headers=mh,
                    json={"decision": "approved", "approved_amount": 5000000, "reason": "ok"},
                    timeout=30)
    check("manager approve", ap.status_code == 201, ap.text)

    logs = httpx.get(f"{API}/audit-logs", headers=mh, timeout=30)
    check("audit logs readable", logs.status_code == 200 and len(logs.json()) > 0, logs.text)

    print(f"\n{'ALL PASSED' if _failures == 0 else str(_failures) + ' STEP(S) FAILED'}")
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
