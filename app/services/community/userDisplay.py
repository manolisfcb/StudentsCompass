from __future__ import annotations

from app.models.userModel import User
from app.schemas.friendshipSchema import FriendUserSummary

DEFAULT_DISPLAY_NAME = "Student"


def build_display_name(
    *,
    first_name: str | None,
    last_name: str | None,
    nickname: str | None = None,
    email: str | None = None,
) -> str:
    """Build a human-readable display name from individual user fields.

    Falls back through full name -> nickname -> email -> a generic label, so
    callers that only have column values (e.g. enriched queries) and callers
    that have a full ``User`` share one consistent rule.
    """
    full_name = " ".join(part for part in (first_name, last_name) if part).strip()
    return full_name or nickname or email or DEFAULT_DISPLAY_NAME


def build_display_name_from_user(user: User) -> str:
    return build_display_name(
        first_name=user.first_name,
        last_name=user.last_name,
        nickname=user.nickname,
        email=user.email,
    )


def build_user_summary(user: User) -> FriendUserSummary:
    return FriendUserSummary(
        id=user.id,
        display_name=build_display_name_from_user(user),
        nickname=user.nickname,
        first_name=user.first_name,
        last_name=user.last_name,
    )
