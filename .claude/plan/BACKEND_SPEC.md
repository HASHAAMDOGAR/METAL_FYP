# Implementation Plan — Metal LLM Marketplace Backend

> Source spec: `.claude/specs/BACKEND_SPEC.md`. On approval, a copy of this plan should also be saved to `.claude/plan/BACKEND_SPEC.md` (the requested location; plan-mode only permits writing the designated plan file).

## Context

The repo currently contains only the SRS PDF and the backend spec — **no code**. This is a greenfield build of the server-side backend for the "Apple Metal-Powered LLM Marketplace with MCP Server Support" FYP, adapted to: **FastAPI + MongoDB (Beanie) + Cloudflare R2 + Modal**, with **no payments** (free models only) and **simplified licensing** (acquire → download → device binding).

The backend serves three client types it does not implement: the macOS MCP Server daemon, the Swift Developer SDK, and the web UI. The plan delivers every section of the spec (§4–§10) as an installable, testable FastAPI service.

### Confirmed decisions
- **MongoDB layer:** Beanie ODM (typed Documents, declarative indexes).
- **Scope:** Full backend, phased — a working vertical slice first, then breadth.
- **MCP Server auth:** reuses the logged-in user's JWT (no separate device-token issuance flow).

## Target layout (per spec §11)

```
backend/
├── pyproject.toml / requirements.txt
├── .env.example
├── app/
│   ├── main.py            # app factory, router mounts, middleware, lifespan
│   ├── config.py          # pydantic-settings (Settings)
│   ├── db.py              # Beanie/Motor init + index registration
│   ├── security.py        # JWT encode/decode, bcrypt, license-key gen
│   ├── deps.py            # current_user, require_roles, licensed-for-model guards
│   ├── errors.py          # error envelope + exception handlers
│   ├── models/            # Beanie Documents (one file per collection)
│   ├── schemas/           # Pydantic request/response models
│   ├── routers/           # auth, users, catalog, publisher, licenses, downloads, inference, telemetry, admin
│   ├── services/          # storage(R2), inference_service(Modal), licensing, reports
│   └── modal_app.py       # deployed separately with `modal deploy`
└── tests/
```

## Phases

### Phase 0 — Scaffolding & config
- `requirements.txt`: `fastapi`, `uvicorn[standard]`, `beanie`, `motor`, `pydantic`, `pydantic-settings`, `python-jose[cryptography]`, `passlib[bcrypt]`, `boto3`, `modal`, `python-multipart`, `httpx`, `pytest`, `pytest-asyncio`.
- `app/config.py`: `Settings` with all `.env` keys from spec §8.6 (`MONGODB_URI`, `JWT_SECRET`, `ACCESS_TTL`, `REFRESH_TTL`, `R2_*`, `MODAL_*`, `DOWNLOAD_URL_TTL`, `MAX_DEVICES_DEFAULT`). Provide `.env.example`.
- `app/main.py`: app factory, `lifespan` that calls `db.init_db()`, mounts routers under `/v1`, registers middleware + exception handlers. `/healthz`, `/readyz` (checks Mongo, R2 `head_bucket`, Modal lookup).

### Phase 1 — Data layer (Beanie Documents) — spec §4
One Document per collection in `app/models/`, with `Settings.indexes` matching the spec exactly:
- `user.py` — `User` (+embedded `PublisherProfile`); unique `email`, `username`.
- `model.py` — `ModelDoc` (+embedded `Artifact`, `Metrics`, `CloudInference`); unique `slug`, text index on name/description/tags, indexes on `publisher_id`, `architecture`, `tags`, `metrics.rating_avg`, `status`. Enums for `architecture`, `quantization`, `file_format`, `status`.
- `license.py` — `License`; unique `license_key`, unique compound `(user_id, model_id)`.
- `device.py` — `Device`; unique compound `(license_id, device_id)`.
- `review.py` — `Review`; unique compound `(model_id, user_id)`.
- `usage_event.py` — `UsageEvent`; indexes on `model_id`, `(user_id, occurred_at)`, optional TTL.
- `token_denylist.py` — refresh-token `jti` denylist (replaces Redis per §8.1), with TTL index on expiry.
- `app/db.py`: `init_beanie(database, document_models=[...])`.

### Phase 2 — Auth & users (vertical slice start) — spec §5.1, §8.1
- `app/security.py`: bcrypt hash/verify; JWT access (~15 min) + refresh (~7 days) with `jti`; `gen_license_key()`.
- `app/deps.py`: `get_current_user`, `require_roles(*roles)`, `require_license(model_id)`.
- `routers/auth.py`: register, login (OAuth2PasswordRequestForm), refresh (rotation + denylist check), logout (denylist insert).
- `routers/users.py`: `GET/PATCH /users/me`, `POST /users/me/become-publisher`.
- **Slice checkpoint:** register → login → `GET /users/me` works end-to-end.

### Phase 3 — Catalog (browse & search) — spec §5.2
- `routers/catalog.py`: `GET /models` (text `q` + structured filters + sort + pagination), `GET /models/{slug}`, `GET /models/{slug}/reviews`.
- `schemas/catalog.py`: `ModelListItem`, `ModelDetail`, `Page[T]` envelope.
- Public (no auth). Enforce pagination defaults; p95 < 2 s via indexes (§10 NFR-P1).

### Phase 4 — Publisher & admin model management — spec §5.3, §9.3
- `routers/publisher.py`: create draft, PATCH metadata, submit (`draft→pending_review`), archive, list own, `GET .../report`.
- `routers/admin.py`: approve / reject (+reason), guarded by `require_roles("admin")`.
- Validation: allow-list `architecture`/`quantization`/`file_format=gguf`; reject unsupported → `415/422` (UC-05/06 alt course).

### Phase 5 — Storage (Cloudflare R2) — spec §6
- `services/storage.py`: boto3 S3 client against R2 endpoint (`signature_version=s3v4`, `region_name=auto`); `presigned_put`, `presigned_get`, `head_object`, plus multipart helpers for large GGUF.
- `routers/publisher.py` artifact endpoint: `POST /publisher/models/{id}/artifact` → presigned PUT; finalize step records `size_bytes`, `sha256`, `version`.
- `routers/downloads.py`: `GET /models/{id}/download` → presigned GET + `sha256` + `size_bytes`; requires active license; logs `download` usage event.

### Phase 6 — Licensing & device binding — spec §5.4, §9.1
- `services/licensing.py`: `acquire(user, model)` (idempotent, unique `(user_id, model_id)`), `bind_device` (enforce `max_devices`, `409` on cap), `unbind_device`, `verify(license_key, device_id, auto_bind)`.
- `routers/licenses.py`: `POST /models/{id}/acquire`, `GET /licenses`, `GET /licenses/{key}`, `POST/DELETE /licenses/{key}/devices[...]`, `POST /licenses/{key}/verify`.
- **Slice checkpoint:** acquire → bind device → verify returns `{valid:true, model_artifact_ref}`.

### Phase 7 — Modal cloud inference fallback — spec §7, §5.6
- `app/modal_app.py`: Modal app `metal-llm-fallback` with `generate(model_ref, prompt, max_tokens, temperature)` on a GPU image (`llama-cpp-python`), returns `{output, tokens_generated, tokens_per_sec}`. Deployed out-of-band via `modal deploy`.
- `services/inference_service.py`: `cloud_generate(model, prompt, **opts)` via `modal.Function.lookup`.
- `routers/inference.py`: `POST /inference` (requires active license + `reason ∈ {no_metal_device,oom,daemon_down}` + `cloud_inference.enabled`; `503` if disabled/unreachable) and `POST /inference/stream` (SSE). Logs `usage_event` with `path="cloud_modal"`.

### Phase 8 — Telemetry & reports — spec §5.7
- `routers/telemetry.py`: `POST /telemetry/events` (batched ingest), `GET /me/usage` (summary).
- `services/reports.py`: aggregation pipelines for `GET /publisher/models/{id}/report` (downloads, inference counts, tokens/sec averages).

### Phase 9 — Cross-cutting hardening — spec §8, §10
- `app/errors.py`: error envelope `{ "error": { code, message, details } }`; handlers for validation, auth, not-found, conflict.
- Rate-limit middleware (in-process token bucket per IP+user, no Redis).
- Structured JSON logging + request IDs.

### Phase 10 — Tests & verification
- `tests/`: pytest + `httpx.AsyncClient` against a test Mongo (test container or ephemeral DB); fixtures for users/tokens/models; Modal + R2 mocked at the service boundary.
- Cover the two slice flows end-to-end + auth guards + device-cap `409` + unsupported-format `415`.
- `scripts/seed.py`: admin + sample publisher + 3 approved models (Llama/Mistral/Qwen) for the catalog.

## Critical files (most important to get right)
- `app/models/license.py` + `app/services/licensing.py` — the device-binding cap and idempotent acquire are the licensing core (spec §5.4, NFR-S4).
- `app/security.py` + `app/deps.py` — auth + role/license guards gate every protected route.
- `app/services/storage.py` — R2 presigned flows; bytes must never transit FastAPI (NFR-P3).
- `app/routers/inference.py` + `app/services/inference_service.py` — the Modal fallback contract and routing rules (§7.3).

## Verification
1. `uvicorn app.main:app --reload`; open `/docs` — all routers present.
2. `pytest` green.
3. Manual slice via `/docs` or httpx: register → login → (as publisher) create+upload+submit model → admin approve → (as consumer) `GET /models` shows it → acquire → bind device → verify `valid:true` → download returns presigned URL.
4. Cloud fallback: with Modal app deployed, `POST /inference` with `reason=no_metal_device` returns tokens and writes a `cloud_modal` usage event.
5. `GET /readyz` returns healthy for Mongo + R2 + Modal.

## Out of scope (per spec §1.2, §13)
MCP Server daemon, Swift SDK, web UI, MCP local IPC/TLS framing, paid models/Stripe/Redis. Modal hosts only free, redistributable models.
