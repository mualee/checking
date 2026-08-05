"""Dev-only startup seeding of demo users.

Creates three Firebase Auth users (in the Auth emulator) and their users/{uid}
profile docs (in whatever Firestore backend is configured) so the app is usable
immediately: sign in as officer@example.com / manager@example.com / admin@example.com,
all with password ILOVESSMI100%.
"""
from __future__ import annotations

import logging

from firebase_admin import firestore

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
                "createdAt": firestore.SERVER_TIMESTAMP,
            }
        )
    logger.info("Seeded %d demo users (password: %s)", len(DEMO_USERS), DEMO_PASSWORD)
