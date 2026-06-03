# Apple Metal-Powered LLM Marketplace — End-to-End Project Report

**Group:** F25CS008 (UCP BSCS Final Year Project)
**Document:** Complete end-to-end record of everything built, deployed, tested, and outstanding.
**Last updated:** 2026-06-03

---

## 1. What this project is

A two-sided platform for distributing and running Large Language Models (LLMs) natively on Apple Silicon:

- **Marketplace** — a hosted web platform where **Model Developers** publish LLMs and **App Developers** discover, license, download, and run them.
- **MCP Server** — a local macOS daemon that loads licensed models and runs **Metal-accelerated** (Apple GPU) inference, talking to client apps over a custom **MCP protocol**.
- **Developer SDK** — a thin Swift library so macOS apps call the local server as easily as a function.

The original SRS targeted Node/Fastify + PostgreSQL + Stripe payments. **This implementation deliberately adapts the stack** (see §3) and focuses on the **server-side backend + a full web frontend + cloud deployment**, with a **Modal GPU fallback** for inference when local Apple Metal is unavailable.

### The core idea
> Bring LLM inference to the Apple GPU (Metal) for speed, wrap it in a licensed marketplace for distribution, and provide a cloud GPU fallback so the experience works everywhere.

---

## 2. Architecture (as built)

```
                              ┌───────────────────────────────────────────────┐
  Browser ──────────────────► │  Next.js Frontend (Modal container)           │
                              │  metal-marketplace-web                         │
                              └───────────────┬───────────────────────────────┘
                                              │ HTTPS / JSON (CORS)
                                              ▼
  MCP Server (macOS, Swift) ──► ┌─────────────────────────────────────────────┐
   - license verify             │  FastAPI Backend (Modal web service)         │
   - model download             │  metal-marketplace-api  ── "api" (umbrella)  │
  Developer SDK ──────────────► └──────┬───────────────┬───────────────┬───────┘
   (cloud inference fallback)          │               │               │
                                       ▼               ▼               ▼
                              MongoDB Atlas     (Cloudflare R2)     Modal GPU app
                              users/models/     model weights —     metal-llm-fallback
                              licenses/...       LOCAL fallback      generate() A10G
                                                 for now (R2 TODO)
```

### Components
| Component | Status | Where |
|---|---|---|
| **Marketplace API** (FastAPI) | ✅ built + deployed | `backend/app/` |
| **Web Frontend** (Next.js) | ✅ built + deployed | `frontend/` |
| **Cloud inference** (Modal GPU) | ✅ built + deployed | `backend/app/modal_app.py` |
| **MongoDB** (Atlas) | ✅ live + seeded | cloud |
| **Object storage** (Cloudflare R2) | ⏳ optional, deferred | local fallback active |
| **MCP Server** (macOS daemon, Swift/Metal) | ❌ out of scope (client) | — |
| **Developer SDK** (Swift) | ❌ out of scope (client) | — |

---

## 3. Technology stack & adaptations

| Area | Original SRS | This build | Status |
|---|---|---|---|
| API framework | Node.js / Fastify | **FastAPI (Python 3.12)** | ✅ |
| Database | PostgreSQL/Mongo | **MongoDB (Beanie ODM) → Atlas** | ✅ |
| Object storage | S3 implied | **Cloudflare R2** (S3-compatible) + local fallback | ⏳ R2 pending creds |
| Cloud inference | none | **Modal** (A10G GPU, llama-cpp) | ✅ |
| Payments | Stripe + fees | **Removed** — free models only | ✅ (by design) |
| Cache/queue | Redis/RabbitMQ | **None** (Mongo TTL denylist) | ✅ (by design) |
| Licensing | purchase → key → run | **acquire (free) → device binding** | ✅ |
| Frontend | — | **Next.js 14 (App Router, TS, Tailwind)** | ✅ |
| Hosting | — | **Modal** (backend, frontend, GPU) | ✅ |

---

## 4. The backend (FastAPI) — what was built

Location: `backend/`. Async FastAPI app, Beanie ODM over Motor, JWT auth, OpenAPI docs at `/docs`.

### 4.1 Data model (MongoDB collections)
| Collection | Purpose | Key constraints |
|---|---|---|
| `users` | accounts + roles (`app_developer`, `model_developer`, `admin`) | unique email & username |
| `models` | catalog entries (GGUF metadata, benchmarks, cloud-inference config) | unique slug, text index |
| `licenses` | free entitlements (user↔model) | unique (user, model), opaque `license_key` |
| `devices` | device bindings per license | unique (license, device), cap = `max_devices` (3) |
| `reviews` | ratings 1–5 | unique (model, user) |
| `usage_events` | telemetry (deploy/inference/download) | indexed by model/user/time |
| `token_denylist` | revoked refresh-token jtis | TTL index (replaces Redis) |

*(The SRS `TRANSACTION` entity was dropped — no payments. `DEVICE` and `USAGE_EVENT` were added.)*

### 4.2 API surface (all implemented & tested)
| Group | Endpoints |
|---|---|
| **Auth** | `POST /v1/auth/register`, `/login`, `/refresh`, `/logout` |
| **Users** | `GET/PATCH /v1/users/me`, `POST /v1/users/me/become-publisher` |
| **Catalog** | `GET /v1/models` (search/filter/sort/paginate), `GET /v1/models/{slug}`, `…/reviews`, `POST …/reviews` |
| **Publisher** | `POST /v1/publisher/models`, `…/artifact` (+`/finalize`), `…/submit`, `PATCH`, `DELETE`, `GET …/report`, `GET /v1/publisher/models` |
| **Admin** | `GET /v1/admin/models/pending`, `POST …/approve`, `…/reject` |
| **Licensing** | `POST /v1/models/{id}/acquire`, `GET /v1/licenses`, `GET …/{key}`, `POST/DELETE …/devices`, `POST …/verify` |
| **Downloads** | `GET /v1/models/{id}/download` (presigned, license-gated) |
| **Inference** | `POST /v1/inference`, `POST /v1/inference/stream` (Modal fallback) |
| **Telemetry** | `POST /v1/telemetry/events`, `GET /v1/me/usage` |
| **Storage (dev)** | `PUT/GET /v1/storage/local/{key}` (local R2 substitute) |
| **Ops** | `GET /healthz`, `GET /readyz`, `/docs`, `/openapi.json` |

### 4.3 Cross-cutting
- **Auth:** OAuth2 password → JWT access (15m) + refresh (7d) with rotation; logout denylists the refresh jti in Mongo.
- **Authorization:** role guards (`require_roles`) + license guards (`require_license`).
- **Storage abstraction:** `STORAGE_BACKEND=local|r2` — same interface, swap with no code change.
- **Errors:** consistent envelope `{error:{code,message,details}}`.
- **Hardening:** request-id logging, in-process rate limiter (no Redis), DB-tolerant startup, CORS.

### 4.4 Project layout
```
backend/app/
  main.py            # app factory, router registry, lifespan, health/ready, CORS
  config.py          # pydantic-settings
  db.py              # Beanie/Motor init
  security.py        # JWT, bcrypt, license-key gen
  deps.py            # auth/role/license guards
  errors.py          # error envelope
  middleware.py      # request-id + rate limit
  models/            # 7 Beanie documents + enums
  schemas/           # Pydantic request/response models
  routers/           # auth, users, catalog, publisher, admin, licenses,
                     # downloads, inference, telemetry, storage_local
  services/          # storage (R2/local), licensing, inference_service (Modal), reports
  modal_app.py       # Modal GPU inference app (deployed separately)
  modal_deploy.py    # Modal deploy of the FastAPI app (umbrella + per-API)
backend/scripts/     # seed.py, smoke_test.py, full_api_test.py, deep_test.py
backend/tests/       # pytest suite
```

---

## 5. Cloud inference (Modal) — what was built

- **`backend/app/modal_app.py`** → Modal app **`metal-llm-fallback`**, function **`generate(model_ref, prompt, max_tokens, temperature)`** on an **A10G GPU**, loading free GGUF models (Llama-3-8B / Mistral-7B / Qwen2.5-7B) via `llama-cpp-python`, with a cached Volume for weights.
- **Bridge:** `services/inference_service.py` resolves the function with `modal.Function.from_name(...)` and calls `await fn.remote.aio(...)`.
- **Routing:** `POST /v1/inference` requires an active license + a `reason ∈ {no_metal_device, oom, daemon_down}` + `cloud_inference.enabled`; logs a `usage_event` with `path=cloud_modal`.
- **Verified live:** cold start ~13–77s (first call downloads the model), warm ~3–4s.

---

## 6. The frontend (Next.js) — what was built

Location: `frontend/`. Next.js 14 (App Router), TypeScript, Tailwind, dark "Apple Metal" theme.

| Page | What it does |
|---|---|
| `/` | **Purpose page** — problem, solution, 3 innovations, animated architecture, tech stack |
| `/how-it-works` | **Service docs** — every API group (purpose, endpoints, how-to), lifecycle, cURL quickstart |
| `/marketplace` | Browse/search catalog with filters + sorting (live API) |
| `/marketplace/[slug]` | Model detail: specs, benchmarks, reviews, **acquire license**, link to playground |
| `/playground` | **Live inference** via the Modal GPU fallback (auto-acquires license) |
| `/login`, `/register` | JWT auth (consumer or publisher) |
| `/dashboard` | Licenses, **device bind/unbind**, **downloads** |

- API client: `frontend/lib/api.ts` (typed). Auth context: `frontend/lib/auth.tsx` (localStorage JWT).
- Deployed via `frontend/modal_app.py` — a `node:20-slim` Modal image that builds Next.js and serves it with `next start` behind `@modal.web_server(3000)`.

---

## 7. Deployments (live)

| Thing | URL / ID | Status |
|---|---|---|
| **Frontend** | https://hashaamdogar--metal-marketplace-web-web.modal.run | ✅ live |
| **Backend API** | https://hashaamdogar--metal-marketplace-api-api.modal.run | ✅ live |
| API docs | …-api.modal.run/docs | ✅ |
| **Modal GPU inference** | app `metal-llm-fallback` / `generate` | ✅ live |
| **MongoDB** | Atlas `cluster0.ghr08hl`, db `metal_marketplace` | ✅ live + seeded |
| Demo admin | `admin@metal.dev` / `admin12345` | ✅ |

**Modal apps deployed:** `metal-marketplace-web`, `metal-marketplace-api`, `metal-llm-fallback`.
**Config:** Modal secret `metal-backend-config` (Atlas URI, JWT secret, storage, etc.).

> Note: backend is currently deployed as a **single "umbrella" web service** (serves all APIs) to fit Modal's **8-web-function plan limit**. Per-API services exist in code (`DEPLOY_PER_API=1`) and need a plan upgrade to deploy individually.

---

## 8. Key end-to-end flows (all working)

1. **Publish:** create draft → presigned upload of GGUF → finalize (sha256) → submit → admin approve → appears in catalog.
2. **Acquire & run (local intent):** acquire free license → MCP server binds device → `verify` → presigned download → load into Metal engine *(MCP/Metal part is client-side, out of scope)*.
3. **Cloud fallback inference:** client reports no local Metal → `POST /inference` → license check → Modal GPU → tokens returned + telemetry logged.
4. **Web journey:** register → browse → model detail → acquire → dashboard (bind device, download) → playground (live GPU inference).

---

## 9. Testing — what was verified

| Suite | Scope | Result |
|---|---|---|
| **Unit tests** (`pytest`) | in-memory Mongo, services & guards | ✅ 10/10 |
| **Full API test** (`full_api_test.py`) | every endpoint, happy + error paths (local) | ✅ 77/77 |
| **Smoke test** (`smoke_test.py`) | core journey (local) | ✅ 23/23 |
| **Deep test** (`deep_test.py`) | **live cloud** — infra, frontend pages, CORS, all APIs, real GPU inference | ✅ 62/62 |

Deep test highlights: `/readyz` all-green (mongo+storage+modal), 7 frontend pages 200, CORS verified, device cap 409, byte-exact download, **real Modal GPU inference** (cold 13s / warm 3s), SSE stream.

---

## 10. Done vs. missing — checklist

### ✅ Done
- [x] Full FastAPI backend (all SRS functional requirements, re-scoped for free licensing)
- [x] MongoDB schema (Beanie) + indexes; seeded Atlas
- [x] JWT auth, roles, license/device guards
- [x] Catalog browse/search (Mongo text index), reviews, ratings
- [x] Publisher upload (presigned) + admin approval workflow
- [x] Free licensing + device binding + license verification endpoint
- [x] Secure, license-gated downloads
- [x] Modal GPU cloud inference (+ streaming) — deployed & live
- [x] Telemetry ingestion + publisher reports
- [x] Storage abstraction (local now, R2-ready)
- [x] Next.js frontend (7 pages) — purpose, service docs, marketplace, playground, auth, dashboard
- [x] Deployed: backend + frontend + GPU app on Modal, DB on Atlas
- [x] CORS, error envelope, rate limiting, request logging
- [x] Test suites: unit, full-API, smoke, deep (live)

### ⏳ Pending / optional
- [ ] **Cloudflare R2 storage** — code ready; needs an R2 API token. Today storage is **local & per-container ephemeral** on Modal (cross-container downloads would miss at scale).
- [ ] **Per-API Modal services** — coded behind `DEPLOY_PER_API=1`; blocked by Modal's 8-web-function plan limit.
- [ ] **Production Mongo security** — Atlas is open to `0.0.0.0/0` (required for Modal's dynamic IPs). Fine for an FYP; tighten with static IPs/PrivateLink for production.
- [ ] **Email verification / password reset** — `is_verified` field exists; flow not implemented.
- [ ] **Real model weights in catalog** — seeded models point to Modal-side refs for inference; download artifacts are placeholders unless a real GGUF is uploaded.

### ❌ Out of scope (client-side, per SRS exclusions)
- [ ] **MCP Server** (macOS Swift/Metal daemon) — performs actual on-device Metal inference; this repo only provides the backend contracts it consumes (`verify`, `download`).
- [ ] **Developer SDK** (Swift) — wraps the MCP protocol.
- [ ] **MCP protocol / local IPC + TLS framing** — client concern.
- [ ] **Payments / Stripe / Redis** — intentionally removed.
- [ ] Non-Apple-Silicon (Intel) support, iOS/iPadOS SDKs, multi-machine distributed inference.

---

## 11. Known limitations / risks
1. **Ephemeral storage in the cloud** — until R2 is wired, uploaded weights live in a single Modal container's `/tmp`; reliable only within one warm container.
2. **Modal plan limits** — 8 web functions per workspace; the backend runs as one umbrella service to leave room for the frontend.
3. **Open Atlas network access** — credentials still required, but IP allowlist is `0.0.0.0/0`.
4. **JWT secret** lives in a Modal secret; rotating it invalidates existing tokens.
5. **No real GGUF download artifacts** for seeded models (inference works via Modal refs; downloads need real uploads).
6. **bcrypt/passlib** logs a benign version-detection warning (functionally fine).

---

## 12. How to run & redeploy

### Local backend
```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # local mongod or Atlas URI
uvicorn app.main:app --reload   # docs at /docs
python -m scripts.seed          # admin + 3 models
pytest                          # unit tests
```

### Local frontend
```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

### Deploy to Modal
```bash
# GPU inference app
modal deploy backend/app/modal_app.py

# backend (umbrella only; add DEPLOY_PER_API=1 for per-API on a higher plan)
cd backend && modal deploy app/modal_deploy.py::modal_app

# frontend container
cd frontend && modal deploy modal_app.py::app
```

### Switch storage to R2 (when token available)
```bash
modal secret create metal-backend-config STORAGE_BACKEND=r2 \
  R2_ENDPOINT=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... R2_BUCKET=... \
  MONGODB_URI=... JWT_SECRET=... --force
cd backend && modal deploy app/modal_deploy.py::modal_app
```

### Run the live deep test
```bash
cd backend && source .venv/bin/activate && python -m scripts.deep_test
```

---

## 13. Configuration reference (env / Modal secret)
`MONGODB_URI`, `MONGODB_DB`, `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TTL`, `REFRESH_TTL`,
`STORAGE_BACKEND` (`local`|`r2`), `LOCAL_STORAGE_DIR`, `PUBLIC_BASE_URL`,
`R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_ACCOUNT_ID`,
`MODAL_APP_NAME`, `MAX_DEVICES_DEFAULT`, `RATE_LIMIT_PER_MINUTE`,
`DOWNLOAD_URL_TTL`, `UPLOAD_URL_TTL`.
Frontend (build-time): `NEXT_PUBLIC_API_URL`.

---

## 14. Suggested next steps (priority order)
1. **Wire Cloudflare R2** (create token → update secret → redeploy) — makes storage durable & multi-container correct.
2. **Upload a real GGUF** for at least one model so the full download→run path uses real weights.
3. **Upgrade Modal plan** (optional) → deploy per-API services for isolation/scaling.
4. **Tighten Atlas** network access for production.
5. **Build the macOS MCP Server + Swift SDK** (the on-device Metal half) — consumes the `verify`/`download` contracts already live here.
6. Add email verification + password reset; optional monitoring dashboard UI for publishers.

---

## 15. Document index (repo)
| File | Purpose |
|---|---|
| `.claude/specs/BACKEND_SPEC.md` | Backend specification |
| `.claude/plan/BACKEND_SPEC.md` | Implementation plan |
| `PROJECT_END_TO_END.md` | **This document** |
| `backend/README.md` | Backend quickstart |
| `print_1phase.pdf` | Original SRS (Phase I) |

**Status: the marketplace backend, web frontend, and cloud GPU inference are fully built, deployed, and verified end-to-end. The remaining work is optional infrastructure (R2, plan upgrade) and the out-of-scope native macOS client (MCP Server + SDK).**
