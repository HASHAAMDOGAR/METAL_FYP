"""Publisher / model management (spec §5.3, §9.3)."""
from __future__ import annotations

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends
from pymongo.errors import DuplicateKeyError

from app import errors
from app.deps import require_roles
from app.models.common import utcnow
from app.models.enums import FileFormat, ModelStatus, Role
from app.models.model import CloudInference, ModelDoc
from app.models.user import User
from app.schemas.model import (
    CreateModelRequest,
    FinalizeArtifactRequest,
    ModelDetail,
    ModelListItem,
    PresignedUploadResponse,
    UpdateModelRequest,
    to_detail,
    to_list_item,
)
from app.services import reports, storage
from app.services.storage import artifact_key
from app.utils import slugify, unique_suffix

router = APIRouter(prefix="/publisher", tags=["publisher"])

publisher_guard = require_roles(Role.model_developer)


async def _owned_model(model_id: str, user: User) -> ModelDoc:
    try:
        oid = PydanticObjectId(model_id)
    except Exception:
        raise errors.not_found("Model not found", code="model_not_found")
    model = await ModelDoc.get(oid)
    if model is None or model.publisher_id != user.id:
        raise errors.not_found("Model not found", code="model_not_found")
    return model


@router.get("/models", response_model=list[ModelListItem])
async def list_my_models(user: User = Depends(publisher_guard)) -> list[ModelListItem]:
    docs = await ModelDoc.find(ModelDoc.publisher_id == user.id).to_list()
    return [to_list_item(d) for d in docs]


@router.post("/models", response_model=ModelDetail, status_code=201)
async def create_model(
    body: CreateModelRequest, user: User = Depends(publisher_guard)
) -> ModelDetail:
    # Format allow-list — only GGUF is supported (UC-05/06 alt course).
    if body.file_format != FileFormat.gguf:
        raise errors.unsupported_media(
            f"Unsupported file_format '{body.file_format}'; only 'gguf' is allowed"
        )

    slug = f"{slugify(body.name)}-{unique_suffix()}"
    cloud = CloudInference()
    if body.cloud_inference is not None:
        cloud.enabled = body.cloud_inference.enabled
        cloud.served_model_ref = body.cloud_inference.served_model_ref

    model = ModelDoc(
        slug=slug,
        name=body.name,
        publisher_id=user.id,
        description=body.description,
        architecture=body.architecture,
        quantization=body.quantization,
        file_format=body.file_format,
        param_count_b=body.param_count_b,
        context_length=body.context_length,
        min_ram_gb=body.min_ram_gb,
        tags=body.tags,
        use_cases=body.use_cases,
        cloud_inference=cloud,
        status=ModelStatus.draft,
    )
    try:
        await model.insert()
    except DuplicateKeyError:
        raise errors.conflict("Slug collision, retry", code="slug_conflict")
    return to_detail(model)


@router.patch("/models/{model_id}", response_model=ModelDetail)
async def update_model(
    model_id: str, body: UpdateModelRequest, user: User = Depends(publisher_guard)
) -> ModelDetail:
    model = await _owned_model(model_id, user)
    data = body.model_dump(exclude_unset=True)
    cloud = data.pop("cloud_inference", None)
    for field, value in data.items():
        setattr(model, field, value)
    if cloud is not None:
        model.cloud_inference.enabled = cloud.get("enabled", model.cloud_inference.enabled)
        if "served_model_ref" in cloud:
            model.cloud_inference.served_model_ref = cloud["served_model_ref"]
    # Edits send an approved/rejected model back to review.
    if model.status in (ModelStatus.approved, ModelStatus.rejected):
        model.status = ModelStatus.pending_review
    model.updated_at = utcnow()
    await model.save()
    return to_detail(model)


@router.post("/models/{model_id}/artifact", response_model=PresignedUploadResponse)
async def get_artifact_upload_url(
    model_id: str, user: User = Depends(publisher_guard)
) -> PresignedUploadResponse:
    model = await _owned_model(model_id, user)
    key = artifact_key(str(model.id))
    url = storage.presigned_put(key)
    model.artifact.storage_key = key
    model.updated_at = utcnow()
    await model.save()
    from app.config import settings

    return PresignedUploadResponse(
        upload_url=url, storage_key=key, expires_in=settings.upload_url_ttl
    )


@router.post("/models/{model_id}/artifact/finalize", response_model=ModelDetail)
async def finalize_artifact(
    model_id: str,
    body: FinalizeArtifactRequest,
    user: User = Depends(publisher_guard),
) -> ModelDetail:
    model = await _owned_model(model_id, user)
    if not model.artifact.storage_key:
        raise errors.bad_request("Request an upload URL first", code="no_upload")
    model.artifact.size_bytes = body.size_bytes
    model.artifact.sha256 = body.sha256
    model.artifact.version = body.version
    model.updated_at = utcnow()
    await model.save()
    return to_detail(model)


@router.post("/models/{model_id}/submit", response_model=ModelDetail)
async def submit_model(
    model_id: str, user: User = Depends(publisher_guard)
) -> ModelDetail:
    model = await _owned_model(model_id, user)
    if not model.artifact.storage_key or not model.artifact.sha256:
        raise errors.bad_request(
            "Upload and finalize the artifact before submitting", code="artifact_missing"
        )
    if model.status not in (ModelStatus.draft, ModelStatus.rejected):
        raise errors.conflict(
            f"Cannot submit a model in status '{model.status.value}'", code="bad_status"
        )
    model.status = ModelStatus.pending_review
    model.rejection_reason = None
    model.updated_at = utcnow()
    await model.save()
    return to_detail(model)


@router.delete("/models/{model_id}", status_code=204, response_model=None)
async def archive_model(model_id: str, user: User = Depends(publisher_guard)) -> None:
    model = await _owned_model(model_id, user)
    model.status = ModelStatus.archived
    model.updated_at = utcnow()
    await model.save()


@router.get("/models/{model_id}/report")
async def usage_report(model_id: str, user: User = Depends(publisher_guard)) -> dict:
    model = await _owned_model(model_id, user)
    return await reports.model_usage_report(model)
