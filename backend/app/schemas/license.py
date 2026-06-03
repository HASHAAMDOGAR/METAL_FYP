"""Licensing & device schemas (spec §5.4, §5.5)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import LicenseStatus


class DeviceResponse(BaseModel):
    device_id: str
    device_name: str | None = None
    platform: str | None = None
    bound_at: datetime
    last_seen_at: datetime
    status: str


class LicenseResponse(BaseModel):
    license_key: str
    model_id: str
    status: LicenseStatus
    issued_at: datetime
    max_devices: int
    bound_device_count: int
    devices: list[DeviceResponse] = Field(default_factory=list)


class BindDeviceRequest(BaseModel):
    device_id: str = Field(min_length=3)
    device_name: str | None = None
    platform: str | None = None


class VerifyRequest(BaseModel):
    device_id: str = Field(min_length=3)
    auto_bind: bool = False


class ArtifactRef(BaseModel):
    model_id: str
    storage_key: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    version: str | None = None


class VerifyResponse(BaseModel):
    valid: bool
    reason: str | None = None
    model_artifact_ref: ArtifactRef | None = None


class DownloadResponse(BaseModel):
    download_url: str
    sha256: str | None = None
    size_bytes: int | None = None
    expires_in: int
