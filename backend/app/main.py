"""FastAPI application entrypoint (spec §11)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import close_db, init_db, ping as db_ping
from app.errors import register_exception_handlers
from app.middleware import register_middleware
from app.routers import (
    admin,
    auth,
    catalog,
    downloads,
    inference,
    licenses,
    publisher,
    storage_local,
    telemetry,
    users,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.main")

# Named API groups → router. Used both for the full app and for deploying each
# API group as its own service (e.g. on Modal).
ROUTERS = {
    "auth": auth.router,
    "users": users.router,
    "catalog": catalog.router,
    "publisher": publisher.router,
    "admin": admin.router,
    "licenses": licenses.router,
    "downloads": downloads.router,
    "inference": inference.router,
    "telemetry": telemetry.router,
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    # DB init is tolerant: a deployed service should still boot (and serve
    # /healthz, /docs) even if the database is temporarily unreachable.
    try:
        await init_db()
    except Exception as exc:  # noqa: BLE001
        logger.warning("DB init failed at startup (continuing degraded): %s", exc)
    yield
    await close_db()


def create_app(include: list[str] | None = None) -> FastAPI:
    """Build the app. ``include`` selects a subset of API groups by name
    (defaults to all) — used to deploy each API as its own service."""
    selected = list(ROUTERS) if include is None else include
    title = "Apple Metal-Powered LLM Marketplace — Backend"
    if include is not None:
        title += f" [{', '.join(selected)}]"

    app = FastAPI(title=title, version="1.0.0", lifespan=lifespan)

    register_middleware(app)
    register_exception_handlers(app)

    # CORS — allow the browser frontend (any origin) to call the API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for name in selected:
        app.include_router(ROUTERS[name], prefix="/v1")

    # Local filesystem storage endpoints — only when not using R2, and only if
    # this service includes the publisher/downloads groups that need it.
    needs_storage = include is None or bool({"publisher", "downloads"} & set(selected))
    if settings.storage_backend.lower() != "r2" and needs_storage:
        app.include_router(storage_local.router, prefix="/v1")

    @app.get("/healthz", tags=["ops"])
    async def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/readyz", tags=["ops"])
    async def readyz() -> dict:
        checks: dict[str, bool] = {"mongo": False}
        try:
            checks["mongo"] = await db_ping()
        except Exception:
            checks["mongo"] = False

        # Storage check is labelled by the active backend (r2 or local).
        storage_label = "r2" if settings.storage_backend.lower() == "r2" else "storage_local"
        try:
            from app.services import storage

            checks[storage_label] = storage.ping()
        except Exception:
            checks[storage_label] = False

        # Modal is an optional fallback; report but don't gate readiness on it.
        modal_ok = False
        try:
            import modal  # noqa: F401

            modal_ok = bool(settings.modal_app_name)
        except Exception:
            modal_ok = False

        ready = checks["mongo"] and checks.get(storage_label, False)
        return {"ready": ready, "checks": {**checks, "modal": modal_ok}}

    return app


app = create_app()
