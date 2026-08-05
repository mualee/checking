"""Seed one Auth user + users/{uid} Firestore doc per role into the emulators.

Run with emulators up:
    firebase emulators:start --only auth,firestore,storage
    .venv/Scripts/python.exe scripts/seed_emulator_users.py

Prints the credentials it created (idempotent-ish: deletes+recreates known uids).
"""
from __future__ import annotations

import sys

sys.path.insert(0, "backend")

from firebase_admin import firestore  # noqa: E402

from app.core.constants import COL_USERS, UserRole  # noqa: E402
from app.core.firebase import get_auth, get_firestore_client  # noqa: E402

SEED = [
    {"uid": "officer-1", "email": "officer@example.com", "role": UserRole.OFFICER,
     "name": "Officer One", "department": "Credit"},
    {"uid": "manager-1", "email": "manager@example.com", "role": UserRole.MANAGER,
     "name": "Manager One", "department": "Credit"},
    {"uid": "admin-1", "email": "admin@example.com", "role": UserRole.ADMIN,
     "name": "Admin One", "department": "IT"},
]
PASSWORD = "Passw0rd!"


def main() -> None:
    auth = get_auth()
    db = get_firestore_client()
    for u in SEED:
        try:
            auth.delete_user(u["uid"])
        except Exception:  # noqa: BLE001 - fine if it doesn't exist yet
            pass
        auth.create_user(uid=u["uid"], email=u["email"], password=PASSWORD,
                         display_name=u["name"])
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
        print(f"seeded {u['role'].value:8} uid={u['uid']} email={u['email']} password={PASSWORD}")


if __name__ == "__main__":
    main()
