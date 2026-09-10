"""Local Firestore-compatible sentinels.

In the fully-local desktop build we don't ship firebase-admin, so we can't use
`firestore.SERVER_TIMESTAMP` / `firestore.Query.DESCENDING`. These stand-ins are
recognised by the in-process FakeFirestoreClient (compared by identity) and used
everywhere the code previously referenced the Firestore ones.
"""
from __future__ import annotations


class _Sentinel:
    __slots__ = ("_name",)

    def __init__(self, name: str) -> None:
        self._name = name

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{self._name}>"


# Resolved to a real UTC datetime on write by the fake store.
SERVER_TIMESTAMP = _Sentinel("SERVER_TIMESTAMP")
# order_by direction flag.
DESCENDING = _Sentinel("DESCENDING")
