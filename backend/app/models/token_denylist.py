"""Refresh-token denylist (spec §8.1) — replaces Redis with a TTL collection."""
from __future__ import annotations

from datetime import datetime

import pymongo
from beanie import Document
from pydantic import Field

from app.models.common import utcnow


class TokenDenylist(Document):
    jti: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "token_denylist"
        indexes = [
            pymongo.IndexModel("jti", unique=True),
            # TTL index: Mongo auto-removes documents after expires_at.
            pymongo.IndexModel("expires_at", expireAfterSeconds=0),
        ]
