"""JWT, password hashing, and key generation (spec §8.1)."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

TokenType = Literal["access", "refresh"]


# --- Passwords ------------------------------------------------------------
def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


# --- JWT ------------------------------------------------------------------
def _create_token(sub: str, token_type: TokenType, ttl_seconds: int, **extra: Any) -> tuple[str, str, datetime]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=ttl_seconds)
    jti = str(uuid.uuid4())
    payload = {
        "sub": sub,
        "type": token_type,
        "jti": jti,
        "iat": now,
        "exp": expires,
        **extra,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti, expires


def create_access_token(user_id: str, roles: list[str]) -> str:
    token, _, _ = _create_token(user_id, "access", settings.access_ttl, roles=roles)
    return token


def create_refresh_token(user_id: str) -> tuple[str, str, datetime]:
    """Returns (token, jti, expires_at) so the jti can be tracked/denylisted."""
    return _create_token(user_id, "refresh", settings.refresh_ttl)


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    """Decode + validate. Raises JWTError on failure or type mismatch."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if expected_type and payload.get("type") != expected_type:
        raise JWTError(f"Expected {expected_type} token")
    return payload


# --- License keys ---------------------------------------------------------
def gen_license_key() -> str:
    """Opaque key like MCP-AB12-CD34-EF56 (spec §4.3)."""
    raw = secrets.token_hex(6).upper()  # 12 hex chars
    return f"MCP-{raw[0:4]}-{raw[4:8]}-{raw[8:12]}"
