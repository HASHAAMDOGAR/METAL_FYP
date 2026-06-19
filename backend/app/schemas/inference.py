"""Cloud inference fallback schemas (spec §5.6)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import InferenceReason


class InferenceRequest(BaseModel):
    model_id: str
    prompt: str = Field(min_length=1)
    # No upper limit: use as many tokens as you want. -1 (or 0) = unlimited —
    # generate until the model emits EOS or fills its context window.
    max_tokens: int = Field(default=512, ge=-1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    device_id: str | None = None
    reason: InferenceReason


class InferenceResponse(BaseModel):
    output: str
    tokens_generated: int
    tokens_per_sec: float
    path: str = "cloud_modal"
