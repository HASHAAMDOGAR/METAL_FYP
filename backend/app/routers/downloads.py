"""Secure model artifact download (spec §5.5)."""
from __future__ import annotations

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends

from app import errors
from app.config import settings
from app.deps import get_current_user, require_license
from app.models.enums import EventType
from app.models.model import ModelDoc
from app.models.usage_event import UsageEvent
from app.models.user import User
from app.schemas.license import DownloadResponse
from app.services import storage

router = APIRouter(tags=["downloads"])


@router.get("/models/{model_id}/download", response_model=DownloadResponse)
async def download_model(
    model_id: str,
    device_id: str | None = None,
    user: User = Depends(get_current_user),
) -> DownloadResponse:
    try:
        oid = PydanticObjectId(model_id)
    except Exception:
        raise errors.not_found("Model not found", code="model_not_found")
    model = await ModelDoc.get(oid)
    if model is None:
        raise errors.not_found("Model not found", code="model_not_found")

    # Authorization: caller must hold an active license (spec §5.5, NFR-S4).
    await require_license(model.id, user)

    if not model.artifact.storage_key:
        raise errors.not_found("Model artifact not available", code="artifact_missing")

    url = storage.presigned_get(model.artifact.storage_key)

    # Log a download usage event and bump the counter.
    await UsageEvent(
        model_id=model.id,
        user_id=user.id,
        device_id=device_id,
        event_type=EventType.download,
    ).insert()
    model.metrics.downloads += 1
    await model.save()

    return DownloadResponse(
        download_url=url,
        sha256=model.artifact.sha256,
        size_bytes=model.artifact.size_bytes,
        expires_in=settings.download_url_ttl,
    )
