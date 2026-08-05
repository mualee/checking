"""Object storage wrappers with a pluggable backend.

Backends (dev): "emulator" (Firebase Storage emulator via google-cloud-storage) or
"local" (files under a dev directory). The local backend avoids the Storage emulator,
which the google-cloud-storage client talks to unreliably on some hosts. In prod the
emulator branch is used with real GCS + signed URLs.
"""
from __future__ import annotations

import json
import os
from datetime import timedelta
from pathlib import Path

from app.core.config import get_settings


def _use_local() -> bool:
    s = get_settings()
    return s.env == "dev" and s.storage_backend == "local"


def _local_base() -> Path:
    base = Path(__file__).resolve().parents[2] / ".devstorage"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _local_path(path: str) -> Path:
    p = _local_base() / path
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def upload_bytes(path: str, data: bytes, content_type: str) -> str:
    if _use_local():
        _local_path(path).write_bytes(data)
        return path
    from app.core.firebase import get_bucket
    blob = get_bucket().blob(path)
    blob.upload_from_string(data, content_type=content_type)
    return path


def upload_json(path: str, obj) -> str:
    payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    return upload_bytes(path, payload, "application/json")


def download_bytes(path: str) -> bytes:
    if _use_local():
        return _local_path(path).read_bytes()
    from app.core.firebase import get_bucket
    return get_bucket().blob(path).download_as_bytes()


def download_json(path: str):
    return json.loads(download_bytes(path).decode("utf-8"))


def exists(path: str) -> bool:
    if _use_local():
        return _local_path(path).exists()
    from app.core.firebase import get_bucket
    return get_bucket().blob(path).exists()


def signed_url(path: str, ttl_seconds: int | None = None) -> str:
    """Short-lived download URL (prod, real GCS)."""
    ttl = ttl_seconds if ttl_seconds is not None else get_settings().report_url_ttl_seconds
    from app.core.firebase import get_bucket
    return get_bucket().blob(path).generate_signed_url(
        expiration=timedelta(seconds=ttl), method="GET"
    )
