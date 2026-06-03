"""Common helpers for documents."""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Timezone-aware UTC now (stored as naive UTC by Mongo)."""
    return datetime.now(timezone.utc)
