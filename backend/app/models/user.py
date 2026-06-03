"""User document (spec §4.1)."""
from __future__ import annotations

from datetime import datetime

import pymongo
from beanie import Document
from pydantic import BaseModel, EmailStr, Field

from app.models.common import utcnow
from app.models.enums import Role


class PublisherProfile(BaseModel):
    org_name: str | None = None
    bio: str | None = None
    website: str | None = None


class User(Document):
    email: EmailStr
    username: str
    password_hash: str
    roles: list[Role] = Field(default_factory=lambda: [Role.app_developer])
    display_name: str | None = None
    is_active: bool = True
    is_verified: bool = False
    publisher_profile: PublisherProfile | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "users"
        indexes = [
            pymongo.IndexModel("email", unique=True),
            pymongo.IndexModel("username", unique=True),
        ]

    @property
    def is_publisher(self) -> bool:
        return Role.model_developer in self.roles

    @property
    def is_admin(self) -> bool:
        return Role.admin in self.roles
