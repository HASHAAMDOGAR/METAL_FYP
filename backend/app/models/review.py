"""Review document (spec §4.5)."""
from __future__ import annotations

from datetime import datetime

import pymongo
from beanie import Document, PydanticObjectId
from pydantic import Field

from app.models.common import utcnow


class Review(Document):
    model_id: PydanticObjectId
    user_id: PydanticObjectId
    rating: int = Field(ge=1, le=5)
    title: str | None = None
    body: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "reviews"
        indexes = [
            pymongo.IndexModel("model_id"),
            pymongo.IndexModel(
                [("model_id", pymongo.ASCENDING), ("user_id", pymongo.ASCENDING)],
                unique=True,
                name="uniq_model_user_review",
            ),
        ]
