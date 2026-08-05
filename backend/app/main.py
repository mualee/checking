"""FastAPI application factory."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.routers import audit_logs, customers, health, statements, users

logger = logging.getLogger("app")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Credit Statement Audit API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(users.router)
    app.include_router(customers.router)
    app.include_router(statements.router)
    app.include_router(audit_logs.router)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:  # noqa: ANN001
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "internal server error"})

    @app.on_event("startup")
    async def _startup() -> None:
        if settings.env == "dev" and settings.seed_demo_users:
            try:
                from app.core.bootstrap import seed_demo_users
                seed_demo_users()
            except Exception:  # noqa: BLE001 - don't block startup if seeding fails
                logger.exception("demo user seeding failed")

    return app


app = create_app()
