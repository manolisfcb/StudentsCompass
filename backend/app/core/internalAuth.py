"""Who is allowed to call the internal task endpoints.

These endpoints start paid work, so "internal" has to mean something a caller
can be held to, not a path prefix that happens not to be linked anywhere.
Cloud Tasks signs each request with an OIDC token minted for a specific service
account, and this module accepts exactly that:

* the token must be signed by Google and unexpired — checked against Google's
  published keys, not parsed and trusted;
* its ``aud`` must be the audience this service was configured with, so a token
  minted for another service cannot be replayed here;
* its ``email`` must be the one service account allowed to dispatch, verified.

The shared-secret path exists for compose and local development, where there is
no Google to mint anything. It is refused outright when ``ENV=production``: a
string in an environment variable is not an identity, and the difference
matters most exactly where it is most tempting to ignore.

A request that satisfies neither is a ``401``. There is no unauthenticated
fallback, because the failure mode of one would be silent.
"""
from __future__ import annotations

import hmac
import logging

from fastapi import HTTPException, Request

from app.config import (
    CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL,
    INTERNAL_TASKS_AUDIENCE,
    INTERNAL_TASKS_SHARED_SECRET,
    IS_PRODUCTION,
)

LOGGER = logging.getLogger(__name__)

SHARED_SECRET_HEADER = "X-Internal-Task-Secret"
GOOGLE_ISSUERS = frozenset({"https://accounts.google.com", "accounts.google.com"})

CODE_INTERNAL_TASK_UNAUTHORIZED = "internal_task_unauthorized"


class InternalTaskAuthError(Exception):
    """The caller did not prove it may start this work."""


def _unauthorized() -> HTTPException:
    # Deliberately uniform: the reason a token was refused is not the caller's
    # business, and spelling it out helps only someone probing the endpoint.
    return HTTPException(
        status_code=401,
        detail="This endpoint requires a valid task credential.",
        headers={"X-Error-Code": CODE_INTERNAL_TASK_UNAUTHORIZED},
    )


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def verify_google_oidc(token: str, *, verifier=None) -> dict:
    """Verify a Google-signed OIDC token and return its claims.

    ``verifier`` is injectable so the checks below can be tested without
    reaching Google. The default is ``google.oauth2.id_token``, which fetches
    and caches Google's signing keys — the part that makes the signature mean
    anything.
    """
    audience = INTERNAL_TASKS_AUDIENCE
    if not audience:
        raise InternalTaskAuthError("INTERNAL_TASKS_AUDIENCE is not configured")

    if verifier is None:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        def verifier(raw: str, expected_audience: str) -> dict:
            return id_token.verify_oauth2_token(
                raw, google_requests.Request(), expected_audience
            )

    try:
        claims = verifier(token, audience)
    except Exception as exc:  # noqa: BLE001 — every invalid token is one answer
        raise InternalTaskAuthError("The token could not be verified") from exc

    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise InternalTaskAuthError("Unexpected issuer")
    if claims.get("aud") != audience:
        raise InternalTaskAuthError("Unexpected audience")

    expected_email = CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL
    if not expected_email:
        raise InternalTaskAuthError("CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL is not configured")
    if claims.get("email") != expected_email:
        raise InternalTaskAuthError("Unexpected caller identity")
    if not claims.get("email_verified", False):
        raise InternalTaskAuthError("The caller identity is not verified")
    return claims


def _shared_secret_accepted(request: Request) -> bool:
    """The development path. Never available in production."""
    if IS_PRODUCTION or not INTERNAL_TASKS_SHARED_SECRET:
        return False
    presented = request.headers.get(SHARED_SECRET_HEADER, "")
    if not presented:
        return False
    # Constant time: the comparison itself must not leak the secret's prefix.
    return hmac.compare_digest(presented, INTERNAL_TASKS_SHARED_SECRET)


async def require_task_caller(request: Request) -> str:
    """FastAPI dependency. Returns how the caller was identified."""
    token = _bearer_token(request)
    if token is not None:
        try:
            claims = verify_google_oidc(token)
        except InternalTaskAuthError as exc:
            LOGGER.warning("Internal task call refused: %s", exc)
            raise _unauthorized() from exc
        return f"oidc:{claims.get('email')}"

    if _shared_secret_accepted(request):
        return "shared-secret"

    LOGGER.warning("Internal task call refused: no usable credential")
    raise _unauthorized()
