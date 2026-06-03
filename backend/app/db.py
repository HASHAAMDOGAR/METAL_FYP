"""MongoDB / Beanie initialization (spec §11)."""
from __future__ import annotations

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.models import DOCUMENT_MODELS

_client: AsyncIOMotorClient | None = None


async def init_db(client: AsyncIOMotorClient | None = None) -> AsyncIOMotorClient:
    """Connect to Mongo and register Beanie documents (creates indexes).

    A client may be injected (used by tests with mongomock).
    """
    global _client
    _client = client or AsyncIOMotorClient(settings.mongodb_uri)
    await init_beanie(
        database=_client[settings.mongodb_db],
        document_models=DOCUMENT_MODELS,
    )
    return _client


def get_client() -> AsyncIOMotorClient:
    if _client is None:
        raise RuntimeError("Database not initialized; call init_db() first.")
    return _client


async def ping() -> bool:
    """Used by /readyz."""
    client = get_client()
    await client.admin.command("ping")
    return True


async def close_db() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
