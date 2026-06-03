"""Usage telemetry document (spec §4.6)."""
from __future__ import annotations

from datetime import datetime

import pymongo
from beanie import Document, PydanticObjectId
from pydantic import Field

from app.models.common import utcnow
from app.models.enums import EventType, InferencePath


class UsageEvent(Document):
    model_id: PydanticObjectId
    user_id: PydanticObjectId
    device_id: str | None = None
    event_type: EventType
    path: InferencePath | None = None
    tokens_generated: int | None = None
    tokens_per_sec: float | None = None
    latency_ms: int | None = None
    occurred_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "usage_events"
        indexes = [
            pymongo.IndexModel("model_id"),
            pymongo.IndexModel(
                [("user_id", pymongo.ASCENDING), ("occurred_at", pymongo.DESCENDING)]
            ),
            pymongo.IndexModel("occurred_at"),
        ]
