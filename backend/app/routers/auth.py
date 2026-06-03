"""Auth endpoints (spec §5.1, §8.1)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from pymongo.errors import DuplicateKeyError

from app import errors
from app.models.enums import Role
from app.models.token_denylist import TokenDenylist
from app.models.user import User
from app.schemas.auth import RegisterRequest, TokenResponse
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _roles_str(user: User) -> list[str]:
    return [r.value for r in user.roles]


def _issue_tokens(user: User) -> TokenResponse:
    access = create_access_token(str(user.id), _roles_str(user))
    refresh, _, _ = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest) -> TokenResponse:
    roles = body.roles or [Role.app_developer]
    user = User(
        email=body.email,
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        roles=roles,
    )
    try:
        await user.insert()
    except DuplicateKeyError:
        raise errors.conflict("Email or username already registered", code="user_exists")
    return _issue_tokens(user)


@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    # `username` field may carry email or username.
    ident = form.username
    user = await User.find_one({"$or": [{"email": ident}, {"username": ident}]})
    if user is None or not verify_password(form.password, user.password_hash):
        raise errors.unauthorized("Invalid credentials")
    if not user.is_active:
        raise errors.forbidden("Account disabled")
    return _issue_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: dict) -> TokenResponse:
    token = body.get("refresh_token")
    if not token:
        raise errors.bad_request("refresh_token is required")
    try:
        payload = decode_token(token, expected_type="refresh")
    except JWTError:
        raise errors.unauthorized("Invalid or expired refresh token")

    jti = payload.get("jti")
    if jti and await TokenDenylist.find_one(TokenDenylist.jti == jti):
        raise errors.unauthorized("Refresh token has been revoked")

    from beanie import PydanticObjectId

    user = await User.get(PydanticObjectId(payload["sub"]))
    if user is None or not user.is_active:
        raise errors.unauthorized("User not found or inactive")

    # Rotation: deny the old refresh jti, issue a fresh pair.
    if jti:
        await TokenDenylist(
            jti=jti,
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        ).insert()
    return _issue_tokens(user)


@router.post("/logout", status_code=204, response_model=None)
async def logout(body: dict) -> None:
    token = body.get("refresh_token")
    if not token:
        raise errors.bad_request("refresh_token is required")
    try:
        payload = decode_token(token, expected_type="refresh")
    except JWTError:
        return  # already invalid; nothing to revoke
    jti = payload.get("jti")
    if jti and not await TokenDenylist.find_one(TokenDenylist.jti == jti):
        await TokenDenylist(
            jti=jti,
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        ).insert()
