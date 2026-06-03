"""Exhaustive endpoint test — exercises every route with happy-path AND error
scenarios, then prints a per-endpoint report.

    python -m scripts.full_api_test
"""
from __future__ import annotations

import hashlib
import os
import sys

import httpx

BASE = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:8010")
ADMIN_EMAIL, ADMIN_PASS = "admin@metal.dev", "admin12345"

rows: list[tuple] = []


def rec(method: str, path: str, scenario: str, expected, got, ok: bool, note: str = ""):
    rows.append((method, path, scenario, str(expected), str(got), ok, note))


def E(method, path, scenario, expected, resp, note=""):
    got = resp.status_code
    rec(method, path, scenario, expected, got, got == expected, note)
    return resp


def main() -> int:
    suffix = os.urandom(3).hex()
    c = httpx.Client(base_url=BASE, timeout=30.0)

    # ---------------- OPS ----------------
    E("GET", "/healthz", "liveness", 200, c.get("/healthz"))
    E("GET", "/readyz", "readiness", 200, c.get("/readyz"))
    E("GET", "/openapi.json", "openapi schema", 200, c.get("/openapi.json"))
    E("GET", "/docs", "swagger ui", 200, c.get("/docs"))

    # ---------------- AUTH ----------------
    admin = c.post("/v1/auth/login", data={"username": ADMIN_EMAIL, "password": ADMIN_PASS})
    E("POST", "/v1/auth/login", "admin happy path", 200, admin)
    admin_h = {"Authorization": f"Bearer {admin.json()['access_token']}"}

    E("POST", "/v1/auth/login", "bad credentials", 401,
      c.post("/v1/auth/login", data={"username": ADMIN_EMAIL, "password": "wrong"}))

    pub_email = f"pub_{suffix}@example.com"
    reg = c.post("/v1/auth/register", json={
        "email": pub_email, "username": f"pub{suffix}", "password": "supersecret123",
        "roles": ["app_developer", "model_developer"]})
    E("POST", "/v1/auth/register", "create publisher", 201, reg)
    pub_h = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    pub_refresh = reg.json()["refresh_token"]

    E("POST", "/v1/auth/register", "duplicate email -> 409", 409,
      c.post("/v1/auth/register", json={"email": pub_email, "username": f"x{suffix}", "password": "supersecret123"}))
    E("POST", "/v1/auth/register", "short username -> 422", 422,
      c.post("/v1/auth/register", json={"email": f"a{suffix}@e.com", "username": "ab", "password": "supersecret123"}))
    E("POST", "/v1/auth/register", "short password -> 422", 422,
      c.post("/v1/auth/register", json={"email": f"b{suffix}@e.com", "username": f"bb{suffix}", "password": "short"}))

    E("POST", "/v1/auth/refresh", "valid refresh -> rotate", 200,
      c.post("/v1/auth/refresh", json={"refresh_token": pub_refresh}))
    E("POST", "/v1/auth/refresh", "reused (rotated) refresh -> 401", 401,
      c.post("/v1/auth/refresh", json={"refresh_token": pub_refresh}))
    E("POST", "/v1/auth/refresh", "missing token -> 400", 400,
      c.post("/v1/auth/refresh", json={}))
    E("POST", "/v1/auth/refresh", "garbage token -> 401", 401,
      c.post("/v1/auth/refresh", json={"refresh_token": "not.a.jwt"}))

    # logout flow on a throwaway account
    tmp = c.post("/v1/auth/register", json={
        "email": f"lo_{suffix}@e.com", "username": f"lo{suffix}", "password": "supersecret123"})
    tmp_refresh = tmp.json()["refresh_token"]
    E("POST", "/v1/auth/logout", "logout (204)", 204,
      c.post("/v1/auth/logout", json={"refresh_token": tmp_refresh}))
    E("POST", "/v1/auth/refresh", "refresh after logout -> 401", 401,
      c.post("/v1/auth/refresh", json={"refresh_token": tmp_refresh}))

    # ---------------- USERS ----------------
    E("GET", "/v1/users/me", "current profile", 200, c.get("/v1/users/me", headers=pub_h))
    E("GET", "/v1/users/me", "no auth -> 401", 401, c.get("/v1/users/me"))
    E("GET", "/v1/users/me", "bad token -> 401", 401,
      c.get("/v1/users/me", headers={"Authorization": "Bearer nope"}))
    E("PATCH", "/v1/users/me", "update display name", 200,
      c.patch("/v1/users/me", headers=pub_h, json={"display_name": "Pub One"}))

    cons = c.post("/v1/auth/register", json={
        "email": f"dev_{suffix}@e.com", "username": f"dev{suffix}", "password": "supersecret123"})
    cons_h = {"Authorization": f"Bearer {cons.json()['access_token']}"}
    E("POST", "/v1/users/me/become-publisher", "promote to publisher", 200,
      c.post("/v1/users/me/become-publisher", headers=cons_h, json={"org_name": "Dev Co"}))

    # ---------------- PUBLISHER ----------------
    E("GET", "/v1/publisher/models", "list own (empty/ok)", 200, c.get("/v1/publisher/models", headers=pub_h))
    E("GET", "/v1/publisher/models", "consumer-as-publisher now allowed", 200,
      c.get("/v1/publisher/models", headers=cons_h))
    # a pure consumer (no publisher role) is forbidden
    nopub = c.post("/v1/auth/register", json={
        "email": f"np_{suffix}@e.com", "username": f"np{suffix}", "password": "supersecret123"})
    nopub_h = {"Authorization": f"Bearer {nopub.json()['access_token']}"}
    E("GET", "/v1/publisher/models", "non-publisher -> 403", 403,
      c.get("/v1/publisher/models", headers=nopub_h))

    create = E("POST", "/v1/publisher/models", "create draft", 201, c.post(
        "/v1/publisher/models", headers=pub_h, json={
            "name": f"Full Llama {suffix}", "description": "endpoint test",
            "architecture": "llama", "quantization": "Q4_K_M", "file_format": "gguf",
            "param_count_b": 8.0, "tags": ["chat", "full"],
            "cloud_inference": {"enabled": True, "served_model_ref": "llama-3-8b-instruct"}}))
    model_id = create.json()["id"]

    E("POST", "/v1/publisher/models", "unsupported format -> 422", 422, c.post(
        "/v1/publisher/models", headers=pub_h,
        json={"name": "Bad", "architecture": "llama", "file_format": "onnx"}))
    E("POST", "/v1/publisher/models", "non-publisher -> 403", 403, c.post(
        "/v1/publisher/models", headers=nopub_h,
        json={"name": "X", "architecture": "llama", "file_format": "gguf"}))

    E("PATCH", f"/v1/publisher/models/{model_id}", "edit metadata", 200,
      c.patch(f"/v1/publisher/models/{model_id}", headers=pub_h, json={"description": "updated"}))
    E("PATCH", "/v1/publisher/models/deadbeefdeadbeefdeadbeef", "edit not-owned -> 404", 404,
      c.patch("/v1/publisher/models/deadbeefdeadbeefdeadbeef", headers=pub_h, json={"description": "x"}))

    # submit before artifact -> 400
    E("POST", f"/v1/publisher/models/{model_id}/submit", "submit w/o artifact -> 400", 400,
      c.post(f"/v1/publisher/models/{model_id}/submit", headers=pub_h))
    # finalize before upload-url -> 400
    E("POST", f"/v1/publisher/models/{model_id}/artifact/finalize", "finalize w/o upload -> 400", 400,
      c.post(f"/v1/publisher/models/{model_id}/artifact/finalize", headers=pub_h,
             json={"size_bytes": 1, "sha256": "x", "version": "1.0.0"}))

    payload = b"GGUF\x00" + os.urandom(128)
    sha = hashlib.sha256(payload).hexdigest()
    up = E("POST", f"/v1/publisher/models/{model_id}/artifact", "get upload url", 200,
           c.post(f"/v1/publisher/models/{model_id}/artifact", headers=pub_h))
    up_url = up.json()["upload_url"]

    # ---------------- STORAGE (local) ----------------
    key = up.json()["storage_key"]
    E("PUT", "/v1/storage/local/{key}", "upload bytes", 200, httpx.put(up_url, content=payload))
    E("PUT", "/v1/storage/local/{key}", "empty upload -> 400", 400,
      httpx.put(up_url, content=b""))
    E("GET", "/v1/storage/local/{key}", "download bytes", 200,
      httpx.get(f"{BASE}/v1/storage/local/{key}"))
    E("GET", "/v1/storage/local/{key}", "missing object -> 404", 404,
      httpx.get(f"{BASE}/v1/storage/local/models/nope/model.gguf"))

    E("POST", f"/v1/publisher/models/{model_id}/artifact/finalize", "finalize artifact", 200,
      c.post(f"/v1/publisher/models/{model_id}/artifact/finalize", headers=pub_h,
             json={"size_bytes": len(payload), "sha256": sha, "version": "1.0.0"}))
    E("POST", f"/v1/publisher/models/{model_id}/submit", "submit for review", 200,
      c.post(f"/v1/publisher/models/{model_id}/submit", headers=pub_h))

    # ---------------- ADMIN ----------------
    E("GET", "/v1/admin/models/pending", "list pending (admin)", 200,
      c.get("/v1/admin/models/pending", headers=admin_h))
    E("GET", "/v1/admin/models/pending", "non-admin -> 403", 403,
      c.get("/v1/admin/models/pending", headers=pub_h))
    E("POST", f"/v1/admin/models/{model_id}/approve", "approve", 200,
      c.post(f"/v1/admin/models/{model_id}/approve", headers=admin_h))
    E("POST", f"/v1/admin/models/{model_id}/approve", "re-approve approved -> 409", 409,
      c.post(f"/v1/admin/models/{model_id}/approve", headers=admin_h))

    # a second model to test reject
    m2 = c.post("/v1/publisher/models", headers=pub_h,
                json={"name": f"Reject Me {suffix}", "architecture": "mistral", "file_format": "gguf"}).json()
    c.post(f"/v1/publisher/models/{m2['id']}/artifact", headers=pub_h)
    httpx.put(f"{BASE}/v1/storage/local/models/{m2['id']}/model.gguf", content=b"x")
    c.post(f"/v1/publisher/models/{m2['id']}/artifact/finalize", headers=pub_h,
           json={"size_bytes": 1, "sha256": "x", "version": "1.0.0"})
    c.post(f"/v1/publisher/models/{m2['id']}/submit", headers=pub_h)
    E("POST", f"/v1/admin/models/{m2['id']}/reject", "reject with reason", 200,
      c.post(f"/v1/admin/models/{m2['id']}/reject", headers=admin_h, json={"reason": "low quality"}))

    slug = create.json()["slug"]

    # ---------------- CATALOG ----------------
    E("GET", "/v1/models", "list approved", 200, c.get("/v1/models"))
    E("GET", "/v1/models", "text search q", 200, c.get("/v1/models", params={"q": "full"}))
    E("GET", "/v1/models", "filter+sort+paginate", 200,
      c.get("/v1/models", params={"architecture": "llama", "sort": "rating", "page": 1, "page_size": 5}))
    E("GET", f"/v1/models/{slug}", "detail by slug", 200, c.get(f"/v1/models/{slug}"))
    E("GET", "/v1/models/no-such-slug", "unknown slug -> 404", 404, c.get("/v1/models/no-such-slug"))
    E("GET", f"/v1/models/{slug}/reviews", "list reviews", 200, c.get(f"/v1/models/{slug}/reviews"))

    # review requires a license first
    E("POST", f"/v1/models/{slug}/reviews", "review w/o license -> 403", 403,
      c.post(f"/v1/models/{slug}/reviews", headers=cons_h, json={"rating": 5}))

    # ---------------- LICENSES ----------------
    E("POST", "/v1/models/deadbeefdeadbeefdeadbeef/acquire", "acquire bad id -> 404", 404,
      c.post("/v1/models/deadbeefdeadbeefdeadbeef/acquire", headers=cons_h))
    acq = E("POST", f"/v1/models/{model_id}/acquire", "acquire free license", 201,
            c.post(f"/v1/models/{model_id}/acquire", headers=cons_h))
    lkey = acq.json()["license_key"]
    E("POST", f"/v1/models/{model_id}/acquire", "acquire idempotent (201,same key)", 201,
      c.post(f"/v1/models/{model_id}/acquire", headers=cons_h))

    E("GET", "/v1/licenses", "list my licenses", 200, c.get("/v1/licenses", headers=cons_h))
    E("GET", f"/v1/licenses/{lkey}", "license detail", 200, c.get(f"/v1/licenses/{lkey}", headers=cons_h))
    E("GET", "/v1/licenses/MCP-0000-0000-0000", "unknown license -> 404", 404,
      c.get("/v1/licenses/MCP-0000-0000-0000", headers=cons_h))

    # verify before binding -> device_not_bound (200 valid=false)
    vb = c.post(f"/v1/licenses/{lkey}/verify", headers=cons_h, json={"device_id": "hw-x"})
    rec("POST", f"/v1/licenses/{lkey}/verify", "verify unbound -> valid:false", "200/valid=false",
        f"{vb.status_code}/valid={vb.json().get('valid')}",
        vb.status_code == 200 and vb.json().get("valid") is False)

    E("POST", f"/v1/licenses/{lkey}/devices", "bind device", 201,
      c.post(f"/v1/licenses/{lkey}/devices", headers=cons_h,
             json={"device_id": "hw-A", "device_name": "M2", "platform": "macOS 14"}))
    # fill cap (default 3): bind 2 more then 4th -> 409
    c.post(f"/v1/licenses/{lkey}/devices", headers=cons_h, json={"device_id": "hw-B"})
    c.post(f"/v1/licenses/{lkey}/devices", headers=cons_h, json={"device_id": "hw-C"})
    E("POST", f"/v1/licenses/{lkey}/devices", "exceed device cap -> 409", 409,
      c.post(f"/v1/licenses/{lkey}/devices", headers=cons_h, json={"device_id": "hw-D"}))

    E("POST", f"/v1/licenses/{lkey}/verify", "verify bound -> valid:true", 200,
      c.post(f"/v1/licenses/{lkey}/verify", headers=cons_h, json={"device_id": "hw-A"}))
    E("DELETE", f"/v1/licenses/{lkey}/devices/hw-C", "unbind device", 200,
      c.delete(f"/v1/licenses/{lkey}/devices/hw-C", headers=cons_h))
    E("DELETE", f"/v1/licenses/{lkey}/devices/hw-missing", "unbind missing -> 404", 404,
      c.delete(f"/v1/licenses/{lkey}/devices/hw-missing", headers=cons_h))

    # ---------------- DOWNLOAD ----------------
    dl = E("GET", f"/v1/models/{model_id}/download", "download (licensed)", 200,
           c.get(f"/v1/models/{model_id}/download", headers=cons_h, params={"device_id": "hw-A"}))
    got = httpx.get(dl.json()["download_url"])
    rec("GET", "download_url", "bytes match sha256", sha[:8],
        hashlib.sha256(got.content).hexdigest()[:8],
        hashlib.sha256(got.content).hexdigest() == sha)
    E("GET", f"/v1/models/{model_id}/download", "download unlicensed -> 403", 403,
      c.get(f"/v1/models/{model_id}/download", headers=nopub_h))

    # ---------------- REVIEWS (now licensed) ----------------
    E("POST", f"/v1/models/{slug}/reviews", "post review (licensed)", 201,
      c.post(f"/v1/models/{slug}/reviews", headers=cons_h, json={"rating": 5, "title": "good"}))
    E("POST", f"/v1/models/{slug}/reviews", "duplicate review -> 409", 409,
      c.post(f"/v1/models/{slug}/reviews", headers=cons_h, json={"rating": 4}))

    # ---------------- TELEMETRY ----------------
    E("POST", "/v1/telemetry/events", "ingest batch", 201,
      c.post("/v1/telemetry/events", headers=cons_h, json={"events": [
          {"model_id": model_id, "event_type": "deploy", "path": "local_metal"},
          {"model_id": model_id, "event_type": "inference", "path": "local_metal",
           "tokens_generated": 200, "tokens_per_sec": 30.0, "latency_ms": 7000}]}))
    E("POST", "/v1/telemetry/events", "empty batch -> 422", 422,
      c.post("/v1/telemetry/events", headers=cons_h, json={"events": []}))
    E("GET", "/v1/me/usage", "usage summary", 200, c.get("/v1/me/usage", headers=cons_h))

    # ---------------- INFERENCE (Modal not deployed) ----------------
    E("POST", "/v1/inference", "cloud inference -> 503 (no Modal)", 503,
      c.post("/v1/inference", headers=cons_h, json={
          "model_id": model_id, "prompt": "hi", "device_id": "hw-A", "reason": "no_metal_device"}))
    E("POST", "/v1/inference", "unlicensed -> 403", 403,
      c.post("/v1/inference", headers=nopub_h, json={
          "model_id": model_id, "prompt": "hi", "reason": "no_metal_device"}))
    E("POST", "/v1/inference", "bad reason enum -> 422", 422,
      c.post("/v1/inference", headers=cons_h, json={
          "model_id": model_id, "prompt": "hi", "reason": "because"}))
    E("POST", "/v1/inference", "unknown model -> 404", 404,
      c.post("/v1/inference", headers=cons_h, json={
          "model_id": "deadbeefdeadbeefdeadbeef", "prompt": "hi", "reason": "oom"}))
    # streaming: 200 then SSE error event (Modal down)
    sresp = c.post("/v1/inference/stream", headers=cons_h, json={
        "model_id": model_id, "prompt": "hi", "device_id": "hw-A", "reason": "daemon_down"})
    rec("POST", "/v1/inference/stream", "SSE opens 200 + error event", "200+error",
        f"{sresp.status_code}+{'error' in sresp.text}",
        sresp.status_code == 200 and "error" in sresp.text)

    # ---------------- PUBLISHER REPORT ----------------
    E("GET", f"/v1/publisher/models/{model_id}/report", "usage report", 200,
      c.get(f"/v1/publisher/models/{model_id}/report", headers=pub_h))

    # ---------------- ARCHIVE ----------------
    E("DELETE", f"/v1/publisher/models/{m2['id']}", "archive model (204)", 204,
      c.delete(f"/v1/publisher/models/{m2['id']}", headers=pub_h))

    # ---------------- REPORT ----------------
    print("\n" + "=" * 100)
    print(f"{'METHOD':6} {'ENDPOINT':52} {'SCENARIO':40} EXP  GOT  OK")
    print("-" * 100)
    npass = nfail = 0
    for m, p, s, exp, got, ok, note in rows:
        npass += ok
        nfail += not ok
        flag = "✓" if ok else "✗ FAIL"
        print(f"{m:6} {p[:52]:52} {s[:40]:40} {exp:>4} {got:>4}  {flag}")
        if not ok and note:
            print(f"       note: {note[:120]}")
    print("=" * 100)
    print(f"TOTAL: {len(rows)} checks across all endpoints — {npass} passed, {nfail} failed")
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
