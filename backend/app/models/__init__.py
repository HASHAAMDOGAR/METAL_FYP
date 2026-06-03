"""Beanie document models (spec §4)."""
from app.models.device import Device
from app.models.license import License
from app.models.model import ModelDoc
from app.models.review import Review
from app.models.token_denylist import TokenDenylist
from app.models.usage_event import UsageEvent
from app.models.user import User

# Order matters only for readability; Beanie initializes them all together.
DOCUMENT_MODELS = [
    User,
    ModelDoc,
    License,
    Device,
    Review,
    UsageEvent,
    TokenDenylist,
]

__all__ = [
    "User",
    "ModelDoc",
    "License",
    "Device",
    "Review",
    "UsageEvent",
    "TokenDenylist",
    "DOCUMENT_MODELS",
]
