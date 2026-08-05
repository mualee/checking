"""Step-2 de-risk: prove the Admin SDK talks to the Emulator Suite.

Writes a Firestore doc, creates an Auth user, mints + verifies an ID token, and
does a Storage upload/download round-trip. Run with emulators already running:

    firebase emulators:start --only auth,firestore,storage
    .venv/Scripts/python.exe scripts/prove_emulator_wiring.py
"""
from __future__ import annotations

import sys
import uuid

sys.path.insert(0, "backend")

import requests  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.firebase import get_auth, get_firestore_client, get_bucket  # noqa: E402


def mint_id_token(uid: str, email: str) -> str:
    """Exchange a custom token for an ID token via the Auth emulator REST endpoint."""
    auth = get_auth()
    custom_token = auth.create_custom_token(uid).decode("utf-8")
    host = get_settings().firebase_auth_emulator_host
    url = (
        f"http://{host}/identitytoolkit.googleapis.com/v1/"
        f"accounts:signInWithCustomToken?key=fake-api-key"
    )
    resp = requests.post(url, json={"token": custom_token, "returnSecureToken": True}, timeout=10)
    resp.raise_for_status()
    return resp.json()["idToken"]


def main() -> None:
    db = get_firestore_client()
    auth = get_auth()

    # 1. Firestore write + read-back
    doc_id = f"probe-{uuid.uuid4().hex[:8]}"
    db.collection("_probe").document(doc_id).set({"hello": "emulator"})
    snap = db.collection("_probe").document(doc_id).get()
    assert snap.exists and snap.to_dict()["hello"] == "emulator", "Firestore round-trip failed"
    print("[ok] Firestore write/read")

    # 2. Auth: create user, mint + verify ID token
    uid = f"probe-user-{uuid.uuid4().hex[:8]}"
    email = f"{uid}@example.com"
    auth.create_user(uid=uid, email=email, password="Passw0rd!")
    id_token = mint_id_token(uid, email)
    decoded = auth.verify_id_token(id_token)
    assert decoded["uid"] == uid, "verify_id_token uid mismatch"
    print("[ok] Auth create_user + verify_id_token")

    # 3. Storage upload/download round-trip
    bucket = get_bucket()
    blob = bucket.blob(f"_probe/{doc_id}.txt")
    blob.upload_from_string(b"storage-emulator-ok", content_type="text/plain")
    downloaded = bucket.blob(f"_probe/{doc_id}.txt").download_as_bytes()
    assert downloaded == b"storage-emulator-ok", "Storage round-trip failed"
    print("[ok] Storage upload/download")

    # cleanup
    db.collection("_probe").document(doc_id).delete()
    auth.delete_user(uid)
    blob.delete()
    print("\nEMULATOR WIRING PROVEN ✔")


if __name__ == "__main__":
    main()
