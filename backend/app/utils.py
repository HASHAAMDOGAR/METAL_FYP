"""Small shared utilities."""
from __future__ import annotations

import re
import secrets

_slug_re = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    base = _slug_re.sub("-", text.lower()).strip("-")
    return base or "model"


def unique_suffix(n: int = 4) -> str:
    return secrets.token_hex(n // 2 + 1)[:n]
