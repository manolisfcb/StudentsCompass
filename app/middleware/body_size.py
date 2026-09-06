"""Cap the request body before anything parses it.

By the time a route handler runs, Starlette has already read the entire body and
run it through the multipart parser, spooling large parts to a temp file. A
limit checked in the handler therefore prevents nothing: the memory and the disk
have been spent, and the only thing left to decide is whether to also pay the
storage provider.

This is plain ASGI middleware rather than ``BaseHTTPMiddleware`` precisely so it
can sit in front of that: it wraps ``receive`` and counts bytes as the server
hands them over, so an oversized body is refused mid-stream. ``Content-Length``
is used as a fast path when it is present, but the streaming count is what
covers a chunked request, which sends no ``Content-Length`` at all.
"""
from __future__ import annotations

_BODYLESS_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "DELETE"})

# A multipart body carries boundaries, part headers and the filename on top of
# the file itself. The route's own budget is about the *file*, so the raw-body
# cap needs this much slack or a file exactly at the limit would be refused here
# before the route could answer precisely.
MULTIPART_OVERHEAD_BYTES = 16 * 1024


class BodyTooLarge(Exception):
    """Raised from the wrapped ``receive`` once the budget is passed."""


class RequestBodySizeLimitMiddleware:
    """Reject bodies larger than the budget that applies to the path.

    ``budgets`` maps a path prefix to its maximum raw body size; the longest
    matching prefix wins, and ``default_max_bytes`` covers everything else.
    """

    def __init__(self, app, *, default_max_bytes: int, budgets: dict[str, int] | None = None):
        self.app = app
        self.default_max_bytes = default_max_bytes
        # Longest prefix first, so a specific route beats a general one.
        self.budgets = sorted((budgets or {}).items(), key=lambda item: -len(item[0]))

    def limit_for(self, path: str) -> int:
        for prefix, max_bytes in self.budgets:
            if path.startswith(prefix):
                return max_bytes
        return self.default_max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method", "").upper() in _BODYLESS_METHODS:
            await self.app(scope, receive, send)
            return

        limit = self.limit_for(scope.get("path", ""))

        declared = _declared_length(scope)
        if declared is not None and declared > limit:
            # Nothing has been read yet: the cheapest possible refusal.
            await _send_too_large(send, limit)
            return

        received = 0

        async def counting_receive():
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise BodyTooLarge(limit)
            return message

        response_started = False

        async def tracking_send(message):
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except BodyTooLarge:
            if response_started:
                # Too late to change the status; the client already has one.
                raise
            await _send_too_large(send, limit)


def _declared_length(scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name.lower() == b"content-length":
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    return None


async def _send_too_large(send, limit: int) -> None:
    body = (
        b'{"detail":"Request body is too large. Maximum allowed size is '
        + str(max(1, limit // 1_000_000)).encode()
        + b' MB."}'
    )
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
