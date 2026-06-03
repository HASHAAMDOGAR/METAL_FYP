"""Licensing & device-binding logic (spec §5.4, §9.1, NFR-S4)."""
from __future__ import annotations

from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from app import errors
from app.models.common import utcnow
from app.models.device import Device
from app.models.enums import DeviceStatus, LicenseStatus, ModelStatus
from app.models.license import License
from app.models.model import ModelDoc
from app.security import gen_license_key


async def acquire(user_id: PydanticObjectId, model: ModelDoc) -> License:
    """Idempotently issue a free license for (user, model)."""
    if model.status != ModelStatus.approved:
        raise errors.forbidden("Model is not available", code="model_unavailable")

    existing = await License.find_one(
        License.user_id == user_id, License.model_id == model.id
    )
    if existing is not None:
        return existing  # idempotent

    license_ = License(
        license_key=gen_license_key(),
        user_id=user_id,
        model_id=model.id,
    )
    try:
        await license_.insert()
    except DuplicateKeyError:
        # Race: another request created it first — return that one.
        existing = await License.find_one(
            License.user_id == user_id, License.model_id == model.id
        )
        if existing:
            return existing
        raise
    return license_


async def get_license_for_user(
    license_key: str, user_id: PydanticObjectId
) -> License:
    license_ = await License.find_one(License.license_key == license_key)
    if license_ is None or license_.user_id != user_id:
        raise errors.not_found("License not found", code="license_not_found")
    return license_


async def bind_device(
    license_: License, device_id: str, device_name: str | None, platform: str | None
) -> Device:
    existing = await Device.find_one(
        Device.license_id == license_.id, Device.device_id == device_id
    )
    if existing is not None:
        existing.last_seen_at = utcnow()
        existing.status = DeviceStatus.active
        if device_name:
            existing.device_name = device_name
        if platform:
            existing.platform = platform
        await existing.save()
        return existing

    if license_.bound_device_count >= license_.max_devices:
        raise errors.conflict(
            f"Device cap reached ({license_.max_devices})",
            code="license_device_limit",
            details={"max_devices": license_.max_devices},
        )

    device = Device(
        license_id=license_.id,
        user_id=license_.user_id,
        device_id=device_id,
        device_name=device_name,
        platform=platform,
    )
    try:
        await device.insert()
    except DuplicateKeyError:
        raise errors.conflict("Device already bound", code="device_exists")

    license_.bound_device_count += 1
    license_.updated_at = utcnow()
    await license_.save()
    return device


async def unbind_device(license_: License, device_id: str) -> None:
    device = await Device.find_one(
        Device.license_id == license_.id, Device.device_id == device_id
    )
    if device is None:
        raise errors.not_found("Device not bound", code="device_not_found")
    await device.delete()
    license_.bound_device_count = max(0, license_.bound_device_count - 1)
    license_.updated_at = utcnow()
    await license_.save()


async def verify(
    license_: License, device_id: str, auto_bind: bool = False
) -> dict:
    """License verification for the local MCP Server (spec §5.4)."""
    model = await ModelDoc.get(license_.model_id)

    if license_.status != LicenseStatus.active:
        return {"valid": False, "reason": "license_revoked", "model_artifact_ref": None}
    if model is None or model.status != ModelStatus.approved:
        return {"valid": False, "reason": "model_unavailable", "model_artifact_ref": None}

    device = await Device.find_one(
        Device.license_id == license_.id, Device.device_id == device_id
    )
    if device is None:
        if not auto_bind:
            return {"valid": False, "reason": "device_not_bound", "model_artifact_ref": None}
        await bind_device(license_, device_id, None, None)
    else:
        device.last_seen_at = utcnow()
        await device.save()

    return {
        "valid": True,
        "reason": None,
        "model_artifact_ref": {
            "model_id": str(model.id),
            "storage_key": model.artifact.storage_key,
            "sha256": model.artifact.sha256,
            "size_bytes": model.artifact.size_bytes,
            "version": model.artifact.version,
        },
    }
