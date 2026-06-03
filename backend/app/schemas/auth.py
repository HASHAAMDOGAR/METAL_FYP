"""Auth & user request/response schemas (spec §5.1)."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import Role
from app.models.user import PublisherProfile


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = None
    roles: list[Role] | None = None  # defaults to [app_developer]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    username: str
    roles: list[Role]
    display_name: str | None = None
    is_active: bool
    is_verified: bool
    publisher_profile: PublisherProfile | None = None


class UpdateMeRequest(BaseModel):
    display_name: str | None = None
    publisher_profile: PublisherProfile | None = None


class BecomePublisherRequest(BaseModel):
    org_name: str | None = None
    bio: str | None = None
    website: str | None = None
