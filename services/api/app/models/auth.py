"""Shared identifiers and UTC timestamps for persisted records."""

from datetime import datetime, timezone
from uuid import uuid4


def uid() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def __getattr__(name: str):
    # Older call sites import User from this module.
    if name == 'User':
        from app.models import User
        return User
    raise AttributeError(name)
