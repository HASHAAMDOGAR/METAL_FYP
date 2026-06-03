"""Model catalog document (spec §4.2)."""
from __future__ import annotations

from datetime import datetime

import pymongo
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field

from app.models.common import utcnow
from app.models.enums import Architecture, FileFormat, ModelStatus, Quantization


class Artifact(BaseModel):
    storage_key: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    version: str = "1.0.0"


class Metrics(BaseModel):
    tokens_per_sec_m2: float | None = None
    downloads: int = 0
    rating_avg: float = 0.0
    rating_count: int = 0


class CloudInference(BaseModel):
    enabled: bool = True
    modal_app: str = "metal-llm-fallback"
    modal_function: str = "generate"
    served_model_ref: str | None = None


class ModelDoc(Document):
    slug: str
    name: str
    publisher_id: PydanticObjectId
    description: str = ""
    architecture: Architecture = Architecture.other
    quantization: Quantization | None = None
    file_format: FileFormat = FileFormat.gguf
    param_count_b: float | None = None
    context_length: int | None = None
    min_ram_gb: int | None = None
    tags: list[str] = Field(default_factory=list)
    use_cases: list[str] = Field(default_factory=list)
    license_type: str = "free"
    price: int = 0
    status: ModelStatus = ModelStatus.draft
    rejection_reason: str | None = None
    artifact: Artifact = Field(default_factory=Artifact)
    metrics: Metrics = Field(default_factory=Metrics)
    cloud_inference: CloudInference = Field(default_factory=CloudInference)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "models"
        indexes = [
            pymongo.IndexModel("slug", unique=True),
            pymongo.IndexModel("publisher_id"),
            pymongo.IndexModel("architecture"),
            pymongo.IndexModel("tags"),
            pymongo.IndexModel("status"),
            pymongo.IndexModel([("metrics.rating_avg", pymongo.DESCENDING)]),
            pymongo.IndexModel([("metrics.downloads", pymongo.DESCENDING)]),
            pymongo.IndexModel(
                [
                    ("name", pymongo.TEXT),
                    ("description", pymongo.TEXT),
                    ("tags", pymongo.TEXT),
                ],
                name="model_text_search",
            ),
        ]
