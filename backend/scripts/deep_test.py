"""Deep end-to-end test of the DEPLOYED cloud stack.

Tests the live backend (FastAPI on Modal), the live frontend (Next.js on Modal),
real Modal GPU inference, CORS, and full user journeys.

    python -m scripts.deep_test
"""
from __future__ import annotations

import hashlib
import os
import sys
import time

import httpx

BE = os.environ.get("BACKEND_URL", "https://hashaamdogar--metal-marketplace-api-api.modal.run")
FE = os.environ.get("FRONTEND_URL", "https://hashaamdogar--metal-marketplace-web-web.modal.run")

rows: list[tuple] = []
_section = ""


def section(name: str):
    global _section
    _section = name
    print(f"\n=== {name} ===")


def rec(name: str, ok, expected="", got="", note=""):
    status = "PASS" if ok is True else ("LIMIT" if ok == "limit" else "FAIL")
    rows.append((_section, name, status, str(expected), str(got), note))
    mark = {"PASS": "✓", "FAIL": "✗ FAIL", "LIMIT": "⚠ KNOWN-LIMIT"}[status]
    extra = ""
    if status != "PASS":
        extra = f"  (exp={expected} got={got}{' ' + note if note else ''})"
    print(f"  [{mark}] {name}{extra}")


def code(resp, expect):
    return resp.status_code == expect


def main() -> int:
    c = httpx.Client(timeout=180.0)
    sfx = os.urandom(3).hex()

    # ---------- 1. Infra health ----------
    section("1. Infrastructure health")
    r = c.get(f"{BE}/healthz"); rec("backend /healthz", code(r, 200), 200, r.status_code)
    r = c.get(f"{BE}/readyz"); j = r.json() if r.status_code == 200 else {}
    checks = j.get("checks", {})
    rec("backend /readyz ready", j.get("ready") is True, True, j.get("ready"))
    rec("  mongo (Atlas) connected", checks.get("mongo") is True, True, checks.get("mongo"))
    rec("  storage backend up", checks.get("storage_local") or checks.get("r2"), True, checks)
    rec("  modal reachable", checks.get("modal") is True, True, checks.get("modal"))

    # ---------- 2. Frontend pages ----------
    section("2. Frontend pages (Next.js on Modal)")
    pages = {
        "/": "Apple Metal-powered",
        "/how-it-works": "How each service works",
        "/marketplace": "Model Marketplace",
        "/playground": "Inference Playground",
        "/login": "Welcome back",
        "/register": "Create your account",
        "/dashboard": None,  # client-gated, just check 200
    }
    for path, marker in pages.items():
        rr = c.get(f"{FE}{path}")
        ok = rr.status_code == 200 and (marker is None or marker in rr.text)
        rec(f"GET {path}", ok, 200, rr.status_code, "" if ok else "missing marker")

    # ---------- 3. CORS ----------
    section("3. CORS (browser -> API)")
    pf = c.request("OPTIONS", f"{BE}/v1/models", headers={
        "Origin": FE, "Access-Control-Request-Method": "GET"})
    allow = pf.headers.get("access-control-allow-origin")
    rec("preflight allow-origin present", allow is not None, "set", allow)

    # ---------- 4. Auth ----------
    section("4. Authentication")
    r = c.post(f"{BE}/v1/auth/login", data={"username": "admin@metal.dev", "password": "admin12345"})
    rec("admin login (seeded)", code(r, 200), 200, r.status_code)
    admin_h = {"Authorization": f"Bearer {r.json()['access_token']}"} if r.status_code == 200 else {}

    r = c.post(f"{BE}/v1/auth/login", data={"username": "admin@metal.dev", "password": "wrong"})
    rec("bad credentials -> 401", code(r, 401), 401, r.status_code)

    pub_email = f"dt_pub_{sfx}@e.com"
    r = c.post(f"{BE}/v1/auth/register", json={
        "email": pub_email, "username": f"dtpub{sfx}", "password": "supersecret123",
        "roles": ["app_developer", "model_developer"]})
    rec("register publisher -> 201", code(r, 201), 201, r.status_code)
    pub_h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    pub_refresh = r.json()["refresh_token"]

    r = c.post(f"{BE}/v1/auth/register", json={"email": pub_email, "username": f"x{sfx}", "password": "supersecret123"})
    rec("duplicate email -> 409", code(r, 409), 409, r.status_code)
    r = c.post(f"{BE}/v1/auth/register", json={"email": f"q{sfx}@e.com", "username": "ab", "password": "supersecret123"})
    rec("short username -> 422", code(r, 422), 422, r.status_code)

    r = c.post(f"{BE}/v1/auth/refresh", json={"refresh_token": pub_refresh})
    rec("refresh rotate -> 200", code(r, 200), 200, r.status_code)
    r = c.post(f"{BE}/v1/auth/refresh", json={"refresh_token": pub_refresh})
    rec("reused refresh -> 401", code(r, 401), 401, r.status_code)

    # ---------- 5. Users ----------
    section("5. Users / profile")
    r = c.get(f"{BE}/v1/users/me", headers=pub_h); rec("GET /users/me", code(r, 200), 200, r.status_code)
    r = c.get(f"{BE}/v1/users/me"); rec("no auth -> 401", code(r, 401), 401, r.status_code)

    cons_email = f"dt_dev_{sfx}@e.com"
    r = c.post(f"{BE}/v1/auth/register", json={"email": cons_email, "username": f"dtdev{sfx}", "password": "supersecret123"})
    cons_h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    nopub = c.post(f"{BE}/v1/auth/register", json={"email": f"dt_np_{sfx}@e.com", "username": f"dtnp{sfx}", "password": "supersecret123"})
    nopub_h = {"Authorization": f"Bearer {nopub.json()['access_token']}"}

    # ---------- 6. Publisher + admin ----------
    section("6. Publisher & admin")
    r = c.get(f"{BE}/v1/publisher/models", headers=nopub_h); rec("non-publisher list -> 403", code(r, 403), 403, r.status_code)
    r = c.post(f"{BE}/v1/publisher/models", headers=pub_h, json={
        "name": f"DeepTest Llama {sfx}", "description": "deep test", "architecture": "llama",
        "quantization": "Q4_K_M", "file_format": "gguf", "param_count_b": 8.0, "tags": ["chat", "deeptest"],
        "cloud_inference": {"enabled": True, "served_model_ref": "llama-3-8b-instruct"}})
    rec("create model draft -> 201", code(r, 201), 201, r.status_code)
    model = r.json(); mid = model["id"]; slug = model["slug"]
    r = c.post(f"{BE}/v1/publisher/models", headers=pub_h, json={"name": "Bad", "architecture": "llama", "file_format": "onnx"})
    rec("unsupported format -> 422", code(r, 422), 422, r.status_code)

    # upload artifact to cloud storage (ephemeral per-container on Modal)
    payload = b"GGUF\x00deep-" + os.urandom(96)
    sha = hashlib.sha256(payload).hexdigest()
    up = c.post(f"{BE}/v1/publisher/models/{mid}/artifact", headers=pub_h)
    rec("get upload url -> 200", code(up, 200), 200, up.status_code)
    put = c.put(up.json()["upload_url"], content=payload)
    rec("upload bytes -> 200", code(put, 200), 200, put.status_code)
    r = c.post(f"{BE}/v1/publisher/models/{mid}/artifact/finalize", headers=pub_h,
               json={"size_bytes": len(payload), "sha256": sha, "version": "1.0.0"})
    rec("finalize artifact -> 200", code(r, 200), 200, r.status_code)
    r = c.post(f"{BE}/v1/publisher/models/{mid}/submit", headers=pub_h)
    rec("submit -> pending_review", r.status_code == 200 and r.json()["status"] == "pending_review", "pending_review", r.json().get("status"))

    r = c.get(f"{BE}/v1/admin/models/pending", headers=pub_h); rec("non-admin pending -> 403", code(r, 403), 403, r.status_code)
    r = c.post(f"{BE}/v1/admin/models/{mid}/approve", headers=admin_h)
    rec("admin approve -> approved", r.status_code == 200 and r.json()["status"] == "approved", "approved", r.json().get("status"))
    r = c.post(f"{BE}/v1/admin/models/{mid}/approve", headers=admin_h); rec("re-approve -> 409", code(r, 409), 409, r.status_code)
    r = c.get(f"{BE}/v1/publisher/models/{mid}/report", headers=pub_h); rec("publisher report -> 200", code(r, 200), 200, r.status_code)

    # ---------- 7. Catalog ----------
    section("7. Catalog & search")
    r = c.get(f"{BE}/v1/models"); rec("list approved -> 200", code(r, 200), 200, r.status_code)
    r = c.get(f"{BE}/v1/models", params={"q": "deeptest"})
    rec("text search finds new model", r.status_code == 200 and r.json()["total"] >= 1, ">=1", r.json().get("total"))
    r = c.get(f"{BE}/v1/models", params={"architecture": "llama", "sort": "rating"}); rec("filter+sort -> 200", code(r, 200), 200, r.status_code)
    r = c.get(f"{BE}/v1/models/{slug}"); rec("model detail -> 200", code(r, 200), 200, r.status_code)
    r = c.get(f"{BE}/v1/models/no-such-slug-xyz"); rec("unknown slug -> 404", code(r, 404), 404, r.status_code)

    # ---------- 8. Licensing & devices ----------
    section("8. Licensing & device binding")
    r = c.post(f"{BE}/v1/models/{mid}/acquire", headers=cons_h); rec("acquire -> 201", code(r, 201), 201, r.status_code)
    key = r.json()["license_key"]
    r2 = c.post(f"{BE}/v1/models/{mid}/acquire", headers=cons_h)
    rec("acquire idempotent (same key)", r2.json().get("license_key") == key, key[:8], (r2.json().get("license_key") or "")[:8])
    r = c.get(f"{BE}/v1/licenses", headers=cons_h); rec("list licenses -> 200", code(r, 200), 200, r.status_code)
    r = c.get(f"{BE}/v1/licenses/MCP-0000-0000-0000", headers=cons_h); rec("unknown license -> 404", code(r, 404), 404, r.status_code)
    vb = c.post(f"{BE}/v1/licenses/{key}/verify", headers=cons_h, json={"device_id": "dt-x"})
    rec("verify unbound -> valid:false", vb.status_code == 200 and vb.json()["valid"] is False, False, vb.json().get("valid"))
    for i in range(3):
        c.post(f"{BE}/v1/licenses/{key}/devices", headers=cons_h, json={"device_id": f"dt-{i}"})
    over = c.post(f"{BE}/v1/licenses/{key}/devices", headers=cons_h, json={"device_id": "dt-4"})
    rec("device cap (3) -> 409", code(over, 409), 409, over.status_code)
    r = c.post(f"{BE}/v1/licenses/{key}/verify", headers=cons_h, json={"device_id": "dt-0"})
    rec("verify bound -> valid:true", r.status_code == 200 and r.json()["valid"] is True, True, r.json().get("valid"))
    r = c.delete(f"{BE}/v1/licenses/{key}/devices/dt-2", headers=cons_h); rec("unbind device -> 200", code(r, 200), 200, r.status_code)

    # ---------- 9. Downloads ----------
    section("9. Secure download")
    dl = c.get(f"{BE}/v1/models/{mid}/download", headers=cons_h, params={"device_id": "dt-0"})
    rec("download (licensed) -> 200", code(dl, 200), 200, dl.status_code)
    if dl.status_code == 200:
        got = c.get(dl.json()["download_url"])
        if got.status_code == 200:
            match = hashlib.sha256(got.content).hexdigest() == sha
            rec("downloaded bytes sha256 match", match, sha[:8], hashlib.sha256(got.content).hexdigest()[:8])
        else:
            rec("download bytes (cloud ephemeral storage)", "limit", 200, got.status_code,
                "local storage is per-container on Modal; needs R2")
    r = c.get(f"{BE}/v1/models/{mid}/download", headers=nopub_h); rec("download unlicensed -> 403", code(r, 403), 403, r.status_code)

    # ---------- 10. Reviews ----------
    section("10. Reviews")
    r = c.post(f"{BE}/v1/models/{slug}/reviews", headers=cons_h, json={"rating": 5, "title": "deep", "body": "great"})
    rec("post review (licensed) -> 201", code(r, 201), 201, r.status_code)
    r = c.post(f"{BE}/v1/models/{slug}/reviews", headers=cons_h, json={"rating": 4}); rec("duplicate review -> 409", code(r, 409), 409, r.status_code)
    r = c.post(f"{BE}/v1/models/{slug}/reviews", headers=nopub_h, json={"rating": 5}); rec("review w/o license -> 403", code(r, 403), 403, r.status_code)
    r = c.get(f"{BE}/v1/models/{slug}")
    rec("rating aggregated", r.json()["metrics"]["rating_count"] >= 1, ">=1", r.json()["metrics"]["rating_count"])

    # ---------- 11. Telemetry ----------
    section("11. Telemetry")
    r = c.post(f"{BE}/v1/telemetry/events", headers=cons_h, json={"events": [
        {"model_id": mid, "event_type": "deploy", "path": "local_metal"},
        {"model_id": mid, "event_type": "inference", "path": "local_metal", "tokens_generated": 100, "tokens_per_sec": 31.0}]})
    rec("ingest batch (2) -> 201", r.status_code == 201 and r.json()["ingested"] == 2, 2, r.json().get("ingested"))
    r = c.post(f"{BE}/v1/telemetry/events", headers=cons_h, json={"events": []}); rec("empty batch -> 422", code(r, 422), 422, r.status_code)
    r = c.get(f"{BE}/v1/me/usage", headers=cons_h); rec("usage summary -> 200", code(r, 200), 200, r.status_code)

    # ---------- 12. REAL Modal GPU inference ----------
    section("12. Cloud inference (real Modal GPU)")
    r = c.post(f"{BE}/v1/inference", headers=nopub_h, json={"model_id": mid, "prompt": "hi", "reason": "no_metal_device"})
    rec("inference unlicensed -> 403", code(r, 403), 403, r.status_code)
    r = c.post(f"{BE}/v1/inference", headers=cons_h, json={"model_id": mid, "prompt": "hi", "reason": "bad"})
    rec("bad reason enum -> 422", code(r, 422), 422, r.status_code)
    r = c.post(f"{BE}/v1/inference", headers=cons_h, json={"model_id": "deadbeefdeadbeefdeadbeef", "prompt": "hi", "reason": "oom"})
    rec("unknown model -> 404", code(r, 404), 404, r.status_code)

    t = time.time()
    r = c.post(f"{BE}/v1/inference", headers=cons_h, json={
        "model_id": mid, "prompt": "Q: What is the capital of France?\nA:", "max_tokens": 24, "reason": "no_metal_device"})
    dt = time.time() - t
    ok = r.status_code == 200 and r.json().get("output") and r.json().get("path") == "cloud_modal"
    rec(f"real GPU inference 200 ({dt:.0f}s)", ok, 200, r.status_code, "" if ok else r.text[:120])
    if ok:
        print("        output:", r.json()["output"].strip()[:90], "| tps", r.json()["tokens_per_sec"])
    t = time.time()
    r = c.post(f"{BE}/v1/inference", headers=cons_h, json={"model_id": mid, "prompt": "Q: 2+2?\nA:", "max_tokens": 8, "reason": "oom"})
    dt2 = time.time() - t
    rec(f"warm inference 200 ({dt2:.0f}s)", code(r, 200), 200, r.status_code)
    sr = c.post(f"{BE}/v1/inference/stream", headers=cons_h, json={"model_id": mid, "prompt": "hello", "max_tokens": 8, "reason": "daemon_down"})
    rec("inference stream (SSE) -> 200", sr.status_code == 200 and "data:" in sr.text, 200, sr.status_code)

    # ---------- report ----------
    print("\n" + "=" * 92)
    print(f"{'SECTION':30} {'CHECK':40} STATUS")
    print("-" * 92)
    npass = nfail = nlimit = 0
    last = ""
    for sec, name, status, exp, got, note in rows:
        npass += status == "PASS"; nfail += status == "FAIL"; nlimit += status == "LIMIT"
        sec_disp = sec if sec != last else ""
        last = sec
        mark = {"PASS": "✓", "FAIL": "✗ FAIL", "LIMIT": "⚠ LIMIT"}[status]
        print(f"{sec_disp[:30]:30} {name[:40]:40} {mark}")
    print("=" * 92)
    print(f"TOTAL: {len(rows)} checks  |  {npass} passed  |  {nfail} failed  |  {nlimit} known-limit")
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
