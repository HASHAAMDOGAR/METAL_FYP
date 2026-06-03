"""Backend → Modal inference bridge (spec §7.2, §7.3)."""
from __future__ import annotations

from app import errors
from app.config import settings
from app.models.model import ModelDoc


async def _lookup_function(model: ModelDoc):
    """Resolve the deployed Modal function for a model. Raises 503 if unreachable."""
    try:
        import modal
    except ImportError:  # pragma: no cover
        raise errors.service_unavailable("Modal SDK not installed", code="modal_unavailable")

    app_name = model.cloud_inference.modal_app or settings.modal_app_name
    fn_name = model.cloud_inference.modal_function or "generate"
    try:
        # modal >=1.0: Function.from_name replaces the removed Function.lookup.
        return modal.Function.from_name(app_name, fn_name)
    except Exception as exc:  # noqa: BLE001
        raise errors.service_unavailable(
            f"Cloud inference backend unavailable: {exc}", code="modal_unavailable"
        )


def _ensure_cloud_enabled(model: ModelDoc) -> str:
    if not model.cloud_inference.enabled:
        raise errors.service_unavailable(
            "Cloud inference is disabled for this model", code="cloud_disabled"
        )
    ref = model.cloud_inference.served_model_ref
    if not ref:
        raise errors.service_unavailable(
            "No served_model_ref configured for cloud fallback", code="cloud_unconfigured"
        )
    return ref


async def cloud_generate(
    model: ModelDoc,
    prompt: str,
    max_tokens: int = 512,
    temperature: float = 0.7,
) -> dict:
    """Run a single (non-streaming) cloud inference and return token stats."""
    ref = _ensure_cloud_enabled(model)
    fn = await _lookup_function(model)
    try:
        # Async invocation so the event loop isn't blocked during inference.
        result = await fn.remote.aio(ref, prompt, max_tokens, temperature)
    except Exception as exc:  # noqa: BLE001
        raise errors.service_unavailable(
            f"Cloud inference failed: {exc}", code="inference_failed"
        )
    result["path"] = "cloud_modal"
    return result


async def cloud_generate_stream(
    model: ModelDoc,
    prompt: str,
    max_tokens: int = 512,
    temperature: float = 0.7,
):
    """Yield output chunks for SSE. Falls back to a single chunk if the Modal
    function is non-streaming."""
    result = await cloud_generate(model, prompt, max_tokens, temperature)
    yield result
