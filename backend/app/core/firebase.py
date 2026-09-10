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

from app.core.config import get_settings

# firebase-admin is imported lazily inside the functions below so that the
# fully-local desktop build (which never initializes Firebase) doesn't need the
# firebase-admin / google-cloud dependencies bundled at all.

_initialized = False
_fake_firestore = None


def _emulator_credentials():
    """A credential yielding google-auth AnonymousCredentials (emulator only)."""
    from firebase_admin import credentials

    class _EmulatorCredentials(credentials.Base):
        def get_credential(self):
            from google.auth.credentials import AnonymousCredentials
            return AnonymousCredentials()

    return _EmulatorCredentials()


def _ensure_initialized() -> None:
    global _initialized
    import firebase_admin
    from firebase_admin import credentials

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
        cred = _emulator_credentials()
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
    global _fake_firestore
    settings = get_settings()
    # Fully-local desktop mode: a disk-backed in-process store, no Firebase init.
    if settings.local_mode:
        if _fake_firestore is None:
            from app.core.fake_firestore import FakeFirestoreClient
            _fake_firestore = FakeFirestoreClient(settings.data_path / "data.json")
        return _fake_firestore
    _ensure_initialized()
    if settings.env == "dev" and settings.firestore_backend == "memory":
        if _fake_firestore is None:
            from app.core.fake_firestore import FakeFirestoreClient
            _fake_firestore = FakeFirestoreClient()
        return _fake_firestore
    from firebase_admin import firestore
    return firestore.client()


def get_bucket():
    _ensure_initialized()
    from firebase_admin import storage
    return storage.bucket()


def get_auth():
    """Return the firebase_admin.auth module after ensuring init."""
    _ensure_initialized()
    from firebase_admin import auth
    return auth
