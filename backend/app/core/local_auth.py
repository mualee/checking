"""Local, offline authentication: bcrypt password hashing + a self-issued JWT.

Replaces Firebase Auth in the fully-local desktop build. The signing secret is
generated once and kept under the per-user data dir, so tokens stay valid across
restarts on the same machine but never leave it.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

_ALGO = "HS256"
_TOKEN_TTL = timedelta(days=7)


def _secret() -> str:
    """Read (or lazily create) the local JWT signing secret."""
    path = get_settings().data_path / "secret.key"
    if not path.exists():
        path.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def issue_token(uid: str, email: str | None) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": uid, "email": email, "iat": now, "exp": now + _TOKEN_TTL}
    return jwt.encode(payload, _secret(), algorithm=_ALGO)


def decode_token(token: str) -> dict:
    """Return the token claims, or raise jwt.PyJWTError on any failure."""
    return jwt.decode(token, _secret(), algorithms=[_ALGO])
