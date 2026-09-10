"""Entry point for the bundled local backend (PyInstaller target).

Electron spawns the built backend.exe with LOCAL_MODE=1 and APP_DATA_DIR set to
the per-user data directory. This runs the FastAPI app with uvicorn on 127.0.0.1.
Using the app object directly (not an import string) keeps it reload-free and
friendly to PyInstaller's frozen environment.
"""
from __future__ import annotations

import os

import uvicorn

# Sensible defaults for the desktop build; Electron overrides via env.
os.environ.setdefault("LOCAL_MODE", "1")

from app.main import app  # noqa: E402  (import after env defaults are set)


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
