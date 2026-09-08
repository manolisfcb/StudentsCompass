"""Session contract shared by both identities.

The app has two authenticable actors - student and recruiter - each with its own
cookie, and until now nothing told a client which one it was holding. A server
rendered page did not need to ask: the template knew, because the view that
built it had already resolved the user. A client that renders itself has no such
luck, and the alternative to asking is guessing from a 401 on some unrelated
endpoint.

The two identities stay separate here. Merging them into one user model is a
data migration with its own failure modes, and doing it underneath a frontend
rewrite would mean debugging both at once.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.csrf import new_csrf_token, set_csrf_cookie
from app.models.companyRecruiterModel import CompanyRecruiter
from app.models.userModel import User
from app.schemas.sessionSchema import SessionActor, SessionRead
from app.services.accounts.userService import (
    auth_backend,
    current_active_user_optional,
    get_jwt_strategy,
)
from app.services.companies.companyService import (
    auth_backend_company,
    current_active_company_recruiter_optional,
    get_jwt_strategy_company,
)

router = APIRouter()


def _student_actor(user: User) -> SessionActor:
    display_name = " ".join(part for part in (user.first_name, user.last_name) if part).strip()
    return SessionActor(
        id=user.id,
        actor_type="student",
        email=user.email,
        display_name=display_name or user.nickname or None,
        is_active=bool(user.is_active),
        is_verified=bool(user.is_verified),
    )


def _recruiter_actor(recruiter: CompanyRecruiter) -> SessionActor:
    display_name = " ".join(part for part in (recruiter.first_name, recruiter.last_name) if part).strip()
    return SessionActor(
        id=recruiter.id,
        actor_type="recruiter",
        email=recruiter.email,
        display_name=display_name or None,
        is_active=bool(recruiter.is_active),
        is_verified=bool(recruiter.is_verified),
        company_id=recruiter.company_id,
        role=recruiter.role,
    )


def _unauthenticated() -> HTTPException:
    """One answer for "no cookie", "expired cookie" and "deactivated account".

    Saying which would let an unauthenticated caller learn whether an address is
    registered by watching how the refusal changes.
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"X-Error-Code": "not_authenticated"},
    )


def _build_session(
    request: Request,
    user: Optional[User],
    recruiter: Optional[CompanyRecruiter],
) -> SessionRead:
    actors: list[SessionActor] = []
    if user is not None:
        actors.append(_student_actor(user))
    if recruiter is not None:
        actors.append(_recruiter_actor(recruiter))

    if not actors:
        raise _unauthenticated()

    # Student first when both cookies are present: it is the account the person
    # signed up with, and the recruiter surface is reachable from it.
    return SessionRead(
        actor=actors[0],
        actors=actors,
        csrf_token=getattr(request.state, "csrf_token", "") or new_csrf_token(),
    )


@router.get("/auth/session", response_model=SessionRead, tags=["auth"])
async def read_session(
    request: Request,
    user: Optional[User] = Depends(current_active_user_optional),
    recruiter: Optional[CompanyRecruiter] = Depends(current_active_company_recruiter_optional),
) -> SessionRead:
    """Who this request is, or 401. The client's first call and its guard."""
    return _build_session(request, user, recruiter)


@router.post("/auth/session/refresh", response_model=SessionRead, tags=["auth"])
async def refresh_session(
    request: Request,
    response: Response,
    user: Optional[User] = Depends(current_active_user_optional),
    recruiter: Optional[CompanyRecruiter] = Depends(current_active_company_recruiter_optional),
) -> SessionRead:
    """Mint a fresh session cookie and a fresh CSRF token for the actors present.

    Explicit rather than automatic. A sliding cookie refreshed on every request
    never expires for an active tab, which is the opposite of what a session
    lifetime is for; this way the client decides when to extend, and each
    extension rotates both halves so a token captured earlier stops working.
    """
    session = _build_session(request, user, recruiter)

    # Re-issue each identity the caller actually holds. ``login`` writes the
    # transport's Set-Cookie onto its own response, so the headers are copied
    # across rather than returning it.
    if user is not None:
        issued = await auth_backend.login(get_jwt_strategy(), user)
        _copy_set_cookie(issued, response)
    if recruiter is not None:
        issued = await auth_backend_company.login(get_jwt_strategy_company(), recruiter)
        _copy_set_cookie(issued, response)

    rotated = new_csrf_token()
    set_csrf_cookie(response, rotated)
    request.state.csrf_rotated = True

    return session.model_copy(update={"csrf_token": rotated})


def _copy_set_cookie(source: Response, destination: Response) -> None:
    for key, value in source.raw_headers:
        if key.lower() == b"set-cookie":
            destination.raw_headers.append((key, value))
