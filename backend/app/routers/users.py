"""User profile endpoints (spec §5.1)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.models.common import utcnow
from app.models.enums import Role
from app.models.user import PublisherProfile, User
from app.schemas.auth import BecomePublisherRequest, UpdateMeRequest, UserResponse

router = APIRouter(tags=["users"])


def _to_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        username=user.username,
        roles=user.roles,
        display_name=user.display_name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        publisher_profile=user.publisher_profile,
    )


@router.get("/users/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)) -> UserResponse:
    return _to_response(user)


@router.patch("/users/me", response_model=UserResponse)
async def update_me(
    body: UpdateMeRequest, user: User = Depends(get_current_user)
) -> UserResponse:
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.publisher_profile is not None:
        user.publisher_profile = body.publisher_profile
    user.updated_at = utcnow()
    await user.save()
    return _to_response(user)


@router.post("/users/me/become-publisher", response_model=UserResponse)
async def become_publisher(
    body: BecomePublisherRequest, user: User = Depends(get_current_user)
) -> UserResponse:
    if Role.model_developer not in user.roles:
        user.roles.append(Role.model_developer)
    user.publisher_profile = PublisherProfile(
        org_name=body.org_name, bio=body.bio, website=body.website
    )
    user.updated_at = utcnow()
    await user.save()
    return _to_response(user)
