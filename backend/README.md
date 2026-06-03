# Metal LLM Marketplace — Backend

FastAPI + MongoDB (Beanie) + Cloudflare R2 + Modal. Implements the backend spec
(`.claude/specs/BACKEND_SPEC.md`): free LLM marketplace, simplified licensing with
device binding, secure R2 downloads, and Modal cloud-inference fallback.

## Quick start

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill in Mongo / R2 / Modal values

# run the API (needs a running MongoDB)
uvicorn app.main:app --reload   # docs at http://localhost:8000/docs

# seed sample data
python -m scripts.seed

# deploy the cloud-inference fallback (separate, needs a Modal account)
modal deploy app/modal_app.py
```

## Tests

```bash
pytest                          # in-memory Mongo (mongomock-motor); R2 + Modal mocked
```

## Layout

| Path | Purpose |
|---|---|
| `app/main.py` | App factory, router mounts, `/healthz`, `/readyz` |
| `app/config.py` | Settings from `.env` |
| `app/db.py` | Beanie/Motor init + indexes |
| `app/security.py`, `app/deps.py` | JWT, password hashing, auth/role/license guards |
| `app/models/` | Beanie documents (users, models, licenses, devices, reviews, usage_events) |
| `app/schemas/` | Pydantic request/response models |
| `app/routers/` | auth, users, catalog, publisher, admin, licenses, downloads, inference, telemetry |
| `app/services/` | `storage` (R2), `licensing`, `inference_service` (Modal), `reports` |
| `app/modal_app.py` | Modal GPU app — deployed separately |
| `scripts/seed.py` | Seed admin + 3 approved models |

## Key flows

- **Acquire → download → deploy:** `POST /v1/models/{id}/acquire` → `POST /v1/licenses/{key}/devices` → `POST /v1/licenses/{key}/verify` → `GET /v1/models/{id}/download`.
- **Cloud fallback:** `POST /v1/inference` with `reason=no_metal_device` routes to Modal.
- **Publish:** `POST /v1/publisher/models` → `.../artifact` (presigned PUT) → `.../artifact/finalize` → `.../submit` → admin `approve`.
