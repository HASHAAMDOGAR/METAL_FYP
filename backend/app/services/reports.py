"""Publisher usage aggregations (spec §5.7, Feature 9)."""
from __future__ import annotations

from app.models.enums import EventType
from app.models.license import License
from app.models.model import ModelDoc
from app.models.usage_event import UsageEvent


async def model_usage_report(model: ModelDoc) -> dict:
    """Aggregate downloads, inference counts and tokens/sec for one model."""
    pipeline = [
        {"$match": {"model_id": model.id}},
        {
            "$group": {
                "_id": "$event_type",
                "count": {"$sum": 1},
                "avg_tps": {"$avg": "$tokens_per_sec"},
                "total_tokens": {"$sum": "$tokens_generated"},
            }
        },
    ]
    rows = await UsageEvent.aggregate(pipeline).to_list()
    by_type = {r["_id"]: r for r in rows}

    def _stat(event: EventType, field: str, default=0):
        row = by_type.get(event.value)
        return (row or {}).get(field, default) or default

    license_count = await License.find(License.model_id == model.id).count()

    return {
        "model_id": str(model.id),
        "slug": model.slug,
        "name": model.name,
        "status": model.status.value,
        "licenses_issued": license_count,
        "downloads": int(_stat(EventType.download, "count")),
        "deployments": int(_stat(EventType.deploy, "count")),
        "inferences": int(_stat(EventType.inference, "count")),
        "total_tokens_generated": int(_stat(EventType.inference, "total_tokens")),
        "avg_tokens_per_sec": round(_stat(EventType.inference, "avg_tps", 0.0) or 0.0, 2),
        "rating_avg": model.metrics.rating_avg,
        "rating_count": model.metrics.rating_count,
    }


async def user_usage_summary(user_id, limit: int = 50) -> dict:
    """Recent usage for the current user (spec GET /me/usage)."""
    recent = (
        await UsageEvent.find(UsageEvent.user_id == user_id)
        .sort([("occurred_at", -1)])
        .limit(limit)
        .to_list()
    )
    total = await UsageEvent.find(UsageEvent.user_id == user_id).count()
    return {
        "total_events": total,
        "recent": [
            {
                "model_id": str(e.model_id),
                "event_type": e.event_type.value,
                "path": e.path.value if e.path else None,
                "tokens_generated": e.tokens_generated,
                "tokens_per_sec": e.tokens_per_sec,
                "occurred_at": e.occurred_at.isoformat(),
            }
            for e in recent
        ],
    }
