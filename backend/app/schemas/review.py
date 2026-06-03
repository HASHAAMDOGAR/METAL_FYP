"""Review schemas (spec §5.2)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateReviewRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    title: str | None = None
    body: str | None = None


class ReviewResponse(BaseModel):
    id: str
    model_id: str
    user_id: str
    rating: int
    title: str | None = None
    body: str | None = None
    created_at: datetime
