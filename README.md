# METAL_FYP — Apple Metal-Powered LLM Marketplace

A two-sided platform for distributing and running Large Language Models **natively on Apple Silicon**, with a **Modal GPU cloud fallback** when local Apple Metal isn't available.

> **UCP BSCS Final Year Project — Group F25CS008**

| | Live URL |
|---|---|
| 🖥️ **Web app** (Next.js) | https://hashaamdogar--metal-marketplace-web-web.modal.run |
| ⚙️ **API** (FastAPI) | https://hashaamdogar--metal-marketplace-api-api.modal.run |
| 📚 **API docs** | https://hashaamdogar--metal-marketplace-api-api.modal.run/docs |

**Demo login:** `admin@metal.dev` / `admin12345`

---

## What it does

LLM integration into native macOS apps is fragmented, ignores the Apple Metal GPU, and lacks a trusted marketplace. This project delivers:

- **Marketplace** — Model Developers publish GGUF models; App Developers discover, license, and download them.
- **MCP Server** *(native macOS client — out of scope here)* — loads licensed models and runs Metal-accelerated inference, verifying licenses against this backend.
- **Cloud fallback** — when local Metal is unavailable, inference is routed to a **Modal GPU**.

This repository contains the **backend (FastAPI)**, the **web frontend (Next.js)**, and the **Modal GPU inference app** — all deployed and tested end-to-end.

---

## Architecture

```
  Browser ──► Next.js frontend (Modal) ──► FastAPI backend (Modal) ──► MongoDB Atlas
                                                  │
  MCP Server / SDK (macOS) ──────────────────────┤──► Cloudflare R2 (model weights)*
   (license verify · download · cloud fallback)   └──► Modal GPU app (cloud inference)

  * R2 is optional/deferred — a local storage fallback is active.
```

---

## Features

- 🔐 **Auth** — JWT (access + refresh with rotation), role-based access (consumer / publisher / admin)
- 🗂️ **Catalog** — browse, full-text search, filter, sort, reviews & ratings
- 📤 **Publishing** — presigned GGUF upload, admin approval workflow
- 🎫 **Licensing** — free entitlements with **device binding** + a license-verification endpoint for the MCP server
- ⬇️ **Secure downloads** — short-lived presigned URLs, license-gated, sha256-verified
- ⚡ **Cloud inference** — Modal A10G GPU fallback (+ SSE streaming)
- 📊 **Telemetry** — usage events and publisher reports

---

## Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI (Python 3.12), Beanie ODM |
| Database | MongoDB Atlas |
| Object storage | Cloudflare R2 (S3-compatible) — *local fallback active* |
| Cloud GPU | Modal (A10G, llama-cpp-python) |
| Frontend | Next.js 14 (App Router, TypeScript, Tailwind) |
| Hosting | Modal (backend, frontend, GPU app) |

---

## Repository structure

```
backend/          FastAPI app (models, routers, services), Modal deploy, tests
  app/            main, config, db, security, deps, models/, routers/, services/
  scripts/        seed, smoke_test, full_api_test, deep_test
  tests/          pytest suite
frontend/         Next.js app (app/ pages, components/, lib/), Modal deploy
.claude/specs/    Backend specification
.claude/plan/     Implementation plan
PROJECT_END_TO_END.md   Full end-to-end project report
print_1phase.pdf  Original SRS (Phase I)
```

---

## Getting started (local)

### Backend
```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # set MONGODB_URI (local mongod or Atlas)
uvicorn app.main:app --reload # http://localhost:8000/docs
python -m scripts.seed        # seed admin + sample models
```

### Frontend
```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev   # http://localhost:3000
```

---

## Testing

```bash
cd backend && source .venv/bin/activate
pytest                            # unit tests        (10/10)
python -m scripts.full_api_test   # every endpoint    (77/77, local)
python -m scripts.deep_test       # live cloud E2E    (62/62)
```

| Suite | Scope | Result |
|---|---|---|
| Unit | services & guards | ✅ 10/10 |
| Full API | every endpoint, happy + error | ✅ 77/77 |
| Deep (live) | frontend + API + real GPU inference | ✅ 62/62 |

---

## Deployment (Modal)

```bash
modal deploy backend/app/modal_app.py                       # GPU inference app
cd backend && modal deploy app/modal_deploy.py::modal_app   # FastAPI backend
cd frontend && modal deploy modal_app.py::app               # Next.js frontend
```

Configuration lives in the Modal secret `metal-backend-config` (Mongo URI, JWT secret, storage, etc.).

---

## Status

✅ **Built & deployed:** backend, frontend, cloud GPU inference, all tests passing.
⏳ **Optional/pending:** Cloudflare R2 storage (local fallback active), per-API Modal services (plan-limited).
❌ **Out of scope (native client):** macOS MCP Server + Swift SDK, payments (intentionally removed).

See **[PROJECT_END_TO_END.md](PROJECT_END_TO_END.md)** for the complete report.

---

## Adaptations vs. the original SRS

FastAPI (not Node/Fastify) · MongoDB (not PostgreSQL) · **Modal** cloud inference fallback · **no payments** (free models only, no Stripe/Redis) · **simplified licensing** (acquire + device binding, no purchase flow) · **Cloudflare R2** for storage.

---

_License: academic / educational use (UCP FYP F25CS008)._
