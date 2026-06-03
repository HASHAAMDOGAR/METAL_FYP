"""Cloud inference fallback test with Modal mocked (spec §5.6, §7)."""
from __future__ import annotations

import pytest

from app.models.enums import Role
from app.models.usage_event import UsageEvent
from app.models.user import User
from tests.conftest import auth_header, register


async def _approved_model(client, ph, email, username, ref="llama-3-8b-instruct"):
    create = await client.post(
        "/v1/publisher/models",
        json={
            "name": "Cloud Model",
            "architecture": "llama",
            "file_format": "gguf",
            "cloud_inference": {"enabled": True, "served_model_ref": ref},
        },
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
    user = await User.find_one(User.email == email)
    user.roles.append(Role.admin)
    await user.save()
    await client.post(f"/v1/admin/models/{model_id}/approve", headers=ph)
    return model_id


@pytest.fixture
def patch_storage(monkeypatch):
    from app.services import storage

    monkeypatch.setattr(storage, "presigned_put", lambda key, ttl=None: "https://r2/put")
    monkeypatch.setattr(storage, "presigned_get", lambda key, ttl=None: "https://r2/get")


@pytest.fixture
def patch_modal(monkeypatch):
    async def fake_generate(model, prompt, max_tokens=512, temperature=0.7):
        return {
            "output": f"echo: {prompt}",
            "tokens_generated": 7,
            "tokens_per_sec": 42.0,
            "path": "cloud_modal",
        }

    from app.services import inference_service

    monkeypatch.setattr(inference_service, "cloud_generate", fake_generate)


@pytest.mark.asyncio
async def test_cloud_inference_fallback(client, patch_storage, patch_modal):
    pub = await register(client, "ci@example.com", "ciuser", roles=["model_developer"])
    ph = auth_header(pub)
    model_id = await _approved_model(client, ph, "ci@example.com", "ciuser")

    cons = await register(client, "u@example.com", "uuser")
    ch = auth_header(cons)
    await client.post(f"/v1/models/{model_id}/acquire", headers=ch)

    r = await client.post(
        "/v1/inference",
        json={
            "model_id": model_id,
            "prompt": "hello",
            "device_id": "hw-1",
            "reason": "no_metal_device",
        },
        headers=ch,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["path"] == "cloud_modal"
    assert body["output"] == "echo: hello"

    # A usage event with path=cloud_modal was logged.
    events = await UsageEvent.find(UsageEvent.event_type == "inference").to_list()
    assert len(events) == 1
    assert events[0].path == "cloud_modal"


@pytest.mark.asyncio
async def test_inference_requires_license(client, patch_storage, patch_modal):
    pub = await register(client, "ci2@example.com", "ci2user", roles=["model_developer"])
    ph = auth_header(pub)
    model_id = await _approved_model(client, ph, "ci2@example.com", "ci2user")

    cons = await register(client, "u2@example.com", "u2user")
    ch = auth_header(cons)
    # No acquire → 403.
    r = await client.post(
        "/v1/inference",
        json={"model_id": model_id, "prompt": "hi", "reason": "no_metal_device"},
        headers=ch,
    )
    assert r.status_code == 403
