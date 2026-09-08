"""An httpx client that behaves like a browser under the CSRF rules.

Every mutating request the app serves now needs the double-submit token, so a
test client that does not carry one is testing a 403, not the endpoint. The
alternative to this class was threading a token through several hundred existing
calls, which would have rewritten tests that are not about CSRF at all - and
would have quietly stopped exercising the real client behaviour the moment
someone forgot one.

What it does is exactly what ``csrf.js`` does in the browser and what the React
HTTP layer will do: read the token cookie, copy it into ``X-CSRF-Token``. The
only addition is bootstrapping - a fresh client has no cookie yet, so the first
unsafe request fetches one, the same way a browser's first page load does.
"""
from __future__ import annotations

from httpx import AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, SAFE_METHODS

# Cheap, unauthenticated, and it hands back a token on the way out.
BOOTSTRAP_PATH = "/api/v1/auth/session"


class CSRFAsyncClient(AsyncClient):
    """``AsyncClient`` that attaches the CSRF token to unsafe methods."""

    async def request(self, method, url, **kwargs):  # type: ignore[override]
        if method.upper() in SAFE_METHODS:
            return await super().request(method, url, **kwargs)

        token = self.cookies.get(CSRF_COOKIE_NAME)
        if not token:
            # Ignore the status: 401 is the expected answer for an anonymous
            # caller and it still carries the Set-Cookie we came for.
            await super().request("GET", BOOTSTRAP_PATH)
            token = self.cookies.get(CSRF_COOKIE_NAME)

        if token:
            headers = dict(kwargs.pop("headers", None) or {})
            # An explicit header in the test wins: that is how a test asserts
            # what happens with a wrong or missing token.
            if not any(key.lower() == CSRF_HEADER_NAME.lower() for key in headers):
                headers[CSRF_HEADER_NAME] = token
            kwargs["headers"] = headers

        return await super().request(method, url, **kwargs)
