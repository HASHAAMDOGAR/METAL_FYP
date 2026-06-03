"""Deploy the FastAPI backend on Modal (fire-and-forget).

    modal deploy app/modal_deploy.py

Produces:
  * ``api``            — the whole FastAPI app as one web service.
  * ``api_<group>``    — each API group (auth, catalog, publisher, …) as its
                         own independent web service.

Every service:
  * runs the FastAPI ASGI app on Modal,
  * autoscales up to ``max_containers`` and scales to zero when idle
    (``min_containers=0``) — fire-and-forget,
  * handles many concurrent requests per container (``@modal.concurrent``),
  * reads configuration from the ``metal-backend-config`` Modal Secret.

NOTE: a deployed (cloud) service needs a cloud-reachable MongoDB URI and,
for multi-container correctness, R2 storage — set both in the Modal Secret.
"""
from __future__ import annotations

import os

import modal

# Per-API services multiply web-function usage (1 per group). Modal's plan caps
# total web functions per workspace, so they are OFF by default. Enable with
# DEPLOY_PER_API=1 once the workspace plan allows the extra web functions.
DEPLOY_PER_API = os.environ.get("DEPLOY_PER_API") == "1"

# Autoscaling caps ("max container").
APP_MAX_CONTAINERS = 10      # umbrella full-app service
GROUP_MAX_CONTAINERS = 5     # each per-API-group service
CONCURRENT_INPUTS = 100      # requests handled concurrently per container

# Image: backend deps + the local `app` package.
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_requirements("requirements.txt")
    .add_local_python_source("app")
)

# Runtime configuration (Mongo URI, JWT secret, R2, etc.).
config = modal.Secret.from_name("metal-backend-config")

modal_app = modal.App("metal-marketplace-api")

# API groups that each get their own service. A subset can be selected via the
# PER_API_GROUPS env var (comma-separated) to fit within the workspace's
# web-function quota.
ALL_API_GROUPS = [
    "auth",
    "users",
    "catalog",
    "publisher",
    "admin",
    "licenses",
    "downloads",
    "inference",
    "telemetry",
]
_selected = os.environ.get("PER_API_GROUPS")
API_GROUPS = [g.strip() for g in _selected.split(",")] if _selected else ALL_API_GROUPS


# --------------------------------------------------------------------------
# Umbrella service — the entire FastAPI app.
# --------------------------------------------------------------------------
@modal_app.function(
    image=image,
    secrets=[config],
    max_containers=APP_MAX_CONTAINERS,
    min_containers=0,
    name="api",
)
@modal.concurrent(max_inputs=CONCURRENT_INPUTS)
@modal.asgi_app()
def api():
    from app.main import create_app

    return create_app()


# --------------------------------------------------------------------------
# One service per API group.
# --------------------------------------------------------------------------
def _register_group(group: str):
    def _factory():
        from app.main import create_app

        return create_app(include=[group])

    _factory.__name__ = f"api_{group}"
    # serialized=True allows registering these dynamically-built services
    # (Modal otherwise requires functions defined at global scope).
    return modal_app.function(
        image=image,
        secrets=[config],
        max_containers=GROUP_MAX_CONTAINERS,
        min_containers=0,
        name=f"api_{group}",
        serialized=True,
    )(modal.concurrent(max_inputs=CONCURRENT_INPUTS)(modal.asgi_app()(_factory)))


if DEPLOY_PER_API:
    for _group in API_GROUPS:
        globals()[f"api_{_group}"] = _register_group(_group)
