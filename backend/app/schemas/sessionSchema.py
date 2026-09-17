"""The shape a client uses to decide who it is talking as.

Kept deliberately small. It answers "which identity does this cookie carry, and
what may it call itself" - not "what may it do". Authorization stays in the
backend: a client that reads ``actor_type`` here and shows a menu is choosing
navigation, and every endpoint behind that menu still decides for itself.
"""
from __future__ import annotations

import uuid
from typing import Literal, Optional

from pydantic import BaseModel

ActorType = Literal["student", "recruiter"]


class SessionActor(BaseModel):
    id: uuid.UUID
    actor_type: ActorType
    email: str
    display_name: Optional[str] = None
    is_active: bool
    is_verified: bool
    # Recruiter-only. Absent for a student rather than null-for-everyone, so a
    # client cannot mistake "no company" for "company not loaded".
    company_id: Optional[uuid.UUID] = None
    role: Optional[str] = None
    # Student-only, and navigation-only, like everything else here: the admin
    # endpoints re-check it for themselves and answer 403 regardless of what a
    # client believes. It is exposed because without it the SPA cannot make the
    # navigation decision the monolith made — `views.py` bounced
    # `not user.is_superuser` off `/admin` to `/admin/login`, and a client that
    # cannot tell an admin from a student has to show the admin shell to both
    # and let it fill with 403s (TASK-053).
    is_superuser: bool = False


class SessionRead(BaseModel):
    """The effective actor, plus every identity this browser currently holds.

    Both cookies can be present at once: student and recruiter are separate
    identities with separate cookies, and the app has always allowed a person to
    hold both. ``actor`` is the one the client should present as; ``actors``
    exists so a client can offer to switch instead of guessing that the other
    session expired.
    """
    actor: SessionActor
    actors: list[SessionActor]
    csrf_token: str
