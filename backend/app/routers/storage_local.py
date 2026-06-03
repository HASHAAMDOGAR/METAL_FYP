"""Local filesystem storage endpoints (dev/test alternative to R2, spec §6).

Only mounted when ``settings.storage_backend == "local"``. These simulate R2
presigned PUT/GET: publishers upload bytes here, clients download from here.
The key path mirrors the R2 object key (``models/{id}/model.gguf``).
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app import errors
from app.services import storage

router = APIRouter(tags=["storage"])


@router.put("/storage/local/{key:path}")
async def upload_local(key: str, request: Request) -> dict:
    data = await request.body()
    if not data:
        raise errors.bad_request("Empty upload body", code="empty_upload")
    size = storage.save_local(key, data)
    return {"stored": True, "key": key, "size_bytes": size}


@router.get("/storage/local/{key:path}")
async def download_local(key: str) -> Response:
    data = storage.read_local(key)
    if data is None:
        raise errors.not_found("Object not found", code="object_not_found")
    return Response(content=data, media_type="application/octet-stream")
