"""Licensing & device binding endpoints (spec §5.4)."""
from __future__ import annotations

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends

from app import errors
from app.deps import get_current_user
from app.models.device import Device
from app.models.model import ModelDoc
from app.models.user import User
from app.schemas.license import (
    BindDeviceRequest,
    DeviceResponse,
    LicenseResponse,
    VerifyRequest,
    VerifyResponse,
)
from app.services import licensing

router = APIRouter(tags=["licenses"])


async def _devices_for(license_id: PydanticObjectId) -> list[DeviceResponse]:
    docs = await Device.find(Device.license_id == license_id).to_list()
    return [
        DeviceResponse(
            device_id=d.device_id,
            device_name=d.device_name,
            platform=d.platform,
            bound_at=d.bound_at,
            last_seen_at=d.last_seen_at,
            status=d.status.value,
        )
        for d in docs
    ]


async def _to_response(license_) -> LicenseResponse:
    return LicenseResponse(
        license_key=license_.license_key,
        model_id=str(license_.model_id),
        status=license_.status,
        issued_at=license_.issued_at,
        max_devices=license_.max_devices,
        bound_device_count=license_.bound_device_count,
        devices=await _devices_for(license_.id),
    )


@router.post("/models/{model_id}/acquire", response_model=LicenseResponse, status_code=201)
async def acquire_model(
    model_id: str, user: User = Depends(get_current_user)
) -> LicenseResponse:
    try:
        oid = PydanticObjectId(model_id)
    except Exception:
        raise errors.not_found("Model not found", code="model_not_found")
    model = await ModelDoc.get(oid)
    if model is None:
        raise errors.not_found("Model not found", code="model_not_found")
    license_ = await licensing.acquire(user.id, model)
    return await _to_response(license_)


@router.get("/licenses", response_model=list[LicenseResponse])
async def my_licenses(user: User = Depends(get_current_user)) -> list[LicenseResponse]:
    from app.models.license import License

    docs = await License.find(License.user_id == user.id).to_list()
    return [await _to_response(d) for d in docs]


@router.get("/licenses/{key}", response_model=LicenseResponse)
async def license_detail(
    key: str, user: User = Depends(get_current_user)
) -> LicenseResponse:
    license_ = await licensing.get_license_for_user(key, user.id)
    return await _to_response(license_)


@router.post("/licenses/{key}/devices", response_model=LicenseResponse, status_code=201)
async def bind_device(
    key: str, body: BindDeviceRequest, user: User = Depends(get_current_user)
) -> LicenseResponse:
    license_ = await licensing.get_license_for_user(key, user.id)
    await licensing.bind_device(license_, body.device_id, body.device_name, body.platform)
    return await _to_response(license_)


@router.delete("/licenses/{key}/devices/{device_id}", response_model=LicenseResponse)
async def unbind_device(
    key: str, device_id: str, user: User = Depends(get_current_user)
) -> LicenseResponse:
    license_ = await licensing.get_license_for_user(key, user.id)
    await licensing.unbind_device(license_, device_id)
    return await _to_response(license_)


@router.post("/licenses/{key}/verify", response_model=VerifyResponse)
async def verify_license(
    key: str, body: VerifyRequest, user: User = Depends(get_current_user)
) -> VerifyResponse:
    """Consumed by the local MCP Server before loading a model (spec §5.4)."""
    license_ = await licensing.get_license_for_user(key, user.id)
    result = await licensing.verify(license_, body.device_id, body.auto_bind)
    return VerifyResponse(**result)
