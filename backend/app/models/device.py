"""Device binding document (spec §4.4)."""
from __future__ import annotations

from datetime import datetime

import pymongo
from beanie import Document, PydanticObjectId
from pydantic import Field

from app.models.common import utcnow
from app.models.enums import DeviceStatus


class Device(Document):
    license_id: PydanticObjectId
    user_id: PydanticObjectId
    device_id: str
    device_name: str | None = None
    platform: str | None = None
    bound_at: datetime = Field(default_factory=utcnow)
    last_seen_at: datetime = Field(default_factory=utcnow)
    status: DeviceStatus = DeviceStatus.active

    class Settings:
        name = "devices"
        indexes = [
            pymongo.IndexModel("device_id"),
            pymongo.IndexModel(
                [("license_id", pymongo.ASCENDING), ("device_id", pymongo.ASCENDING)],
                unique=True,
                name="uniq_license_device",
            ),
        ]
