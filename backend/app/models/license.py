"""License document (spec §4.3) — free entitlement linking a user to a model."""
from __future__ import annotations

from datetime import datetime

import pymongo
from beanie import Document, PydanticObjectId
from pydantic import Field

from app.config import settings
from app.models.common import utcnow
from app.models.enums import LicenseStatus


class License(Document):
    license_key: str
    user_id: PydanticObjectId
    model_id: PydanticObjectId
    status: LicenseStatus = LicenseStatus.active
    issued_at: datetime = Field(default_factory=utcnow)
    max_devices: int = Field(default_factory=lambda: settings.max_devices_default)
    bound_device_count: int = 0
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "licenses"
        indexes = [
            pymongo.IndexModel("license_key", unique=True),
            pymongo.IndexModel("model_id"),
            pymongo.IndexModel(
                [("user_id", pymongo.ASCENDING), ("model_id", pymongo.ASCENDING)],
                unique=True,
                name="uniq_user_model_license",
            ),
        ]
