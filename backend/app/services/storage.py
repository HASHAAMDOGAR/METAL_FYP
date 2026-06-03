"""Object storage abstraction (spec §6).

Two interchangeable backends, selected by ``settings.storage_backend``:

* ``"r2"``    — Cloudflare R2 via boto3 (S3-compatible presigned URLs). Used in
                production; requires R2 credentials.
* ``"local"`` — Filesystem store served by the API itself. Default, so the
                backend runs and is fully testable without any R2 credentials.

Both expose the same interface: ``presigned_put``, ``presigned_get``,
``head_object``, ``ping`` and ``artifact_key``. Callers (publisher upload,
download endpoint) are backend-agnostic.
"""
from __future__ import annotations

import os
from functools import lru_cache

from app.config import settings


def artifact_key(model_id: str) -> str:
    return f"models/{model_id}/model.gguf"


def _is_r2() -> bool:
    return settings.storage_backend.lower() == "r2"


# --------------------------------------------------------------------------
# Cloudflare R2 backend
# --------------------------------------------------------------------------
@lru_cache
def _r2_client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


# --------------------------------------------------------------------------
# Local filesystem backend
# --------------------------------------------------------------------------
def _local_path(key: str) -> str:
    safe = key.replace("..", "_")
    return os.path.join(settings.local_storage_dir, safe)


def _local_url(key: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/v1/storage/local/{key}"


# --------------------------------------------------------------------------
# Public interface
# --------------------------------------------------------------------------
def presigned_put(key: str, ttl: int | None = None) -> str:
    if _is_r2():
        return _r2_client().generate_presigned_url(
            "put_object",
            Params={"Bucket": settings.r2_bucket, "Key": key},
            ExpiresIn=ttl or settings.upload_url_ttl,
        )
    # local: upload goes to our own PUT endpoint
    os.makedirs(os.path.dirname(_local_path(key)), exist_ok=True)
    return _local_url(key)


def presigned_get(key: str, ttl: int | None = None) -> str:
    if _is_r2():
        return _r2_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.r2_bucket, "Key": key},
            ExpiresIn=ttl or settings.download_url_ttl,
        )
    return _local_url(key)


def head_object(key: str) -> dict | None:
    if _is_r2():
        try:
            return _r2_client().head_object(Bucket=settings.r2_bucket, Key=key)
        except Exception:
            return None
    path = _local_path(key)
    if os.path.exists(path):
        return {"ContentLength": os.path.getsize(path)}
    return None


def save_local(key: str, data: bytes) -> int:
    """Write bytes for the local backend (used by the local storage router)."""
    path = _local_path(key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def read_local(key: str) -> bytes | None:
    path = _local_path(key)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return f.read()


def ping() -> bool:
    """Used by /readyz."""
    if _is_r2():
        _r2_client().head_bucket(Bucket=settings.r2_bucket)
        return True
    # local: ensure the storage dir is writable
    os.makedirs(settings.local_storage_dir, exist_ok=True)
    return os.access(settings.local_storage_dir, os.W_OK)
