# Backend Specification — Apple Metal-Powered LLM Marketplace with MCP Server Support

**Project:** Apple Metal-Powered LLM Marketplace with MCP Server Support for MacOS Developers
**Group:** F25CS008 (UCP BSCS Final Project)
**Document scope:** Complete backend specification (server-side services, APIs, data, integrations)
**Spec version:** 1.0
**Date:** 2026-06-03

---

## 0. How this differs from the original SRS

This backend spec implements the system described in the Phase-I SRS, with the following deliberate technology and scope adaptations:

| Area | Original SRS | This backend |
|---|---|---|
| API framework | Node.js / Fastify | **FastAPI (Python 3.11+)** |
| Database | PostgreSQL **or** MongoDB | **MongoDB** (document model) |
| Cloud inference | none (local Metal only) | **Modal** as cloud LLM inference fallback when local Metal is unavailable |
| Object storage | (S3 implied) | **Cloudflare R2** (S3-compatible, zero egress) for model weights |
| Payments | Stripe payment gateway, transaction fees | **Removed.** Free models only. No Stripe, no transaction/payout entities |
| Caching/queue | (implied Redis / RabbitMQ) | **No Redis.** In-process logic only; optional Modal-side queueing |
| Licensing | Purchase → License_Key → device run | **Simplified:** acquire (free) → download → **device binding**. No purchase flow |

Everything else (Metal-accelerated local inference, the MCP protocol, the MCP Server daemon, Developer SDK) stays conceptually identical. The MCP Server and SDK remain **native macOS (Swift/Metal)** components and are *clients* of this backend; this document specifies only the **server-side backend** plus the **contracts** the MCP Server/SDK depend on.

---

## 1. System Overview

### 1.1 Components in scope (backend)

1. **Marketplace API** — FastAPI service exposing REST + JSON over HTTPS. Handles:
   <!-- model weight artifacts are stored in Cloudflare R2; see §6 -->
   - User accounts & authentication (App Developers + Model Developers)
   - Model catalog: browse, search, filter, model detail
   - Publisher onboarding & model upload/management
   - Free licensing: license issuance and **device binding**
   - Model artifact storage & secure, authorized download
   - Ratings & reviews
   - Usage/monitoring telemetry ingestion + publisher reports
   - **License verification endpoint** consumed by the local MCP Server
2. **Cloud Inference Fallback (Modal)** — a Modal app that loads a (free) model and serves inference. The Marketplace API exposes an `/inference` proxy endpoint that routes to Modal **only when** the client reports local Metal is unavailable.
3. **MongoDB** — primary datastore.
4. **Cloudflare R2** — object storage for model weight files (GGUF) + metadata; S3-compatible API, accessed via boto3 (see §6).

### 1.2 Components out of scope (clients of this backend)

- **MCP Server** (local Swift/Metal daemon) — performs Metal-accelerated inference, calls backend for license verification and model download.
- **Developer SDK** (Swift) — wraps MCP protocol calls.
- **Marketplace Web UI** — browser frontend that consumes the Marketplace API.

### 1.3 High-level topology

```
                    HTTPS / JSON
 Browser (Web UI) ───────────────►┐
                                  │
 MCP Server (macOS, Swift) ──────►│   FastAPI Marketplace API ──► MongoDB
   - license verify               │            │
   - model download               │            ├──► Object storage (GGUF)
                                  │            ├──► Cloudflare R2 (GGUF weights)
 Developer SDK / Client App ─────►│            │
   (when local Metal unavailable) ┘            └──► Modal (cloud inference fallback)
```

### 1.4 Inference routing policy

- **Default path:** Client app → Developer SDK → local MCP Server → Metal Inference Engine (fully on-device, backend not involved in the inference itself).
- **Fallback path:** If the client/SDK reports no Apple Silicon Metal device available (e.g., unsupported hardware, OOM, or daemon down), the client calls `POST /inference` on the Marketplace API, which forwards to the Modal-hosted model and returns generated tokens.
- The backend **never** performs Metal inference itself; cloud fallback runs on Modal GPUs with a free model.

---

## 2. Technology Stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | type hints required |
| Web framework | FastAPI | async, OpenAPI auto-docs at `/docs` |
| ASGI server | Uvicorn (+ Gunicorn workers in prod) | |
| Data | MongoDB 6+ | via **Motor** (async driver) or **Beanie** ODM |
| Validation | Pydantic v2 | request/response models |
| Auth | OAuth2 password flow + **JWT** (`python-jose`), `passlib[bcrypt]` | access + refresh tokens |
| File storage | **Cloudflare R2** (S3-compatible, via boto3) | model weights; zero egress fees |
| Cloud inference | **Modal** | Python SDK, GPU container |
| Background work | FastAPI `BackgroundTasks` / Modal queues | **no Redis/Celery** |
| Config | `pydantic-settings` + `.env` | |
| Testing | `pytest`, `httpx.AsyncClient`, `mongomock`/test container | |

---

## 3. User Classes & Roles

| Role | Description | Key permissions |
|---|---|---|
| **App Developer (Consumer)** | macOS dev integrating LLMs into apps | browse/search, acquire free license, download, bind devices, rate/review, cloud-inference fallback |
| **Model Developer (Publisher)** | Publishes/optimizes LLMs for macOS | all consumer rights + upload/manage models, view usage reports |
| **Admin** (internal) | Platform operator | approve models, moderate reviews, manage users |
| **MCP Server (service principal)** | Local daemon acting on behalf of a user | license verification, authorized download (uses the user's token / device token) |

A single account may hold both `app_developer` and `model_developer` roles.

---

## 4. Data Model (MongoDB Collections)

MongoDB is schemaless at the engine level; schemas below are enforced via Pydantic/Beanie and optional JSON-schema validators. All documents carry `_id: ObjectId`, `created_at`, `updated_at` (UTC).

Derived from the SRS ERD (`USER`, `MODEL`, `LICENSE`, `TRANSACTION`). **TRANSACTION is dropped** (no payments). A `Device` concept is added for device binding, and a `UsageEvent` collection for monitoring.

### 4.1 `users`

```jsonc
{
  "_id": ObjectId,
  "email": "dev@example.com",          // unique, indexed
  "username": "muneeb",                 // unique, indexed
  "password_hash": "bcrypt$...",
  "roles": ["app_developer"],           // subset of [app_developer, model_developer, admin]
  "display_name": "Muneeb Ahmad",
  "is_active": true,
  "is_verified": false,                 // email verification (optional)
  "publisher_profile": {                // present iff model_developer
    "org_name": "Acme AI",
    "bio": "…",
    "website": "https://…"
  },
  "created_at": ISODate, "updated_at": ISODate
}
```
Indexes: `email` (unique), `username` (unique).

### 4.2 `models`  (catalog entry per published LLM)

```jsonc
{
  "_id": ObjectId,
  "slug": "llama-3-8b-instruct-q4",     // unique, indexed
  "name": "Llama 3 8B Instruct (Q4)",
  "publisher_id": ObjectId,             // -> users._id (model_developer)
  "description": "…",
  "architecture": "llama",              // llama | mistral | qwen | …
  "quantization": "Q4_K_M",             // GGUF quant label
  "file_format": "gguf",
  "param_count_b": 8.0,                  // billions
  "context_length": 8192,
  "min_ram_gb": 16,                      // deployment hint
  "tags": ["chat","instruct","code"],
  "use_cases": ["chat","summarization"],
  "license_type": "free",               // ALWAYS free in this build
  "price": 0,                            // fixed 0 (kept for schema stability)
  "status": "approved",                 // draft|pending_review|approved|rejected|archived
  "artifact": {
    "storage_key": "models/<id>/model.gguf",
    "size_bytes": 4733280256,
    "sha256": "…",                       // integrity check
    "version": "1.0.0"
  },
  "metrics": {
    "tokens_per_sec_m2": 31.4,           // published benchmark
    "downloads": 0,
    "rating_avg": 0.0,
    "rating_count": 0
  },
  "cloud_inference": {                   // Modal fallback config
    "enabled": true,
    "modal_app": "metal-llm-fallback",
    "modal_function": "generate",
    "served_model_ref": "llama-3-8b-instruct"
  },
  "created_at": ISODate, "updated_at": ISODate
}
```
Indexes: `slug` (unique), `publisher_id`, `architecture`, `tags`, text index on `name`+`description`+`tags`, `metrics.rating_avg`, `status`.

### 4.3 `licenses`  (free entitlement linking a user to a model)

```jsonc
{
  "_id": ObjectId,
  "license_key": "MCP-XXXX-XXXX-XXXX",   // unique, indexed, opaque
  "user_id": ObjectId,                   // -> users
  "model_id": ObjectId,                  // -> models
  "status": "active",                    // active|revoked
  "issued_at": ISODate,
  "max_devices": 3,                      // device-binding cap
  "bound_device_count": 1,
  "created_at": ISODate, "updated_at": ISODate
}
```
Constraints: unique `(user_id, model_id)` — one license per user/model. Indexes: `license_key` (unique), `(user_id, model_id)` (unique compound), `model_id`.

### 4.4 `devices`  (device binding for a license)

```jsonc
{
  "_id": ObjectId,
  "license_id": ObjectId,                // -> licenses
  "user_id": ObjectId,
  "device_id": "hw-uuid-...",            // hardware identifier from MCP Server
  "device_name": "Muneeb's M2 Air",
  "platform": "macOS 14.5 / M2",
  "bound_at": ISODate,
  "last_seen_at": ISODate,
  "status": "active"                     // active|unbound
}
```
Indexes: unique `(license_id, device_id)`, `device_id`.

### 4.5 `reviews`

```jsonc
{
  "_id": ObjectId,
  "model_id": ObjectId,
  "user_id": ObjectId,
  "rating": 4,                            // 1..5
  "title": "Fast on M2",
  "body": "…",
  "created_at": ISODate, "updated_at": ISODate
}
```
Indexes: unique `(model_id, user_id)` (one review per user/model), `model_id`.

### 4.6 `usage_events`  (monitoring telemetry)

```jsonc
{
  "_id": ObjectId,
  "model_id": ObjectId,
  "user_id": ObjectId,
  "device_id": "hw-uuid-...",
  "event_type": "inference",             // deploy|inference|unload|download
  "path": "local_metal",                 // local_metal | cloud_modal
  "tokens_generated": 256,
  "tokens_per_sec": 30.7,
  "latency_ms": 8340,
  "occurred_at": ISODate
}
```
Indexes: `model_id`, `(user_id, occurred_at)`, `occurred_at` (TTL optional for raw events).

### 4.7 Entity relationships (revised ERD)

```
USER 1───N MODEL          (publisher publishes models)
USER 1───N LICENSE        (a user holds many free licenses)
MODEL 1───N LICENSE       (a model is licensed to many users)
LICENSE 1───N DEVICE      (a license bound to <= max_devices)
USER 1───N REVIEW N───1 MODEL
MODEL 1───N USAGE_EVENT
```
*(TRANSACTION entity removed vs. SRS — no payments.)*

---

## 5. API Specification

Base URL: `https://api.<host>/v1`. All bodies JSON. Auth via `Authorization: Bearer <access_token>` unless marked public. Errors use a consistent envelope (§8).

### 5.1 Auth & Accounts

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | public | Create account (`email`, `username`, `password`, `roles?`) |
| POST | `/auth/login` | public | OAuth2 password → `{access_token, refresh_token, token_type}` |
| POST | `/auth/refresh` | refresh | Exchange refresh token for new access token |
| POST | `/auth/logout` | user | Invalidate refresh token (server-side denylist by jti) |
| GET | `/users/me` | user | Current profile |
| PATCH | `/users/me` | user | Update display name / publisher profile |
| POST | `/users/me/become-publisher` | user | Add `model_developer` role + publisher profile |

### 5.2 Catalog (Browse & Search) — FR 3.2

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/models` | public | List/search. Query: `q`, `architecture`, `tags`, `min_params`, `max_params`, `sort` (`downloads|rating|newest`), `page`, `page_size` |
| GET | `/models/{slug}` | public | Model detail (incl. metrics, reviews summary) |
| GET | `/models/{slug}/reviews` | public | Paginated reviews |

Search implementation: MongoDB text index for `q`; structured filters via indexed fields; sort on `metrics.*` / `created_at`. Target p95 < 2 s (NFR 4.1.3).

### 5.3 Publisher / Model Management — FR 3.4

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/publisher/models` | publisher | Create model draft (metadata, pricing fixed to free) |
| POST | `/publisher/models/{id}/artifact` | publisher | Upload GGUF (multipart or presigned-URL flow, §6) |
| PATCH | `/publisher/models/{id}` | publisher | Edit metadata; resubmit for review |
| POST | `/publisher/models/{id}/submit` | publisher | Move `draft → pending_review` |
| DELETE | `/publisher/models/{id}` | publisher | Archive |
| GET | `/publisher/models` | publisher | List own models |
| GET | `/publisher/models/{id}/report` | publisher | Usage report (downloads, inference counts, tokens/sec aggregates) |
| POST | `/admin/models/{id}/approve` | admin | `pending_review → approved` |
| POST | `/admin/models/{id}/reject` | admin | `pending_review → rejected` (+reason) |

Validation: only allow-listed `architecture`/`quantization`/`file_format` (`gguf`). Reject unsupported formats (SRS alt-course UC-05/06) with `415`/`422`.

### 5.4 Licensing & Device Binding — FR 3.4 (simplified, no purchase)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/models/{id}/acquire` | user | **Free acquire.** Idempotently issues a `license` for `(user, model)`; returns `license_key`. No payment |
| GET | `/licenses` | user | List my licenses |
| GET | `/licenses/{key}` | user/service | License detail (status, devices, caps) |
| POST | `/licenses/{key}/devices` | user/service | **Bind a device** (`device_id`, `device_name`, `platform`). Fails `409` if `bound_device_count >= max_devices` |
| DELETE | `/licenses/{key}/devices/{device_id}` | user | Unbind a device (frees a slot) |
| POST | `/licenses/{key}/verify` | **service (MCP Server)** | **License verification** for a given `device_id`. Returns `{valid, reason, model_artifact_ref}` |

`verify` is the endpoint the local MCP Server calls before loading a model (SRS UC-01 step 2 "confirms a valid license"). It checks: license `active`, model `approved`, and the device is bound (or auto-binds if under cap when `auto_bind=true`).

### 5.5 Download — FR 3.1 / Secure Download

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/models/{id}/download` | user/service (licensed) | Returns a short-lived **presigned download URL** + `sha256` + `size_bytes`. Requires an active license; logs a `download` usage event |

Authorization: caller must hold an `active` license for the model. The MCP Server uses this to fetch weights into local secure storage (D3).

### 5.6 Cloud Inference Fallback (Modal) — adaptation

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/inference` | user (licensed) | Cloud fallback inference. Body: `{model_id, prompt, max_tokens?, temperature?, device_id, reason}`. Routes to Modal. Returns `{output, tokens_generated, tokens_per_sec, path:"cloud_modal"}` |
| POST | `/inference/stream` | user (licensed) | Same, but `text/event-stream` (SSE) token streaming |

Preconditions: client asserts local Metal unavailable (`reason ∈ {no_metal_device, oom, daemon_down}`); license active; `model.cloud_inference.enabled = true`. The endpoint invokes the Modal function and records a `usage_event` with `path="cloud_modal"`.

### 5.7 Telemetry / Monitoring — FR Feature 9

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/telemetry/events` | user/service | Ingest usage events from MCP Server (batched array). `event_type`, `tokens_per_sec`, `latency_ms`, `path` |
| GET | `/me/usage` | user | My recent usage summary |

### 5.8 Health/Ops

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/healthz` | public | Liveness |
| GET | `/readyz` | public | Readiness (DB + storage + Modal reachability) |
| GET | `/docs`, `/openapi.json` | public | OpenAPI |

---

## 6. Model Artifact Storage & Upload (Cloudflare R2)

- **Store:** Cloudflare **R2** bucket, keyed `models/{model_id}/model.gguf`. R2 exposes an **S3-compatible API**, so the backend uses **boto3** with the R2 endpoint — no provider-specific SDK.
  - Endpoint: `https://<account_id>.r2.cloudflarestorage.com`
  - Credentials: R2 Access Key ID + Secret Access Key (S3-style)
  - **Zero egress fees** — well suited to repeated multi-GB GGUF downloads.
- **Upload flow (large GGUF files):**
  1. `POST /publisher/models/{id}/artifact` returns a **presigned PUT URL** (R2/S3 `put_object`). For very large files, use **multipart upload** (presigned part URLs + `complete_multipart_upload`).
  2. Publisher (or UI) uploads bytes **directly to R2** — bytes never transit FastAPI.
  3. Backend finalizes: records `size_bytes`, computes/verifies `sha256`, sets `artifact.version`.
- **Download flow:** `GET /models/{id}/download` returns a **presigned GET URL** (short TTL, e.g. 5 min) generated against R2 — bytes stream from R2, not the API. Integrity verified client-side via `sha256`. Optionally front the bucket with a Cloudflare **custom domain / CDN** for faster global pulls.
- **Security (SRS Safety 4.2.1):** R2 encrypts objects at rest by default; bucket is private (no public access); download authorized per active license; presigned URLs expire quickly.

```python
# services/storage.py — R2 via boto3
import boto3
from botocore.config import Config

r2 = boto3.client(
    "s3",
    endpoint_url=settings.R2_ENDPOINT,            # https://<acct>.r2.cloudflarestorage.com
    aws_access_key_id=settings.R2_ACCESS_KEY_ID,
    aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
    config=Config(signature_version="s3v4"),
    region_name="auto",
)

def presigned_put(key: str, ttl: int = 900) -> str:
    return r2.generate_presigned_url("put_object",
        Params={"Bucket": settings.R2_BUCKET, "Key": key}, ExpiresIn=ttl)

def presigned_get(key: str, ttl: int = 300) -> str:
    return r2.generate_presigned_url("get_object",
        Params={"Bucket": settings.R2_BUCKET, "Key": key}, ExpiresIn=ttl)
```

---

## 7. Cloud Inference with Modal (Detailed)

### 7.1 Modal app

A separate Modal Python app (`modal_app.py`) defines a GPU function that loads a free GGUF/transformers model and generates text. Deployed independently; the FastAPI backend calls it via the Modal SDK or an HTTPS web endpoint.

```python
# modal_app.py  (deployed: `modal deploy modal_app.py`)
import modal

app = modal.App("metal-llm-fallback")
image = (modal.Image.debian_slim()
         .pip_install("llama-cpp-python", "huggingface_hub"))

@app.function(image=image, gpu="A10G", timeout=300)
def generate(model_ref: str, prompt: str,
             max_tokens: int = 512, temperature: float = 0.7) -> dict:
    # load (cached) model by ref, run inference, return tokens + stats
    ...
    return {"output": text, "tokens_generated": n, "tokens_per_sec": tps}
```

### 7.2 Backend → Modal bridge

```python
# inference_service.py
import modal

async def cloud_generate(model: ModelDoc, prompt: str, **opts) -> InferenceResult:
    fn = modal.Function.lookup(model.cloud_inference.modal_app,
                               model.cloud_inference.modal_function)
    res = fn.remote(model.cloud_inference.served_model_ref, prompt, **opts)
    return InferenceResult(path="cloud_modal", **res)
```

### 7.3 Routing rules

| Condition | Route |
|---|---|
| Client has Metal device + MCP Server up | **local** (no backend inference call) |
| Client reports `no_metal_device` / `oom` / `daemon_down` AND `model.cloud_inference.enabled` | **Modal** via `POST /inference` |
| Cloud disabled for model OR Modal unreachable | `503` with actionable error |

All cloud inferences logged to `usage_events` (`path="cloud_modal"`) for publisher reports and cost visibility.

---

## 8. Cross-Cutting Backend Concerns

### 8.1 Authentication & Authorization
- OAuth2 password grant → JWT access token (~15 min) + refresh token (~7 days).
- Refresh-token rotation; server-side denylist (by `jti`) on logout — **stored in MongoDB**, not Redis.
- Role-based dependency guards in FastAPI (`require_roles("model_developer")`, etc.).
- MCP Server uses the user's token (or a device-scoped token) to call `verify`/`download`.

### 8.2 Error envelope
```jsonc
{ "error": { "code": "license_device_limit", "message": "Device cap reached", "details": {...} } }
```
Standard HTTP codes: `400/401/403/404/409/415/422/429/503`.

### 8.3 Validation
Pydantic v2 models for every request/response; reject unknown fields; enum-constrain `architecture`, `quantization`, `file_format`, `event_type`, `path`.

### 8.4 Rate limiting
Lightweight in-process / middleware token-bucket per IP+user (no Redis). Heavier limits enforced at the gateway/reverse-proxy layer if deployed.

### 8.5 Logging & observability
Structured JSON logs; request IDs; `usage_events` collection doubles as product analytics. `/readyz` checks Mongo, Cloudflare R2, and Modal.

### 8.6 Config (`.env`)
`MONGODB_URI`, `JWT_SECRET`, `ACCESS_TTL`, `REFRESH_TTL`, `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_ACCOUNT_ID`, `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, `MODAL_APP_NAME`, `DOWNLOAD_URL_TTL`, `MAX_DEVICES_DEFAULT`.

---

## 9. Key Backend Flows (Sequence-level)

### 9.1 Acquire → Download → Local deploy (maps to UC-01)
1. `POST /models/{id}/acquire` → issues free `license` (`license_key`).
2. MCP Server: `POST /licenses/{key}/devices` (or `verify?auto_bind=true`) → binds device.
3. MCP Server: `POST /licenses/{key}/verify` `{device_id}` → `{valid:true, model_artifact_ref}`.
4. MCP Server: `GET /models/{id}/download` → presigned URL + `sha256`; downloads weights to local secure storage.
5. MCP Server loads into Metal Inference Engine (on-device); posts `deploy` usage event.

### 9.2 Inference (local default vs. cloud fallback) (maps to UC-02)
- **Local:** SDK → MCP Server → Metal → tokens (backend uninvolved; SDK posts a `usage_event` with `path="local_metal"`).
- **Fallback:** SDK detects no Metal → `POST /inference {model_id, prompt, device_id, reason}` → backend verifies license → Modal `generate` → returns tokens; logs `path="cloud_modal"`.

### 9.3 Publish (maps to UC-05/06)
`POST /publisher/models` (draft) → `POST .../artifact` (upload GGUF) → `POST .../submit` → admin `approve` → appears in catalog. Unsupported format → `415/422`.

---

## 10. Non-Functional Requirements (backend)

| ID | Requirement |
|---|---|
| NFR-P1 | Catalog/detail/search endpoints p95 < **2 s** (SRS 4.1.3). |
| NFR-P2 | `verify` and `acquire` p95 < **300 ms** (block model load minimally). |
| NFR-P3 | Download endpoint returns presigned URL < 200 ms; bytes served by storage, not API. |
| NFR-P4 | Cloud fallback first-token latency target < a few seconds (model warm on Modal). |
| NFR-S1 | All traffic over HTTPS/TLS (SRS 4.3.1). |
| NFR-S2 | OAuth2 + JWT on all non-public endpoints (SRS 4.3.2). |
| NFR-S3 | Weights encrypted at rest; download authorized per active license; short-TTL URLs (SRS 4.2.1). |
| NFR-S4 | Only licensed `(user, device)` may verify/download a model (SRS Licensing Constraint). |
| NFR-Sc1 | Stateless API workers → horizontal scale behind a load balancer. |
| NFR-Sc2 | MongoDB indexes per §4; pagination mandatory on list endpoints. |
| NFR-R1 | Graceful `503` + retry guidance when Modal unreachable. |

*(PCI-DSS / payment-security NFRs from the SRS are N/A — no payments.)*

---

## 11. Suggested Project Structure (FastAPI)

```
backend/
├── app/
│   ├── main.py                 # FastAPI app, router mounts, middleware
│   ├── config.py               # pydantic-settings
│   ├── db.py                   # Motor/Beanie init, indexes
│   ├── deps.py                 # auth + role dependencies
│   ├── security.py             # JWT, password hashing
│   ├── models/                 # Beanie/Pydantic docs: user, model, license, device, review, usage_event
│   ├── schemas/                # request/response Pydantic models
│   ├── routers/
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── catalog.py
│   │   ├── publisher.py
│   │   ├── licenses.py         # acquire, verify, devices
│   │   ├── downloads.py
│   │   ├── inference.py        # Modal fallback
│   │   ├── telemetry.py
│   │   └── admin.py
│   ├── services/
│   │   ├── storage.py          # Cloudflare R2 (boto3) presigned URLs
│   │   ├── inference_service.py# Modal bridge
│   │   ├── licensing.py        # issue/verify/bind logic
│   │   └── reports.py          # publisher usage aggregations
│   └── modal_app.py            # deployed separately to Modal
└── tests/
```

---

## 12. Traceability (SRS → Backend)

| SRS item | Backend coverage |
|---|---|
| FR 3.1 LLM Model Deployment (UC-01) | §5.4 verify, §5.5 download, §9.1 |
| FR 3.2 Browsing & Search | §5.2, §4.2 indexes |
| FR 3.3 MCP Protocol Communication (UC-02) | local path (client) + §5.6 cloud fallback, §9.2 |
| FR 3.4 Monetization/Payments | **Re-scoped** to free licensing §5.4 (no payments) |
| FR 3.4 Model Publisher Mgmt (UC-05/06) | §5.3, §9.3 |
| ERD (USER/MODEL/LICENSE/TRANSACTION) | §4 (TRANSACTION dropped; DEVICE/USAGE added) |
| Class diagram (Model_License_Manager) | §5.4 licensing service (`verify/grant/revoke`) |
| Feature 9 Monitoring Dashboard | §5.7 telemetry + §5.3 publisher report |
| NFR 4.1–4.3 | §10 |

---

## 13. Open Items / Assumptions

1. **Storage backend** — Cloudflare R2 (S3-compatible via boto3). Confirm bucket, R2 API token, and whether a custom CDN domain fronts downloads.
2. **Model approval** — manual admin review assumed (per SRS UC-05 step 3).
3. **Device ID source** — provided by the MCP Server (hardware UUID); backend treats it as opaque.
4. **Modal models** — only free, redistributable models hosted on Modal for fallback; `served_model_ref` maps to a Modal-side loader.
5. **MCP protocol itself** (local IPC/TLS framing) is a client-side concern; backend only exposes the HTTPS contracts above.
```
