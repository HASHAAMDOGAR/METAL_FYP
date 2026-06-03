"""Live end-to-end smoke test against a running server (real Mongo + local storage).

Run the server first (uvicorn on PUBLIC_BASE_URL), seed an admin, then:

    python -m scripts.smoke_test

Exercises the full backend: auth → publish → upload → approve → catalog →
acquire → device bind → verify → download (byte-exact) → review → telemetry →
cloud-inference fallback (expects graceful 503 when Modal unconfigured).
"""
from __future__ import annotations

import hashlib
import os
import sys

import httpx

BASE = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:8010")
ADMIN_EMAIL = "admin@metal.dev"
ADMIN_PASS = "admin12345"

_passed = 0
_failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    mark = "PASS" if cond else "FAIL"
    if cond:
        _passed += 1
    else:
        _failed += 1
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail and not cond else ""))


def main() -> int:
    suffix = os.urandom(3).hex()
    c = httpx.Client(base_url=BASE, timeout=30.0)

    print("\n== Auth ==")
    # Admin login (seeded).
    r = c.post("/v1/auth/login", data={"username": ADMIN_EMAIL, "password": ADMIN_PASS})
    check("admin login", r.status_code == 200, r.text)
    admin_h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # Publisher register + become publisher.
    pub_email = f"pub_{suffix}@example.com"
    r = c.post("/v1/auth/register", json={
        "email": pub_email, "username": f"pub{suffix}", "password": "supersecret123",
        "roles": ["app_developer", "model_developer"],
    })
    check("publisher register", r.status_code == 201, r.text)
    pub_h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    print("\n== Publish ==")
    r = c.post("/v1/publisher/models", headers=pub_h, json={
        "name": f"Smoke Llama {suffix}", "description": "smoke test model",
        "architecture": "llama", "quantization": "Q4_K_M", "file_format": "gguf",
        "param_count_b": 8.0, "tags": ["chat", "smoke"],
        "cloud_inference": {"enabled": True, "served_model_ref": "llama-3-8b-instruct"},
    })
    check("create model draft", r.status_code == 201, r.text)
    model = r.json()
    model_id = model["id"]

    # Get upload URL and PUT bytes (local storage simulating presigned PUT).
    payload = b"GGUF\x00fake-model-weights-" + os.urandom(64)
    sha = hashlib.sha256(payload).hexdigest()
    r = c.post(f"/v1/publisher/models/{model_id}/artifact", headers=pub_h)
    check("request upload url", r.status_code == 200, r.text)
    up_url = r.json()["upload_url"]
    r2 = httpx.put(up_url, content=payload, timeout=30.0)
    check("upload bytes to storage", r2.status_code == 200, r2.text)

    r = c.post(f"/v1/publisher/models/{model_id}/artifact/finalize", headers=pub_h,
               json={"size_bytes": len(payload), "sha256": sha, "version": "1.0.0"})
    check("finalize artifact", r.status_code == 200, r.text)

    r = c.post(f"/v1/publisher/models/{model_id}/submit", headers=pub_h)
    check("submit for review", r.status_code == 200 and r.json()["status"] == "pending_review", r.text)

    print("\n== Admin approval ==")
    r = c.post(f"/v1/admin/models/{model_id}/approve", headers=admin_h)
    check("admin approve", r.status_code == 200 and r.json()["status"] == "approved", r.text)
    slug = r.json()["slug"]

    print("\n== Catalog ==")
    r = c.get("/v1/models")
    check("catalog lists models", r.status_code == 200 and r.json()["total"] >= 1, r.text)
    r = c.get(f"/v1/models/{slug}")
    check("model detail by slug", r.status_code == 200 and r.json()["slug"] == slug, r.text)

    print("\n== Consumer: acquire → bind → verify → download ==")
    cons_email = f"dev_{suffix}@example.com"
    r = c.post("/v1/auth/register", json={
        "email": cons_email, "username": f"dev{suffix}", "password": "supersecret123"})
    check("consumer register", r.status_code == 201, r.text)
    cons_h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = c.post(f"/v1/models/{model_id}/acquire", headers=cons_h)
    check("acquire free license", r.status_code == 201, r.text)
    key = r.json()["license_key"]
    r2 = c.post(f"/v1/models/{model_id}/acquire", headers=cons_h)
    check("acquire is idempotent", r2.json()["license_key"] == key, r2.text)

    r = c.post(f"/v1/licenses/{key}/devices", headers=cons_h,
               json={"device_id": "hw-smoke-1", "device_name": "M2 Air", "platform": "macOS 14"})
    check("bind device", r.status_code == 201 and r.json()["bound_device_count"] == 1, r.text)

    r = c.post(f"/v1/licenses/{key}/verify", headers=cons_h, json={"device_id": "hw-smoke-1"})
    ok = r.status_code == 200 and r.json()["valid"] and r.json()["model_artifact_ref"]["sha256"] == sha
    check("verify license (MCP path)", ok, r.text)

    r = c.get(f"/v1/models/{model_id}/download?device_id=hw-smoke-1", headers=cons_h)
    check("download returns url", r.status_code == 200, r.text)
    dl_url, dl_sha = r.json()["download_url"], r.json()["sha256"]
    got = httpx.get(dl_url, timeout=30.0)
    byte_ok = got.status_code == 200 and hashlib.sha256(got.content).hexdigest() == sha == dl_sha
    check("downloaded bytes match sha256", byte_ok, f"{got.status_code}")

    print("\n== Reviews & telemetry ==")
    r = c.post(f"/v1/models/{slug}/reviews", headers=cons_h,
               json={"rating": 5, "title": "fast", "body": "great on M2"})
    check("post review", r.status_code == 201, r.text)
    r = c.get(f"/v1/models/{slug}")
    check("rating aggregated", r.json()["metrics"]["rating_count"] == 1, r.text)

    r = c.post("/v1/telemetry/events", headers=cons_h, json={"events": [
        {"model_id": model_id, "device_id": "hw-smoke-1", "event_type": "deploy", "path": "local_metal"},
        {"model_id": model_id, "device_id": "hw-smoke-1", "event_type": "inference",
         "path": "local_metal", "tokens_generated": 256, "tokens_per_sec": 31.2, "latency_ms": 8200},
    ]})
    check("ingest telemetry batch", r.status_code == 201 and r.json()["ingested"] == 2, r.text)
    r = c.get("/v1/me/usage", headers=cons_h)
    check("usage summary", r.status_code == 200 and r.json()["total_events"] >= 2, r.text)

    print("\n== Cloud inference fallback (Modal unconfigured → graceful 503) ==")
    r = c.post("/v1/inference", headers=cons_h, json={
        "model_id": model_id, "prompt": "hello", "device_id": "hw-smoke-1",
        "reason": "no_metal_device"})
    ok = r.status_code == 503 and r.json()["error"]["code"] in (
        "modal_unavailable", "inference_failed", "cloud_unconfigured", "cloud_disabled")
    check("inference returns graceful 503 (no Modal creds)", ok, f"{r.status_code} {r.text}")

    print("\n== Publisher report ==")
    r = c.get(f"/v1/publisher/models/{model_id}/report", headers=pub_h)
    rep_ok = r.status_code == 200 and r.json()["downloads"] >= 1 and r.json()["inferences"] >= 1
    check("publisher usage report", rep_ok, r.text)

    print(f"\n==== RESULT: {_passed} passed, {_failed} failed ====")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
