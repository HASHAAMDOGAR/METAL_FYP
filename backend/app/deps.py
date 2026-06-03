"""FastAPI dependencies: auth, role guards, license guards (spec §8.1, §5.4)."""
from __future__ import annotations

from beanie import PydanticObjectId
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from app import errors
from app.models.enums import LicenseStatus, Role
from app.models.license import License
from app.models.user import User
from app.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login", auto_error=False)


async def get_current_user(token: str | None = Depends(oauth2_scheme)) -> User:
    if not token:
        raise errors.unauthorized()
    try:
        payload = decode_token(token, expected_type="access")
    except JWTError:
        raise errors.unauthorized("Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise errors.unauthorized("Malformed token")

    user = await User.get(PydanticObjectId(user_id))
    if user is None or not user.is_active:
        raise errors.unauthorized("User not found or inactive")
    return user


def require_roles(*roles: Role):
    """Dependency factory enforcing that the user holds at least one role."""

    async def _guard(user: User = Depends(get_current_user)) -> User:
        if not any(r in user.roles for r in roles):
            raise errors.forbidden(
                f"Requires one of roles: {', '.join(r.value for r in roles)}"
            )
        return user

    return _guard


async def require_license(
    model_id: PydanticObjectId, user: User
) -> License:
    """Return the user's active license for a model, or raise 403."""
    license_ = await License.find_one(
        License.user_id == user.id,
        License.model_id == model_id,
        License.status == LicenseStatus.active,
    )
    if license_ is None:
        raise errors.forbidden("No active license for this model", code="license_required")
    return license_
