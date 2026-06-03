"""Telemetry ingestion schemas (spec §5.7)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import EventType, InferencePath


class UsageEventInput(BaseModel):
    model_id: str
    device_id: str | None = None
    event_type: EventType
    path: InferencePath | None = None
    tokens_generated: int | None = None
    tokens_per_sec: float | None = None
    latency_ms: int | None = None


class TelemetryBatch(BaseModel):
    events: list[UsageEventInput] = Field(min_length=1, max_length=500)


class IngestResponse(BaseModel):
    ingested: int
