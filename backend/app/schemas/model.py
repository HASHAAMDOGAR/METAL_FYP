"""Model catalog & publisher schemas (spec §5.2, §5.3)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import Architecture, FileFormat, ModelStatus, Quantization
from app.models.model import Artifact, CloudInference, Metrics, ModelDoc


class ModelListItem(BaseModel):
    id: str
    slug: str
    name: str
    publisher_id: str
    architecture: Architecture
    quantization: Quantization | None = None
    param_count_b: float | None = None
    tags: list[str]
    license_type: str
    status: ModelStatus
    metrics: Metrics


class ModelDetail(ModelListItem):
    description: str
    file_format: FileFormat
    context_length: int | None = None
    min_ram_gb: int | None = None
    use_cases: list[str]
    artifact: Artifact
    cloud_inference: CloudInference


class CloudInferenceInput(BaseModel):
    enabled: bool = True
    served_model_ref: str | None = None


class CreateModelRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = ""
    architecture: Architecture
    quantization: Quantization | None = None
    file_format: FileFormat = FileFormat.gguf
    param_count_b: float | None = None
    context_length: int | None = None
    min_ram_gb: int | None = None
    tags: list[str] = Field(default_factory=list)
    use_cases: list[str] = Field(default_factory=list)
    cloud_inference: CloudInferenceInput | None = None


class UpdateModelRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    architecture: Architecture | None = None
    quantization: Quantization | None = None
    param_count_b: float | None = None
    context_length: int | None = None
    min_ram_gb: int | None = None
    tags: list[str] | None = None
    use_cases: list[str] | None = None
    cloud_inference: CloudInferenceInput | None = None


class FinalizeArtifactRequest(BaseModel):
    size_bytes: int
    sha256: str
    version: str = "1.0.0"


class RejectRequest(BaseModel):
    reason: str


class PresignedUploadResponse(BaseModel):
    upload_url: str
    storage_key: str
    expires_in: int
    method: str = "PUT"


def to_list_item(m: ModelDoc) -> ModelListItem:
    return ModelListItem(
        id=str(m.id),
        slug=m.slug,
        name=m.name,
        publisher_id=str(m.publisher_id),
        architecture=m.architecture,
        quantization=m.quantization,
        param_count_b=m.param_count_b,
        tags=m.tags,
        license_type=m.license_type,
        status=m.status,
        metrics=m.metrics,
    )


def to_detail(m: ModelDoc) -> ModelDetail:
    return ModelDetail(
        **to_list_item(m).model_dump(),
        description=m.description,
        file_format=m.file_format,
        context_length=m.context_length,
        min_ram_gb=m.min_ram_gb,
        use_cases=m.use_cases,
        artifact=m.artifact,
        cloud_inference=m.cloud_inference,
    )
