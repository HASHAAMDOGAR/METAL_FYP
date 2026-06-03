"""Cloud inference fallback endpoints (spec §5.6, §7.3)."""
from __future__ import annotations

import json

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app import errors
from app.errors import APIError
from app.deps import get_current_user, require_license
from app.models.enums import EventType, InferencePath
from app.models.model import ModelDoc
from app.models.usage_event import UsageEvent
from app.models.user import User
from app.schemas.inference import InferenceRequest, InferenceResponse
from app.services import inference_service

router = APIRouter(tags=["inference"])


async def _resolve_licensed_model(body: InferenceRequest, user: User) -> ModelDoc:
    try:
        oid = PydanticObjectId(body.model_id)
    except Exception:
        raise errors.not_found("Model not found", code="model_not_found")
    model = await ModelDoc.get(oid)
    if model is None:
        raise errors.not_found("Model not found", code="model_not_found")
    await require_license(model.id, user)  # active license required
    return model


async def _log_inference(model, user, body, result) -> None:
    await UsageEvent(
        model_id=model.id,
        user_id=user.id,
        device_id=body.device_id,
        event_type=EventType.inference,
        path=InferencePath.cloud_modal,
        tokens_generated=result.get("tokens_generated"),
        tokens_per_sec=result.get("tokens_per_sec"),
    ).insert()


@router.post("/inference", response_model=InferenceResponse)
async def cloud_inference(
    body: InferenceRequest, user: User = Depends(get_current_user)
) -> InferenceResponse:
    model = await _resolve_licensed_model(body, user)
    result = await inference_service.cloud_generate(
        model, body.prompt, body.max_tokens, body.temperature
    )
    await _log_inference(model, user, body, result)
    return InferenceResponse(**result)


@router.post("/inference/stream")
async def cloud_inference_stream(
    body: InferenceRequest, user: User = Depends(get_current_user)
) -> StreamingResponse:
    model = await _resolve_licensed_model(body, user)

    async def event_gen():
        last = None
        try:
            async for chunk in inference_service.cloud_generate_stream(
                model, body.prompt, body.max_tokens, body.temperature
            ):
                last = chunk
                yield f"data: {json.dumps(chunk)}\n\n"
        except APIError as exc:
            # Stream already started (200) — surface the failure as an SSE event
            # rather than crashing the connection.
            yield f"data: {json.dumps({'error': {'code': exc.code, 'message': exc.message}})}\n\n"
            yield "data: [DONE]\n\n"
            return
        if last is not None:
            await _log_inference(model, user, body, last)
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
