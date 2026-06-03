"""Test fixtures: in-memory Mongo (mongomock-motor) + httpx client.

Modal and R2 are mocked at the service boundary so no cloud calls happen.
"""
from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from beanie import init_beanie
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

import app.db as db_module
from app.models import DOCUMENT_MODELS


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def initialized_db(monkeypatch):
    """Initialize Beanie against an in-memory Mongo for each test."""
    client = AsyncMongoMockClient()
    await init_beanie(
        database=client["test_db"], document_models=DOCUMENT_MODELS
    )
    # Point app.db at the mock so /readyz and lifespan reuse it.
    monkeypatch.setattr(db_module, "_client", client)

    async def _noop_init(_=None):
        return client

    monkeypatch.setattr(db_module, "init_db", _noop_init)
    yield client


@pytest_asyncio.fixture
async def client(initialized_db):
    from app.main import create_app

    app = create_app()
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# --- helpers --------------------------------------------------------------
async def register(client: AsyncClient, email: str, username: str, roles=None) -> dict:
    payload = {
        "email": email,
        "username": username,
        "password": "supersecret123",
    }
    if roles:
        payload["roles"] = roles
    r = await client.post("/v1/auth/register", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def auth_header(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}
