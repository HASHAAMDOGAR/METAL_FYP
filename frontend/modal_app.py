"""Deploy the Next.js frontend as a container on Modal (fire-and-forget).

    cd frontend && modal deploy modal_app.py::app

Builds the Next.js production bundle inside the image (with the backend API URL
baked in at build time, since NEXT_PUBLIC_* is inlined), then serves it with
`next start` behind Modal's web_server proxy.
"""
from __future__ import annotations

import subprocess

import modal

# Backend (umbrella) API URL — inlined into the client bundle at build time.
API_URL = "https://symia-cloud--metal-marketplace-api-api.modal.run"

image = (
    modal.Image.from_registry("node:20-slim", add_python="3.11")
    .env({"NEXT_PUBLIC_API_URL": API_URL, "NEXT_TELEMETRY_DISABLED": "1"})
    .workdir("/app")
    .add_local_dir(
        ".",
        "/app",
        copy=True,
        ignore=["node_modules", ".next", "modal_app.py", ".git"],
    )
    .run_commands("cd /app && npm install && npm run build")
)

app = modal.App("metal-marketplace-web")


@app.function(
    image=image,
    max_containers=3,
    min_containers=0,
    scaledown_window=300,
)
@modal.concurrent(max_inputs=100)
@modal.web_server(3000, startup_timeout=180)
def web():
    subprocess.Popen(
        "cd /app && npx next start -p 3000 -H 0.0.0.0",
        shell=True,
    )
