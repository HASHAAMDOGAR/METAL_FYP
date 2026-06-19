"""Cloud Models — hosted catalog + chat, served on the managed GPU cloud.

Listing is public (so the catalog page loads); chat requires a signed-in user,
consistent with the rest of the inference surface.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.models.user import User
from app.schemas.cloud_models import CloudChatRequest, CloudChatResponse, CloudModel
from app.services import cloud_models_service

router = APIRouter(prefix="/cloud-models", tags=["cloud-models"])


@router.get("", response_model=list[CloudModel])
async def list_cloud_models() -> list[CloudModel]:
    models = await cloud_models_service.list_models()
    return [CloudModel(**m) for m in models]


@router.post("/chat", response_model=CloudChatResponse)
async def cloud_models_chat(
    body: CloudChatRequest, _user: User = Depends(get_current_user)
) -> CloudChatResponse:
    messages = [m.model_dump() for m in body.messages]
    result = await cloud_models_service.chat(
        body.model, messages, body.max_tokens, body.temperature
    )
    return CloudChatResponse(**result)
