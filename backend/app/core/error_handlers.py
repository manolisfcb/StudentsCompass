"""The one place a failing ``/api/v1`` request is turned into a body.

Before this, the shape depended on how a route happened to fail. A route that
used the TASK-011 helpers answered ``{"detail": "... (ref: abc)"}`` with the
code in an ``X-Error-Code`` header; one of the 119 bare ``HTTPException`` sites
answered ``{"detail": ...}`` with no code at all; an unhandled exception fell to
Starlette's default and answered ``Internal Server Error`` as plain text. Three
shapes, and a client that had to parse prose to tell them apart.

These handlers normalise at the **edge** instead of at the raise site. That is
deliberate and it is what keeps this task inside its Scope: rewriting 119 raise
sites would change which operations fail and with what status, which §Scope puts
out of bounds. Here nothing about *when* a request fails changes — only the
bytes it answers with.

**Scoped to ``/api/v1``.** ``views_router`` still serves Jinja pages and
``internal_tasks_router`` is not part of the public contract; neither is mounted
under the prefix, and an HTML page whose 404 became a JSON envelope would be a
regression. Anything outside the prefix keeps the framework's behaviour
untouched.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import (
    GENERIC_SERVER_MESSAGE,
    AppError,
    ErrorCode,
    code_for_status,
    error_envelope,
    is_safe_client_message,
    log_cause,
)
from app.core.observability import current_request_id

LOGGER = logging.getLogger("app.error")

API_PREFIX = "/api/v1"

#: Codes the TASK-011 helpers already put on the exception. Reading them back
#: is what lets those 20 call sites keep their precise code without being
#: touched: the helper's header is the carrier, this is the receiver.
ERROR_CODE_HEADER = "X-Error-Code"
ERROR_ID_HEADER = "X-Error-Id"


def _is_api(request: Request) -> bool:
    return request.url.path.startswith(API_PREFIX)


def _request_id(request: Request) -> str:
    """This request's id, read from the place that is still in scope.

    The ``ContextVar`` is not always readable here. Starlette runs the handler
    for an *unhandled* exception from ``ServerErrorMiddleware``, which sits
    **outside** ``RequestContextMiddleware`` — so that middleware's ``finally``
    has already reset the id, and the contextvar reads ``-``. The 500 body would
    then quote an id that appears in no log line, which is precisely the
    correlation this task exists to provide.

    ``scope["state"]`` does not unwind, so it is the reliable source; the
    contextvar remains the fallback for a handler reached some other way.
    """
    from_scope = request.scope.get("state", {}).get("request_id")
    if from_scope:
        return from_scope
    return current_request_id()


def _envelope_response(
    request: Request,
    status_code: int,
    code: ErrorCode | str,
    message: str,
    *,
    details=None,
    headers: dict[str, str] | None = None,
    legacy_detail: object | None = None,
) -> JSONResponse:
    body = error_envelope(code, message, request_id=_request_id(request), details=details)

    # --- legacy adapter, retired by TASK-059 -------------------------------
    # The Jinja screens are still live and read ``errorData.detail`` directly
    # (``questionnaire.js``, ``register.js``, ``company-dashboard.js`` and
    # others). Dropping the key here would not break a test — it would break
    # the running app, so §Scope asks for the old shape to be kept as an
    # adapter while a legacy consumer still reads it.
    #
    # The value is reproduced, never synthesised. A helper from
    # ``app.core.errors`` already ends its detail with "(ref: ...)", so that
    # suffix survives by coming through ``message``; the bare raise sites never
    # had one, and appending it here would have put a correlation id into
    # sentences the user reads on screen. Same string as before, per site.
    #
    # New clients must read ``error``; this key carries no code and no details,
    # and it goes away with the templates.
    body["detail"] = message if legacy_detail is None else legacy_detail

    # The id is echoed in a header too: a client that cannot read a body — a
    # 204, a CORS preflight, a proxy log — can still quote it.
    merged = {ERROR_ID_HEADER: body["error"]["request_id"], ERROR_CODE_HEADER: str(code)}
    if headers:
        merged.update(headers)
    return JSONResponse(status_code=status_code, content=body, headers=merged)


def _message_and_details(detail, status_code: int) -> tuple[str, object | None]:
    """Split whatever a raise site passed as ``detail`` into the two fields.

    ``detail`` is a free-for-all in FastAPI: a string, a dict, a list. A dict or
    list is structured, so it belongs in ``details``; the message then falls
    back to the family sentence rather than being a JSON dump rendered as prose.
    """
    if isinstance(detail, (dict, list)):
        return _generic_message(status_code), detail
    text = str(detail) if detail is not None else ""
    if not text or not is_safe_client_message(text):
        # A message that smells of machinery never reaches the caller, whatever
        # raised it. The unsafe original is not logged here — the handler that
        # has the exception logs it with the traceback.
        return _generic_message(status_code), None
    return text, None


def _catalogued(raw_code: str | None, status_code: int) -> ErrorCode:
    """Only a catalogue member reaches a client.

    A raise site hands its code over as a header string, so nothing stops a typo
    or an invented value from becoming public and permanent — the exact failure
    mode the enum exists to close. An unknown code is reported and the family
    code is used instead, so a mistake degrades to something truthful rather
    than shipping a contract nobody declared.
    """
    if raw_code is None:
        return code_for_status(status_code)
    try:
        return ErrorCode(raw_code)
    except ValueError:
        LOGGER.warning(
            "error code %r is not in the catalogue; answering with the family code",
            raw_code,
        )
        return code_for_status(status_code)


def _generic_message(status_code: int) -> str:
    if status_code >= 500:
        return GENERIC_SERVER_MESSAGE
    return _FAMILY_MESSAGES.get(status_code, "The request could not be processed.")


_FAMILY_MESSAGES: dict[int, str] = {
    401: "Authentication is required.",
    403: "You do not have access to this resource.",
    404: "The requested resource was not found.",
    405: "That method is not allowed on this resource.",
    409: "The request conflicts with the current state.",
    413: "The request payload is too large.",
    422: "The request failed validation.",
    429: "Too many requests. Please slow down.",
}


def install_error_handlers(app: FastAPI) -> None:
    """Register the handlers. Called once, from ``app.py``."""

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        if not _is_api(request):
            raise exc  # nothing outside the API raises it; let the server 500
        if exc.status_code >= 500:
            log_cause(LOGGER, exc, code=str(exc.code), reference=_request_id(request))
        return _envelope_response(
            request, exc.status_code, exc.code, exc.message, details=exc.details
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        if not _is_api(request):
            return await request_validation_exception_handler(request, exc)
        # Pydantic's own list is the machine-readable answer to "which field?",
        # but its ``ctx`` can carry the offending *value* — a password, a CV
        # fragment — and ``url`` links a docs page that varies by version.
        details = [
            {
                "loc": [str(part) for part in error.get("loc", ())],
                "type": error.get("type", ""),
                "msg": error.get("msg", ""),
            }
            for error in exc.errors()
        ]
        return _envelope_response(
            request,
            422,
            ErrorCode.VALIDATION_FAILED,
            _generic_message(422),
            details=details,
            legacy_detail=details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        if not _is_api(request):
            return await http_exception_handler(request, exc)
        headers = dict(getattr(exc, "headers", None) or {})
        # A helper from ``app.core.errors`` already chose a catalogue code and
        # put it here; a bare raise site did not, and gets its family code.
        raw_code = headers.pop(ERROR_CODE_HEADER, None)
        headers.pop(ERROR_ID_HEADER, None)
        code = _catalogued(raw_code, exc.status_code)
        message, details = _message_and_details(exc.detail, exc.status_code)
        return _envelope_response(
            request, exc.status_code, code, message, details=details, headers=headers
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        if not _is_api(request):
            raise exc
        # The traceback goes to the log under this request's id and nowhere
        # else. This is the branch that used to leak ``str(exception)``.
        reference = _request_id(request)
        log_cause(
            LOGGER,
            exc,
            code=str(ErrorCode.INTERNAL),
            reference=reference,
            context=f"{request.method} {request.url.path}",
        )
        return _envelope_response(request, 500, ErrorCode.INTERNAL, GENERIC_SERVER_MESSAGE)


__all__ = ["install_error_handlers", "API_PREFIX", "ERROR_CODE_HEADER", "ERROR_ID_HEADER"]
