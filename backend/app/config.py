"""Application configuration loaded from environment / .env (spec §8.6)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "metal_marketplace"

    # JWT / Auth
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_ttl: int = 900
    refresh_ttl: int = 604800

    # Storage backend: "r2" (Cloudflare R2) or "local" (filesystem, for dev/testing).
    # Defaults to "local" so the backend runs without R2 credentials.
    storage_backend: str = "local"
    local_storage_dir: str = ".localstorage"
    public_base_url: str = "http://localhost:8000"

    # Cloudflare R2 (used only when storage_backend == "r2")
    r2_account_id: str = ""
    r2_endpoint: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "metal-marketplace-models"

    # Modal
    modal_token_id: str = ""
    modal_token_secret: str = ""
    modal_app_name: str = "metal-llm-fallback"

    # Misc
    download_url_ttl: int = 300
    upload_url_ttl: int = 900
    max_devices_default: int = 3
    rate_limit_per_minute: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
