"""A minimal in-memory Firestore substitute for local dev.

WHY: the Firestore emulator is a Java service that will not start on some hosts
(a JVM loopback-selector failure). The Auth and Storage emulators are Node-based and
run fine. This shim implements exactly the subset of the google-cloud-firestore client
API the backend uses, so the whole stack can run locally without the Java emulator.

Scope (implemented): collection/document(get/set/update/delete), auto-id document(),
subcollections, collection.add(), stream(), where(==,>=,<=,>,<), order_by(direction),
limit(), collection_group(), and snapshot.reference.parent.parent navigation. Server
timestamps are resolved to real UTC datetimes on write.

NOT a full Firestore: single process, no persistence, no transactions/indexes. Dev only.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from firebase_admin import firestore

_SENTINEL = firestore.SERVER_TIMESTAMP
_DESCENDING = firestore.Query.DESCENDING


def _resolve_sentinels(value):
    if value is _SENTINEL:
        return datetime.now(timezone.utc)
    if isinstance(value, dict):
        return {k: _resolve_sentinels(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_sentinels(v) for v in value]
    return value


def _coerce_pair(a, b):
    """Make two values comparable (datetime vs ISO string)."""
    if isinstance(a, datetime) and isinstance(b, str):
        return a.isoformat(), b
    if isinstance(a, str) and isinstance(b, datetime):
        return a, b.isoformat()
    return a, b


class FakeSnapshot:
    def __init__(self, ref: "FakeDocRef", data: dict | None):
        self.reference = ref
        self.id = ref.id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class FakeDocRef:
    def __init__(self, store: "FakeStore", path: tuple[str, ...]):
        self._store = store
        self._path = path

    @property
    def id(self) -> str:
        return self._path[-1]

    @property
    def parent(self) -> "FakeCollectionRef":
        return FakeCollectionRef(self._store, self._path[:-1])

    def get(self) -> FakeSnapshot:
        return FakeSnapshot(self, self._store.get(self._path))

    def set(self, data: dict) -> None:
        self._store.set(self._path, _resolve_sentinels(data))

    def update(self, data: dict) -> None:
        self._store.update(self._path, _resolve_sentinels(data))

    def delete(self) -> None:
        self._store.delete(self._path)

    def collection(self, name: str) -> "FakeCollectionRef":
        return FakeCollectionRef(self._store, self._path + (name,))


class FakeQuery:
    def __init__(self, store, path, *, group=False, filters=None, order=None, limit_n=None):
        self._store = store
        self._path = path
        self._group = group
        self._filters = filters or []
        self._order = order
        self._limit = limit_n

    def _clone(self, **kw):
        base = dict(filters=self._filters, order=self._order, limit_n=self._limit, group=self._group)
        base.update(kw)
        return FakeQuery(self._store, self._path, **base)

    def where(self, field, op, value):
        return self._clone(filters=self._filters + [(field, op, value)])

    def order_by(self, field, direction=None):
        return self._clone(order=(field, direction))

    def limit(self, n):
        return self._clone(limit_n=n)

    def _matches(self, data: dict) -> bool:
        for field, op, value in self._filters:
            actual = data.get(field)
            a, b = _coerce_pair(actual, value)
            try:
                if op == "==" and not (a == b):
                    return False
                if op == ">=" and not (a is not None and a >= b):
                    return False
                if op == "<=" and not (a is not None and a <= b):
                    return False
                if op == ">" and not (a is not None and a > b):
                    return False
                if op == "<" and not (a is not None and a < b):
                    return False
            except TypeError:
                return False
        return True

    def stream(self):
        rows = self._store.iter_collection(self._path, group=self._group)
        results = [(p, d) for p, d in rows if self._matches(d)]
        if self._order:
            field, direction = self._order
            reverse = direction == _DESCENDING
            results.sort(key=lambda pd: _SortKey(pd[1].get(field)), reverse=reverse)
        if self._limit is not None:
            results = results[: self._limit]
        for p, d in results:
            yield FakeSnapshot(FakeDocRef(self._store, p), d)


class _SortKey:
    """Order-by key tolerant of None and mixed types (None sorts last on ascending)."""

    def __init__(self, v):
        self.v = v

    def __lt__(self, other):
        a, b = self.v, other.v
        if a is None:
            return False
        if b is None:
            return True
        a, b = _coerce_pair(a, b)
        try:
            return a < b
        except TypeError:
            return str(a) < str(b)


class FakeCollectionRef(FakeQuery):
    def __init__(self, store, path):
        super().__init__(store, path, group=False)

    @property
    def parent(self) -> FakeDocRef | None:
        return FakeDocRef(self._store, self._path[:-1]) if len(self._path) >= 2 else None

    def document(self, doc_id: str | None = None) -> FakeDocRef:
        return FakeDocRef(self._store, self._path + (doc_id or uuid.uuid4().hex,))

    def add(self, data: dict):
        ref = self.document()
        ref.set(data)
        return (datetime.now(timezone.utc), ref)


class FakeStore:
    """Holds all documents keyed by their full path tuple."""

    def __init__(self):
        self._docs: dict[tuple[str, ...], dict] = {}
        self._lock = threading.RLock()

    def get(self, path):
        with self._lock:
            d = self._docs.get(path)
            return dict(d) if d is not None else None

    def set(self, path, data):
        with self._lock:
            self._docs[path] = dict(data)

    def update(self, path, data):
        with self._lock:
            existing = self._docs.get(path)
            if existing is None:
                existing = {}
            existing.update(data)
            self._docs[path] = existing

    def delete(self, path):
        with self._lock:
            self._docs.pop(path, None)

    def iter_collection(self, path, *, group=False):
        """Yield (path, data) for docs directly under a collection, or (group mode)
        any doc whose immediate parent collection name equals path[-1]."""
        with self._lock:
            items = list(self._docs.items())
        if group:
            name = path[-1]
            for p, d in items:
                if len(p) >= 2 and p[-2] == name:
                    yield p, dict(d)
        else:
            depth = len(path) + 1  # collection path + doc id
            for p, d in items:
                if len(p) == depth and p[: len(path)] == path:
                    yield p, dict(d)


class FakeFirestoreClient:
    def __init__(self):
        self._store = FakeStore()

    def collection(self, name: str) -> FakeCollectionRef:
        return FakeCollectionRef(self._store, (name,))

    def collection_group(self, name: str) -> FakeQuery:
        return FakeQuery(self._store, (name,), group=True)
