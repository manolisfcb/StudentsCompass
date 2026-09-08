"""Double-submit CSRF tokens for the cookie-authenticated API.

Both identities in this app authenticate with an httpOnly cookie, which the
browser attaches to any request a third-party page can provoke. ``SameSite=Lax``
already blocks the cross-site *form* POST, but it is one setting on one cookie:
it does not survive a same-site subdomain, it is relaxed for top-level
navigations, and it is not a check the application itself performs. The token
here is that check.

Double-submit, specifically: the token travels in a cookie the page's own script
can read and in the ``X-CSRF-Token`` header it copies there. An attacker's page
can make the browser send the cookie, but the same-origin policy stops it from
*reading* the cookie, so it cannot produce the matching header. The cookie is
therefore deliberately NOT httpOnly - the client has to read it - which is safe
only because it carries no authority on its own: it authorizes nothing without
the session cookie beside it.

``Origin`` is validated alongside the token rather than instead of it. A browser
sets ``Origin`` on mutating requests and a page cannot forge it, so it catches
the same attack one step earlier; but it is absent on some same-origin requests
and from non-browser clients, so it can only ever reject, never authorize.
"""
from __future__ import annotations

import secrets
from urllib.parse import urlsplit

from starlette.requests import Request
from starlette.responses import Response

from app.config import IS_PRODUCTION

CSRF_COOKIE_NAME = "studentscompass_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"

# Methods that RFC 9110 calls safe: they must not change state, so a token
# would protect nothing. Everything else is checked.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

TOKEN_BYTES = 32

# Matches the session cookies' lifetime (see userService/companyService), so the
# token never expires while the session it protects is still usable.
CSRF_COOKIE_MAX_AGE = 3600


def new_csrf_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def set_csrf_cookie(response: Response, token: str) -> None:
    """Publish the token to the client.

    ``httponly=False`` on purpose: the whole mechanism depends on the page's own
    script reading this value back. See the module docstring.
    """
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        max_age=CSRF_COOKIE_MAX_AGE,
        httponly=False,
        secure=IS_PRODUCTION,
        samesite="lax",
        path="/",
    )


def clear_csrf_cookie(response: Response) -> None:
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/")


def tokens_match(cookie_token: str | None, header_token: str | None) -> bool:
    """Constant-time comparison of the two halves of the double submit.

    Both halves must be present and non-empty: an empty cookie and an empty
    header are equal, and treating that as a match would let a client that has
    never been issued a token mutate freely.
    """
    if not cookie_token or not header_token:
        return False
    return secrets.compare_digest(cookie_token, header_token)


def _normalize_origin(value: str) -> str:
    parts = urlsplit(value)
    if not parts.scheme or not parts.netloc:
        return ""
    return f"{parts.scheme}://{parts.netloc}".lower()


def request_origin(request: Request) -> str:
    """The origin the browser says this request came from, normalized.

    ``Origin`` is authoritative when present. ``Referer`` is the fallback for
    the browsers and request shapes that omit it; it carries a full URL, so only
    its scheme and authority are taken.
    """
    origin = request.headers.get("origin", "").strip()
    if origin and origin.lower() != "null":
        return _normalize_origin(origin)

    referer = request.headers.get("referer", "").strip()
    if referer:
        return _normalize_origin(referer)

    return ""


def origin_is_allowed(origin: str, allowed_origins: frozenset[str]) -> bool:
    """An absent origin is not a rejection; see the module docstring.

    Only a *present* origin that is not on the list fails here. The token check
    is what covers the case where the header is missing entirely.
    """
    if not origin:
        return True
    return origin in allowed_origins
