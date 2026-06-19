# METAL_FYP — Apple Metal-Powered LLM Marketplace

A two-sided platform for distributing and running Large Language Models **natively on Apple Silicon**, with a **Modal GPU cloud fallback** when local Apple Metal isn't available.

> **UCP BSCS Final Year Project — Group F25CS008**

| | Live URL |
|---|---|
| 🖥️ **Web app** (Next.js) | https://symia-cloud--metal-marketplace-web-web.modal.run |
| ☁️ **Cloud Models** | https://symia-cloud--metal-marketplace-web-web.modal.run/cloud |
| ⚙️ **API** (FastAPI) | https://symia-cloud--metal-marketplace-api-api.modal.run |
| 📚 **API docs** | https://symia-cloud--metal-marketplace-api-api.modal.run/docs |

**Demo login:** `admin@metal.dev` / `admin12345`

---

## What it does

LLM integration into native macOS apps is fragmented, ignores the Apple Metal GPU, and lacks a trusted marketplace. This project delivers:

- **Marketplace** — Model Developers publish GGUF models; App Developers discover, license, and download them.
- **Cloud Models** — a catalog of **hundreds of hosted models** on a managed GPU cloud; pick one and chat instantly in the browser, no download required. White-labeled (the upstream provider is never exposed to users).
- **Native Swift SDK** — a macOS app picks `.managedCloud` (→ Modal GPU) or `.localInfer` (→ download + run locally via **Ollama**) behind one API.
- **Cloud inference** — runs on a **Modal GPU**; the website's Playground uses this path. **No token limit** — generate as much as you want.
- **Native Apple Metal compute** — a C++/Objective-C++ Metal GEMM kernel (`metal-native/`) demonstrating on-device GPU acceleration (137× over a CPU baseline on M3).

This repository contains the **backend (FastAPI)**, the **web frontend (Next.js)**, the **Modal GPU inference app**, the **native Swift SDK**, and **native Metal compute** — all deployed/tested end-to-end. See **[docs/WHATS_NEW.md](docs/WHATS_NEW.md)** for the latest capabilities.

---

## Architecture

```
  Browser ──► Next.js frontend (Modal) ──► FastAPI backend (Modal) ──► MongoDB Atlas
                                                  │
  MCP Server / SDK (macOS) ──────────────────────┤──► Cloudflare R2 (model weights)*
   (license verify · download · cloud fallback)   ├──► Modal GPU app (cloud inference)
                                                  └──► Managed cloud-model provider**
                                                       (Cloud Models catalog + chat)

  *  R2 is optional/deferred — a local storage fallback is active.
  ** OpenAI-compatible upstream, white-labeled; configured via a secret, never exposed to users.
```

---

## Features

- 🔐 **Auth** — JWT (access + refresh with rotation), role-based access (consumer / publisher / admin)
- 🗂️ **Catalog** — browse, full-text search, filter, sort, reviews & ratings
- 📤 **Publishing** — presigned GGUF upload, admin approval workflow
- 🎫 **Licensing** — free entitlements with **device binding** + a license-verification endpoint for the MCP server
- ⬇️ **Secure downloads** — short-lived presigned URLs, license-gated, sha256-verified
- ⚡ **Cloud inference** — Modal A10G GPU fallback (+ SSE streaming), **no token limit**
- ☁️ **Cloud Models** — browse hundreds of hosted models and chat instantly in-browser; "ready to run" status is verified by probing real availability (`scripts/refresh_serverless.py`)
- 🍎 **Native Swift SDK** — `.managedCloud` (Modal GPU) **and** `.localInfer` (on-device via Ollama: downloads + runs the model locally)
- 🎨 **Modern web UI** — Next.js + Tailwind, glass-morphism design, live chat interface
- 📊 **Telemetry** — usage events and publisher reports

---

## Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI (Python 3.12), Beanie ODM |
| Database | MongoDB Atlas |
| Object storage | Cloudflare R2 (S3-compatible) — *local fallback active* |
| Cloud GPU | Modal (A10G, llama-cpp-python) |
| Cloud Models | Managed cloud-model provider (OpenAI-compatible upstream, white-labeled) |
| Frontend | Next.js 14 (App Router, TypeScript, Tailwind) |
| Native SDK | Swift (SwiftPM) — Modal cloud + local Ollama |
| Native compute | Apple Metal (C++/Objective-C++ GEMM kernel) |
| Hosting | Modal (backend, frontend, GPU app) |

---

## Repository structure

```
backend/          FastAPI app (models, routers, services), Modal deploy, tests
  app/            main, config, db, security, deps, models/, routers/, services/
                  routers/cloud_models.py + services/cloud_models_service.py (Cloud Models)
                  serverless_models.py  (verified "ready to run" allowlist)
  scripts/        seed, smoke_test, full_api_test, deep_test, refresh_serverless
  tests/          pytest suite
frontend/         Next.js app (app/ pages incl. cloud/, components/, lib/), Modal deploy
swift-sdk/        Native Swift SDK (MetalLLM): managed-cloud + local Ollama, CLI demo
metal-native/     Native Apple Metal GEMM compute (C++/Objective-C++)
docs/             WHATS_NEW.md, ARCHITECTURE_COMMUNICATION.md
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

### Swift SDK
```bash
cd swift-sdk
swift build
swift run metal-llm-cli "Q: capital of Japan?\nA:"      # cloud + local Ollama demo
```
```swift
let client = MetalLLM()
try await client.login(username: "admin@metal.dev", password: "admin12345")
let cloud = client.model(id: modelId, mode: .managedCloud)          // Modal GPU
let local = client.localModel(ollamaModel: "qwen2.5:0.5b")          // on-device via Ollama
```
Local mode requires Ollama (`brew install --cask ollama` → `ollama serve`).

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

Configuration lives in the Modal secret `metal-backend-config` (Mongo URI, JWT secret, storage, Cloud Models provider key, etc.). The live deployment runs in the `symia-cloud` Modal workspace.

To refresh the Cloud Models "ready to run" allowlist (re-probes real availability):
```bash
cd backend && python -m scripts.refresh_serverless   # regenerates app/serverless_models.py
modal deploy app/modal_deploy.py::modal_app           # redeploy
```

---

## Status

✅ **Built & deployed:** backend, frontend (redesigned UI), cloud GPU inference, **Cloud Models** (hosted catalog + in-browser chat), **native Swift SDK** (cloud + local Ollama), **native Metal compute**, all tests passing.
⏳ **Optional/pending:** Cloudflare R2 storage (local fallback active), per-API Modal services (plan-limited).
❌ **Out of scope:** the full macOS MCP daemon (Metal-via-Ollama covers local inference for the SDK today), payments (intentionally removed).

See **[PROJECT_END_TO_END.md](PROJECT_END_TO_END.md)** for the complete report.

---

## Adaptations vs. the original SRS

FastAPI (not Node/Fastify) · MongoDB (not PostgreSQL) · **Modal** cloud inference fallback · **no payments** (free models only, no Stripe/Redis) · **simplified licensing** (acquire + device binding, no purchase flow) · **Cloudflare R2** for storage.

---

_License: academic / educational use (UCP FYP F25CS008)._
