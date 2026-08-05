"""Shared test fixtures.

Integration tests require the Firebase Emulator Suite. When it is not reachable they
are skipped (not failed) with a clear message. Unit tests have no such requirement.
"""
from __future__ import annotations

import os
import socket
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

FIRESTORE_HOST = os.environ.get("FIRESTORE_EMULATOR_HOST", "localhost:8080")
AUTH_HOST = os.environ.get("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")


def _port_open(hostport: str) -> bool:
    host, port = hostport.split(":")
    try:
        with socket.create_connection((host, int(port)), timeout=0.5):
            return True
    except OSError:
        return False


def emulators_available() -> bool:
    return _port_open(FIRESTORE_HOST) and _port_open(AUTH_HOST)


requires_emulators = pytest.mark.skipif(
    not emulators_available(),
    reason="Firebase Emulator Suite not reachable (start it with "
           "`firebase emulators:start --only auth,firestore,storage`)",
)


@pytest.fixture(scope="session")
def app_client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture(scope="session")
def seeded_users():
    """Create officer/manager/admin users in the emulator and return their id tokens."""
    import requests
    from firebase_admin import firestore
    from app.core.constants import COL_USERS, UserRole
    from app.core.firebase import get_auth, get_firestore_client

    auth = get_auth()
    db = get_firestore_client()
    users = {}
    for role in (UserRole.OFFICER, UserRole.MANAGER, UserRole.ADMIN):
        uid = f"test-{role.value}-{uuid.uuid4().hex[:6]}"
        email = f"{uid}@example.com"
        auth.create_user(uid=uid, email=email, password="Passw0rd!")
        db.collection(COL_USERS).document(uid).set(
            {"name": role.value, "email": email, "role": role.value,
             "department": "T", "isActive": True, "createdAt": firestore.SERVER_TIMESTAMP}
        )
        custom = auth.create_custom_token(uid).decode("utf-8")
        url = (f"http://{AUTH_HOST}/identitytoolkit.googleapis.com/v1/"
               f"accounts:signInWithCustomToken?key=fake")
        resp = requests.post(url, json={"token": custom, "returnSecureToken": True}, timeout=10)
        resp.raise_for_status()
        users[role.value] = {"uid": uid, "email": email, "token": resp.json()["idToken"]}
    return users


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
