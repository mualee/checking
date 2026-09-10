"""Startup seeding.

Two paths:
- Local desktop mode: seed a single admin the first time the app runs (when the
  users collection is empty), and write the credentials to FIRST_RUN.txt so the
  user can sign in. They should change the password in Settings afterwards.
- Legacy dev mode: seed three demo Firebase Auth users (emulator).
"""
from __future__ import annotations

import logging

from app.core import sentinels

from app.core.config import get_settings
from app.core.constants import COL_USERS, UserRole
from app.core.firebase import get_auth, get_firestore_client

logger = logging.getLogger("app.bootstrap")

DEMO_PASSWORD = "ILOVESSMI100%"
DEMO_USERS = [
    {"uid": "officer-1",
     "email": "officer@example.com",
     "role": UserRole.OFFICER,
     "name": "Officer One", "department": "Credit"},
    {"uid": "manager-1",
    "email": "manager@example.com",
    "role": UserRole.MANAGER,
     "name": "Manager One",
     "department": "Credit"},
    {"uid": "admin-1",
      "email": "admin@example.com",
      "role": UserRole.ADMIN,
     "name": "Admin One",
     "department": "IT"},
]

DEFAULT_ADMIN_EMAIL = "admin@local.app"
DEFAULT_ADMIN_PASSWORD = "admin1234"


def seed_local_admin() -> None:
    """Create a default admin the first time the local app runs (empty user set)."""
    db = get_firestore_client()
    if any(db.collection(COL_USERS).limit(1).stream()):
        return  # already provisioned

    from app.core.local_auth import hash_password

    ref = db.collection(COL_USERS).document()
    ref.set(
        {
            "name": "Administrator",
            "email": DEFAULT_ADMIN_EMAIL,
            "role": UserRole.ADMIN.value,
            "department": "IT",
            "isActive": True,
            "passwordHash": hash_password(DEFAULT_ADMIN_PASSWORD),
            "createdAt": sentinels.SERVER_TIMESTAMP,
        }
    )

    try:
        note = get_settings().data_path / "FIRST_RUN.txt"
        note.write_text(
            "Default administrator account created.\n"
            f"  Email:    {DEFAULT_ADMIN_EMAIL}\n"
            f"  Password: {DEFAULT_ADMIN_PASSWORD}\n\n"
            "Please sign in and change this password in Settings.\n",
            encoding="utf-8",
        )
    except OSError:
        pass
    logger.info("Seeded default admin: %s / %s", DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD)


def seed_demo_users() -> None:
    auth = get_auth()
    db = get_firestore_client()
    for u in DEMO_USERS:
        try:
            auth.create_user(uid=u["uid"], email=u["email"], password=DEMO_PASSWORD,
                             display_name=u["name"])
        except Exception:  # noqa: BLE001 - already exists (idempotent) or emulator quirk
            pass
        db.collection(COL_USERS).document(u["uid"]).set(
            {
                "name": u["name"],
                "email": u["email"],
                "role": u["role"].value,
                "department": u["department"],
                "isActive": True,
                "createdAt": sentinels.SERVER_TIMESTAMP,
            }
        )
    logger.info("Seeded %d demo users (password: %s)", len(DEMO_USERS), DEMO_PASSWORD)
