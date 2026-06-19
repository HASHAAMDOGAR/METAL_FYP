"""Modal cloud-inference fallback app (spec §7.1).

Deployed independently from the FastAPI backend:

    modal deploy app/modal_app.py

The FastAPI backend invokes `generate` via `modal.Function.lookup` only when a
client reports the local Apple-Silicon Metal path is unavailable. Only free,
redistributable models are served here.
"""
from __future__ import annotations

import modal

app = modal.App("metal-llm-fallback")

image = (
    modal.Image.debian_slim()
    .pip_install("llama-cpp-python==0.3.5", "huggingface_hub==0.27.0")
)

# Map of served_model_ref -> (HuggingFace repo, filename) for free GGUF models.
MODEL_REGISTRY: dict[str, tuple[str, str]] = {
    "llama-3-8b-instruct": (
        "bartowski/Meta-Llama-3-8B-Instruct-GGUF",
        "Meta-Llama-3-8B-Instruct-Q4_K_M.gguf",
    ),
    "mistral-7b-instruct": (
        "bartowski/Mistral-7B-Instruct-v0.3-GGUF",
        "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf",
    ),
    "qwen2.5-7b-instruct": (
        "bartowski/Qwen2.5-7B-Instruct-GGUF",
        "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
    ),
}

_cache = modal.Volume.from_name("metal-llm-models", create_if_missing=True)
CACHE_DIR = "/models"


@app.function(image=image, gpu="A10G", timeout=600, volumes={CACHE_DIR: _cache})
def generate(
    model_ref: str,
    prompt: str,
    max_tokens: int = 512,
    temperature: float = 0.7,
) -> dict:
    """Load (cached) model by ref, run inference, return tokens + stats."""
    import time

    from huggingface_hub import hf_hub_download
    from llama_cpp import Llama

    if model_ref not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model_ref '{model_ref}'")

    repo, filename = MODEL_REGISTRY[model_ref]
    path = hf_hub_download(repo_id=repo, filename=filename, cache_dir=CACHE_DIR)
    _cache.commit()

    # Large context so users aren't limited to a small completion length.
    llm = Llama(model_path=path, n_gpu_layers=-1, n_ctx=8192, verbose=False)

    # max_tokens <= 0 means "no limit" — generate until EOS or context is full.
    mt = max_tokens if max_tokens and max_tokens > 0 else -1

    start = time.time()
    out = llm.create_completion(prompt, max_tokens=mt, temperature=temperature)
    elapsed = max(time.time() - start, 1e-6)

    text = out["choices"][0]["text"]
    n = out.get("usage", {}).get("completion_tokens", len(text.split()))
    return {
        "output": text,
        "tokens_generated": int(n),
        "tokens_per_sec": round(n / elapsed, 2),
    }
