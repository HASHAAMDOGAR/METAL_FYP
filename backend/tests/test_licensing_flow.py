"""End-to-end slice: publish → approve → acquire → bind → verify → download.

Maps to spec §9.1 / §9.3. Modal + R2 are mocked at the service boundary.
"""
from __future__ import annotations

import pytest

from app.models.enums import Role
from app.models.user import User
from tests.conftest import auth_header, register


async def _make_admin(email: str, username: str):
    user = await User.find_one(User.email == email)
    user.roles.append(Role.admin)
    await user.save()


@pytest.fixture
def patch_storage(monkeypatch):
    from app.services import storage

    monkeypatch.setattr(storage, "presigned_put", lambda key, ttl=None: f"https://r2.test/{key}?put")
    monkeypatch.setattr(storage, "presigned_get", lambda key, ttl=None: f"https://r2.test/{key}?get")


@pytest.mark.asyncio
async def test_full_license_flow(client, patch_storage):
    # Publisher creates + uploads + submits a model.
    pub = await register(client, "pub@example.com", "publisher", roles=["app_developer", "model_developer"])
    ph = auth_header(pub)

    create = await client.post(
        "/v1/publisher/models",
        json={
            "name": "Llama 3 8B Instruct",
            "description": "fast",
            "architecture": "llama",
            "quantization": "Q4_K_M",
            "file_format": "gguf",
            "param_count_b": 8.0,
            "tags": ["chat", "instruct"],
            "cloud_inference": {"enabled": True, "served_model_ref": "llama-3-8b-instruct"},
        },
        headers=ph,
    )
    assert create.status_code == 201, create.text
    model_id = create.json()["id"]

    up = await client.post(f"/v1/publisher/models/{model_id}/artifact", headers=ph)
    assert up.status_code == 200
    assert "put" in up.json()["upload_url"]

    fin = await client.post(
        f"/v1/publisher/models/{model_id}/artifact/finalize",
        json={"size_bytes": 4733280256, "sha256": "abc123", "version": "1.0.0"},
        headers=ph,
    )
    assert fin.status_code == 200

    sub = await client.post(f"/v1/publisher/models/{model_id}/submit", headers=ph)
    assert sub.status_code == 200
    assert sub.json()["status"] == "pending_review"

    # Admin approves.
    await _make_admin("pub@example.com", "publisher")
    # Re-login to get a token carrying the admin role is unnecessary; guard reads DB user.
    appr = await client.post(f"/v1/admin/models/{model_id}/approve", headers=ph)
    assert appr.status_code == 200, appr.text
    slug = appr.json()["slug"]

    # Consumer browses catalog.
    cons = await register(client, "dev@example.com", "devuser")
    ch = auth_header(cons)
    listing = await client.get("/v1/models")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    detail = await client.get(f"/v1/models/{slug}")
    assert detail.status_code == 200

    # Acquire (free) — idempotent.
    acq = await client.post(f"/v1/models/{model_id}/acquire", headers=ch)
    assert acq.status_code == 201
    key = acq.json()["license_key"]
    acq2 = await client.post(f"/v1/models/{model_id}/acquire", headers=ch)
    assert acq2.json()["license_key"] == key  # idempotent

    # Bind device.
    bind = await client.post(
        f"/v1/licenses/{key}/devices",
        json={"device_id": "hw-uuid-1", "device_name": "M2 Air", "platform": "macOS 14"},
        headers=ch,
    )
    assert bind.status_code == 201
    assert bind.json()["bound_device_count"] == 1

    # Verify (MCP Server).
    ver = await client.post(
        f"/v1/licenses/{key}/verify",
        json={"device_id": "hw-uuid-1"},
        headers=ch,
    )
    assert ver.status_code == 200
    assert ver.json()["valid"] is True
    assert ver.json()["model_artifact_ref"]["sha256"] == "abc123"

    # Download.
    dl = await client.get(f"/v1/models/{model_id}/download?device_id=hw-uuid-1", headers=ch)
    assert dl.status_code == 200
    assert "get" in dl.json()["download_url"]
    assert dl.json()["sha256"] == "abc123"


@pytest.mark.asyncio
async def test_device_cap_enforced(client, patch_storage):
    pub = await register(client, "p2@example.com", "pub2", roles=["model_developer"])
    ph = auth_header(pub)
    create = await client.post(
        "/v1/publisher/models",
        json={"name": "Mistral 7B", "architecture": "mistral", "file_format": "gguf"},
        headers=ph,
    )
    model_id = create.json()["id"]
    await client.post(f"/v1/publisher/models/{model_id}/artifact", headers=ph)
    await client.post(
        f"/v1/publisher/models/{model_id}/artifact/finalize",
        json={"size_bytes": 1, "sha256": "x", "version": "1.0.0"},
        headers=ph,
    )
    await client.post(f"/v1/publisher/models/{model_id}/submit", headers=ph)
    await _make_admin("p2@example.com", "pub2")
    await client.post(f"/v1/admin/models/{model_id}/approve", headers=ph)

    cons = await register(client, "d2@example.com", "d2user")
    ch = auth_header(cons)
    key = (await client.post(f"/v1/models/{model_id}/acquire", headers=ch)).json()["license_key"]

    # Default cap is 3 — bind 3 then expect 409 on the 4th.
    for i in range(3):
        r = await client.post(
            f"/v1/licenses/{key}/devices",
            json={"device_id": f"hw-{i}"},
            headers=ch,
        )
        assert r.status_code == 201
    over = await client.post(
        f"/v1/licenses/{key}/devices", json={"device_id": "hw-4"}, headers=ch
    )
    assert over.status_code == 409
    assert over.json()["error"]["code"] == "license_device_limit"


@pytest.mark.asyncio
async def test_unsupported_format_rejected(client):
    pub = await register(client, "p3@example.com", "pub3", roles=["model_developer"])
    ph = auth_header(pub)
    r = await client.post(
        "/v1/publisher/models",
        json={"name": "Bad", "architecture": "llama", "file_format": "onnx"},
        headers=ph,
    )
    # onnx is not in the FileFormat enum → 422 validation error.
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_download_requires_license(client, patch_storage):
    pub = await register(client, "p4@example.com", "pub4", roles=["model_developer"])
    ph = auth_header(pub)
    create = await client.post(
        "/v1/publisher/models",
        json={"name": "Qwen 7B", "architecture": "qwen", "file_format": "gguf"},
        headers=ph,
    )
    model_id = create.json()["id"]
    await client.post(f"/v1/publisher/models/{model_id}/artifact", headers=ph)
    await client.post(
        f"/v1/publisher/models/{model_id}/artifact/finalize",
        json={"size_bytes": 1, "sha256": "x", "version": "1.0.0"},
        headers=ph,
    )
    await client.post(f"/v1/publisher/models/{model_id}/submit", headers=ph)
    await _make_admin("p4@example.com", "pub4")
    await client.post(f"/v1/admin/models/{model_id}/approve", headers=ph)

    cons = await register(client, "d4@example.com", "d4user")
    ch = auth_header(cons)
    # No license acquired → forbidden.
    dl = await client.get(f"/v1/models/{model_id}/download", headers=ch)
    assert dl.status_code == 403
    assert dl.json()["error"]["code"] == "license_required"
