"""Create one admin user in the REAL Firebase project (Auth user + users/{uid} doc).

Run against your configured project (reads backend/.env -> ENV=prod + service account):

    cd backend
    ../.venv/Scripts/python.exe ../scripts/seed_prod_admin.py <email> <password> [name]

Example:
    ../.venv/Scripts/python.exe ../scripts/seed_prod_admin.py admin@mybank.la "StrongPass!23" "Admin"

Idempotent: if the email already exists, it reuses that account and just ensures the
users/{uid} profile doc has role=admin, isActive=true.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")  # run from backend/ so `app` and .env resolve

from firebase_admin import firestore  # noqa: E402

from app.core.constants import COL_USERS, UserRole  # noqa: E402
from app.core.firebase import get_auth, get_firestore_client  # noqa: E402


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: seed_prod_admin.py <email> <password> [name]")
        return 2
    email = sys.argv[1]
    password = sys.argv[2]
    name = sys.argv[3] if len(sys.argv) > 3 else "Admin"

    auth = get_auth()
    db = get_firestore_client()

    try:
        user = auth.create_user(email=email, password=password, display_name=name)
        uid = user.uid
        print(f"created Auth user: {email} (uid={uid})")
    except Exception:
        # Already exists -> reuse.
        user = auth.get_user_by_email(email)
        uid = user.uid
        print(f"Auth user already exists: {email} (uid={uid}) — reusing")

    db.collection(COL_USERS).document(uid).set(
        {
            "name": name,
            "email": email,
            "role": UserRole.ADMIN.value,
            "department": "IT",
            "isActive": True,
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
    )
    print(f"wrote users/{uid} with role=admin, isActive=true")
    print("\nDONE — you can now log in with this email/password as an admin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
