"""Telemetry ingestion + user usage summary (spec §5.7)."""
from __future__ import annotations

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.models.usage_event import UsageEvent
from app.models.user import User
from app.schemas.telemetry import IngestResponse, TelemetryBatch
from app.services import reports

router = APIRouter(tags=["telemetry"])


@router.post("/telemetry/events", response_model=IngestResponse, status_code=201)
async def ingest_events(
    batch: TelemetryBatch, user: User = Depends(get_current_user)
) -> IngestResponse:
    docs: list[UsageEvent] = []
    for e in batch.events:
        try:
            model_oid = PydanticObjectId(e.model_id)
        except Exception:
            continue  # skip malformed ids rather than failing the whole batch
        docs.append(
            UsageEvent(
                model_id=model_oid,
                user_id=user.id,
                device_id=e.device_id,
                event_type=e.event_type,
                path=e.path,
                tokens_generated=e.tokens_generated,
                tokens_per_sec=e.tokens_per_sec,
                latency_ms=e.latency_ms,
            )
        )
    if docs:
        await UsageEvent.insert_many(docs)
    return IngestResponse(ingested=len(docs))


@router.get("/me/usage")
async def my_usage(user: User = Depends(get_current_user)) -> dict:
    return await reports.user_usage_summary(user.id)
