"""Auth & user flow tests (spec §5.1)."""
from __future__ import annotations

import pytest

from tests.conftest import auth_header, register


@pytest.mark.asyncio
async def test_register_login_me(client):
    await register(client, "a@example.com", "alice")

    r = await client.post(
        "/v1/auth/login",
        data={"username": "alice", "password": "supersecret123"},
    )
    assert r.status_code == 200
    tokens = r.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    r = await client.get("/v1/users/me", headers=auth_header(tokens))
    assert r.status_code == 200
    assert r.json()["username"] == "alice"


@pytest.mark.asyncio
async def test_duplicate_register_conflicts(client):
    await register(client, "dup@example.com", "dup")
    r = await client.post(
        "/v1/auth/register",
        json={"email": "dup@example.com", "username": "dup", "password": "supersecret123"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "user_exists"


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    r = await client.get("/v1/users/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_become_publisher(client):
    tokens = await register(client, "p@example.com", "pub")
    r = await client.post(
        "/v1/users/me/become-publisher",
        json={"org_name": "Acme AI"},
        headers=auth_header(tokens),
    )
    assert r.status_code == 200
    assert "model_developer" in r.json()["roles"]
