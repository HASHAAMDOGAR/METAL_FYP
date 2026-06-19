"""Managed cloud-model bridge.

Proxies a catalog of hosted models and chat completions through an upstream
OpenAI-compatible provider. The upstream provider is an implementation detail:
the marketplace presents these as its own "Cloud Models", so this module never
leaks the provider's identity to API clients (see ``_sanitize``).
"""
from __future__ import annotations

import re

import httpx

from app import errors
from app.config import settings
from app.serverless_models import RUNNABLE

# Inference can be slow for large models; allow a long read timeout.
_TIMEOUT = httpx.Timeout(600.0, connect=30.0)

# Model types that can do text chat at all.
_CHATTABLE = {"chat", "language", "code"}

# Verified runnable models (probed for real availability). The provider catalog
# has no reliable serverless flag, so this allowlist is the source of truth for
# the "ready to run" badge. Refresh with scripts/refresh_serverless.py.
_RUNNABLE: set[str] = set(RUNNABLE)

# Strip any mention of the upstream provider from surfaced text (white-label).
_PROVIDER_RE = re.compile(r"together\s*computer|together\.?ai|together", re.IGNORECASE)


def _sanitize(text: str) -> str:
    return _PROVIDER_RE.sub("the cloud provider", text or "")


def _clean_org(org: str | None) -> str | None:
    """Never surface the upstream provider as a model's organization."""
    if org and "together" in org.lower():
        return "Community"
    return org


def _headers() -> dict:
    key = settings.together_api_key
    if not key:
        raise errors.service_unavailable(
            "Cloud model provider is not configured", code="provider_unconfigured"
        )
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


async def list_models() -> list[dict]:
    """Return the full hosted-model catalog, normalized and white-labeled."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.get(
                f"{settings.together_base_url}/models", headers=_headers()
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:  # noqa: BLE001
            raise errors.service_unavailable(
                f"Cloud model catalog unavailable: {_sanitize(str(exc))}",
                code="provider_unavailable",
            )

    raw = resp.json()
    items = raw if isinstance(raw, list) else raw.get("data", [])
    out: list[dict] = []
    for m in items:
        mid = m.get("id")
        if not mid:
            continue
        mtype = (m.get("type") or "").lower()
        org = m.get("organization") or (mid.split("/")[0] if "/" in mid else None)
        # "Ready to run" only if the model is on the verified-runnable allowlist
        # (probed for real availability). Catalog metadata can't be trusted for
        # this — most priced models still reject with "non-serverless".
        chattable = mid in _RUNNABLE if _RUNNABLE else mtype in _CHATTABLE
        out.append(
            {
                "id": mid,
                "name": _sanitize(m.get("display_name") or mid.split("/")[-1]),
                "organization": _clean_org(org),
                "type": mtype or None,
                "context_length": m.get("context_length"),
                "chattable": chattable,
            }
        )
    # Instantly-runnable models first, then alphabetical.
    out.sort(key=lambda x: (not x["chattable"], x["name"].lower()))
    return out


async def chat(
    model: str,
    messages: list[dict],
    max_tokens: int | None,
    temperature: float,
) -> dict:
    """Run a chat completion against the hosted model and return the reply."""
    payload: dict = {"model": model, "messages": messages, "temperature": temperature}
    # max_tokens <= 0 (or omitted) means "no limit" — let the model decide.
    if max_tokens and max_tokens > 0:
        payload["max_tokens"] = max_tokens

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.post(
                f"{settings.together_base_url}/chat/completions",
                headers=_headers(),
                json=payload,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                body = exc.response.json()
                detail = (body.get("error") or {}).get("message") or str(body)
            except Exception:  # noqa: BLE001
                detail = exc.response.text
            if "non-serverless" in detail.lower():
                raise errors.service_unavailable(
                    "This model requires a dedicated deployment and isn't available "
                    "for instant use. Pick a model marked as ready-to-run.",
                    code="model_not_serverless",
                )
            raise errors.service_unavailable(
                f"Cloud inference failed: {_sanitize(detail)}",
                code="inference_failed",
            )
        except httpx.HTTPError as exc:  # noqa: BLE001
            raise errors.service_unavailable(
                f"Cloud inference failed: {_sanitize(str(exc))}",
                code="inference_failed",
            )

    data = resp.json()
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content") or ""
    finish = choice.get("finish_reason")

    # Reasoning models (e.g. GPT-OSS, GLM, Qwen3-thinking) emit their chain of
    # thought in `reasoning` and the answer in `content`. With a small token
    # budget the whole budget goes to reasoning and `content` comes back empty
    # (finish_reason="length"). Surface something useful instead of a blank reply.
    if not content:
        reasoning = (message.get("reasoning") or "").strip()
        if reasoning:
            content = reasoning
        elif finish == "length":
            content = (
                "(The model reached the token limit before finishing. "
                "Increase Max tokens and try again.)"
            )

    usage = data.get("usage") or {}
    return {
        "output": content,
        "model": model,
        "tokens_generated": int(usage.get("completion_tokens") or 0),
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "path": "cloud_managed",
    }
