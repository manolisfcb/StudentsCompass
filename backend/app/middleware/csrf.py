"""Enforce the double-submit CSRF token on every mutating request.

Two responsibilities, deliberately in one place so they cannot drift apart:

* Issue. Any request without a token gets one, and the cookie rides back on the
  response. That is what makes a cold client work: a browser loading a page and
  a REST client calling ``GET /api/v1/auth/session`` both come away holding a
  token before they need one.
* Verify. Every unsafe method must present the token in ``X-CSRF-Token``
  matching the cookie, and must not arrive from a foreign ``Origin``.

Applied as middleware rather than as a dependency per route because the failure
mode of the per-route version is silence: a new mutating endpoint that forgets
the dependency is unprotected and nothing says so. Here the default is closed,
and an exemption has to be written down in ``exempt_paths``.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SAFE_METHODS,
    new_csrf_token,
    origin_is_allowed,
    request_origin,
    set_csrf_cookie,
    tokens_match,
)
from app.core.errors import ErrorCode, new_error_reference

CODE_CSRF = ErrorCode.CSRF_TOKEN_INVALID

# One message for a missing token, a stale token and a foreign origin alike. The
# client cannot act differently on the three, and distinguishing them would tell
# a probing page which half of the check it just failed.
CSRF_MESSAGE = "The request could not be verified. Please reload the page and try again."


class CSRFMiddleware(BaseHTTPMiddleware):
    """Refuse unsafe methods that do not echo the CSRF cookie back in a header.

    ``exempt_paths`` holds prefixes that are checked some other way: the machine
    callers that never carry a browser cookie in the first place, and so cannot
    be the target of a cross-site request.
    """

    def __init__(
        self,
        app,
        *,
        allowed_origins: list[str] | None = None,
        exempt_paths: tuple[str, ...] = (),
        rotate_paths: tuple[str, ...] = (),
    ):
        super().__init__(app)
        self.allowed_origins = frozenset(
            origin.strip().lower().rstrip("/") for origin in (allowed_origins or []) if origin.strip()
        )
        self.exempt_paths = exempt_paths
        self.rotate_paths = rotate_paths

    def _is_exempt(self, path: str) -> bool:
        return any(path.startswith(prefix) for prefix in self.exempt_paths)

    def _rotates(self, path: str) -> bool:
        return any(path.endswith(suffix) for suffix in self.rotate_paths)

    @staticmethod
    def _refuse(issued_token: str) -> JSONResponse:
        """Refuse, and hand back a usable token on the way out.

        Without this the refusal is a dead end: a client whose token expired -
        or one that opened with a POST and never had one - gets a 403 and no way
        to obtain the thing it was missing, so every subsequent attempt fails
        the same way. Issuing here makes a single retry succeed, which is the
        behaviour the frontend is being written against.

        It gives an attacker's page nothing: a cross-site request cannot read
        this response, which is the whole reason the scheme works.
        """
        reference = new_error_reference()
        response = JSONResponse(
            status_code=403,
            content={"detail": f"{CSRF_MESSAGE} (ref: {reference})"},
            headers={"X-Error-Code": CODE_CSRF, "X-Error-Id": reference},
        )
        set_csrf_cookie(response, issued_token)
        return response

    async def dispatch(self, request, call_next):
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)

        # The token this request is entitled to for the rest of its life. A
        # client that already holds one keeps it: rotating on every response
        # would race with any page that has two requests in flight.
        issued_token = cookie_token or new_csrf_token()
        request.state.csrf_token = issued_token

        must_verify = request.method.upper() not in SAFE_METHODS and not self._is_exempt(request.url.path)

        if must_verify:
            if not origin_is_allowed(request_origin(request), self.allowed_origins):
                return self._refuse(issued_token)
            if not tokens_match(cookie_token, request.headers.get(CSRF_HEADER_NAME)):
                return self._refuse(issued_token)

        response = await call_next(request)

        # A route that rotated the token itself (session refresh) has already
        # set its own cookie; do not overwrite it with the pre-rotation value.
        if getattr(request.state, "csrf_rotated", False):
            return response

        # Crossing an authentication boundary invalidates the old token. Without
        # this, a token an attacker planted before login stays valid after it,
        # which is the fixation half of the same attack the token defends
        # against. Only on success: a refused login changes no identity.
        if self._rotates(request.url.path) and response.status_code < 400:
            set_csrf_cookie(response, new_csrf_token())
            return response

        if cookie_token != issued_token:
            set_csrf_cookie(response, issued_token)

        return response
