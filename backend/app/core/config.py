"""Application settings, loaded from environment / .env file."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["dev", "prod"] = "dev"
    gcp_project_id: str = "demo-credit-audit"
    storage_bucket: str = "demo-credit-audit.appspot.com"

    # Firestore backend for dev: "emulator" (Java service) or "memory" (in-process shim).
    # Use "memory" on hosts where the Java Firestore emulator can't start.
    firestore_backend: Literal["emulator", "memory"] = "emulator"
    # Object storage for dev: "emulator" (Firebase Storage emulator) or "local" (dev dir).
    storage_backend: Literal["emulator", "local"] = "emulator"
    # On startup in dev, seed demo Auth users + user profile docs.
    seed_demo_users: bool = False

    # Emulator hosts — only consulted when env == "dev".
    firestore_emulator_host: str = "localhost:8080"
    firebase_auth_emulator_host: str = "localhost:9099"
    firebase_storage_emulator_host: str = "localhost:9199"

    # Prod only: path to a service-account JSON (falls back to ADC if unset).
    google_application_credentials: str | None = None

    # CORS origins for the frontend (comma-separated in env).
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Signed-URL lifetime for report downloads.
    report_url_ttl_seconds: int = 15 * 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
