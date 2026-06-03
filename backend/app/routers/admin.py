"""Admin model moderation (spec §5.3)."""
from __future__ import annotations

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends

from app import errors
from app.deps import require_roles
from app.models.common import utcnow
from app.models.enums import ModelStatus, Role
from app.models.model import ModelDoc
from app.models.user import User
from app.schemas.model import ModelDetail, RejectRequest, to_detail

router = APIRouter(prefix="/admin", tags=["admin"])

admin_guard = require_roles(Role.admin)


async def _get_model(model_id: str) -> ModelDoc:
    try:
        oid = PydanticObjectId(model_id)
    except Exception:
        raise errors.not_found("Model not found", code="model_not_found")
    model = await ModelDoc.get(oid)
    if model is None:
        raise errors.not_found("Model not found", code="model_not_found")
    return model


@router.get("/models/pending", response_model=list[ModelDetail])
async def list_pending(_: User = Depends(admin_guard)) -> list[ModelDetail]:
    docs = await ModelDoc.find(ModelDoc.status == ModelStatus.pending_review).to_list()
    return [to_detail(d) for d in docs]


@router.post("/models/{model_id}/approve", response_model=ModelDetail)
async def approve(model_id: str, _: User = Depends(admin_guard)) -> ModelDetail:
    model = await _get_model(model_id)
    if model.status != ModelStatus.pending_review:
        raise errors.conflict(
            f"Only pending models can be approved (status={model.status.value})",
            code="bad_status",
        )
    model.status = ModelStatus.approved
    model.rejection_reason = None
    model.updated_at = utcnow()
    await model.save()
    return to_detail(model)


@router.post("/models/{model_id}/reject", response_model=ModelDetail)
async def reject(
    model_id: str, body: RejectRequest, _: User = Depends(admin_guard)
) -> ModelDetail:
    model = await _get_model(model_id)
    if model.status != ModelStatus.pending_review:
        raise errors.conflict(
            f"Only pending models can be rejected (status={model.status.value})",
            code="bad_status",
        )
    model.status = ModelStatus.rejected
    model.rejection_reason = body.reason
    model.updated_at = utcnow()
    await model.save()
    return to_detail(model)
