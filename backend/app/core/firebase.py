"""Single Firebase Admin SDK initialization point.

In dev mode we point the Admin SDK at the local Emulator Suite by exporting the
*_EMULATOR_HOST env vars BEFORE initialize_app(), and we hand the App an anonymous
credential so no real service-account / ADC lookup ever happens. In that mode the
emulators do not validate credentials.

All access to Firestore / Storage in the app goes through get_firestore_client()
and get_bucket(), which initialize lazily on first use (never at import time) so
tests can override Settings first.
"""
from __future__ import annotations

import os

import firebase_admin
from firebase_admin import credentials, firestore, storage

from app.core.config import get_settings

_initialized = False
_fake_firestore = None


class _EmulatorCredentials(credentials.Base):
    """A credential that yields google-auth AnonymousCredentials.

    Used only against the Emulator Suite, which ignores credentials. This keeps
    firestore.client() / storage.bucket() from ever attempting real ADC resolution.
    """

    def get_credential(self):
        from google.auth.credentials import AnonymousCredentials
        return AnonymousCredentials()


def _ensure_initialized() -> None:
    global _initialized
    if _initialized or firebase_admin._apps:
        _initialized = True
        return

    settings = get_settings()

    if settings.env == "dev":
        # Must be set before initialize_app so the underlying google-cloud clients
        # pick them up. Firestore/Auth honor these directly; google-cloud-storage
        # honors STORAGE_EMULATOR_HOST (with scheme).
        os.environ.setdefault("FIRESTORE_EMULATOR_HOST", settings.firestore_emulator_host)
        os.environ.setdefault("FIREBASE_AUTH_EMULATOR_HOST", settings.firebase_auth_emulator_host)
        os.environ.setdefault("FIREBASE_STORAGE_EMULATOR_HOST", settings.firebase_storage_emulator_host)
        os.environ.setdefault(
            "STORAGE_EMULATOR_HOST", f"http://{settings.firebase_storage_emulator_host}"
        )
        cred = _EmulatorCredentials()
    elif settings.google_application_credentials:
        cred = credentials.Certificate(settings.google_application_credentials)
    else:
        cred = credentials.ApplicationDefault()

    firebase_admin.initialize_app(
        cred,
        {
            "projectId": settings.gcp_project_id,
            "storageBucket": settings.storage_bucket,
        },
    )
    _initialized = True


def get_firestore_client():
    _ensure_initialized()
    settings = get_settings()
    if settings.env == "dev" and settings.firestore_backend == "memory":
        global _fake_firestore
        if _fake_firestore is None:
            from app.core.fake_firestore import FakeFirestoreClient
            _fake_firestore = FakeFirestoreClient()
        return _fake_firestore
    return firestore.client()


def get_bucket():
    _ensure_initialized()
    return storage.bucket()


def get_auth():
    """Return the firebase_admin.auth module after ensuring init."""
    _ensure_initialized()
    from firebase_admin import auth
    return auth
