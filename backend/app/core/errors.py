"""One place that decides what a failing request tells the caller.

Routes used to answer with ``str(e)``. A storage or driver exception carries
connection strings, SQL, bound parameters and file paths, so that turned an
internal fault into a description of the machine. The rules here:

* the **public** body never contains exception text — it carries a stable code,
  a fixed human message and a short reference id;
* the **log** carries the real cause, redacted, under that same reference id, so
  support can join a user report to a traceback without the user ever holding
  the details;
* a failure that happened mid-transaction rolls the session back, so nothing
  downstream inherits a session that can only raise.
"""
from __future__ import annotations

import re
import traceback
import uuid
from enum import StrEnum
from logging import Logger
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.observability import NO_REQUEST, current_request_id

#: Bumped only when a code is *removed* or its meaning changes. Adding a member
#: is backward compatible: a client that does not know a code falls back to the
#: status family, which is why every code below stays pinned to one status.
ERROR_CATALOG_VERSION = "1"


class ErrorCode(StrEnum):
    """The closed set of codes ``/api/v1`` may answer with.

    An enum rather than loose strings because these are a **contract**: the
    React client branches on them, so a typo in a route used to invent a new
    public code silently. Membership is now checkable, and the catalogue can be
    enumerated for the OpenAPI contract that TASK-043 pins.

    The human message beside a code may be reworded or translated at any time;
    the code may not.
    """

    # --- generic, one per status family the API answers with ---------------
    INTERNAL = "internal_error"
    INVALID_INPUT = "invalid_input"
    VALIDATION_FAILED = "validation_failed"
    #: The wire value TASK-042 already publishes from ``authRoute``. Kept as
    #: it is rather than renamed to "unauthenticated": it is public, a client
    #: may already branch on it, and this task changes shape, not contract.
    UNAUTHENTICATED = "not_authenticated"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    CONFLICT = "conflict"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "service_unavailable"

    # --- domain specific, kept from TASK-011 / TASK-032 --------------------
    QUESTIONNAIRE_PROFILE = "questionnaire_profile_unavailable"
    RESOURCE_FILE = "resource_file_unavailable"
    RESOURCE_STORAGE_UNCONFIGURED = "resource_storage_unavailable"
    RESUME_UPLOAD = "resume_upload_failed"
    RESUME_STORAGE_UNCONFIGURED = "resume_storage_unavailable"
    ADMIN_RESOURCE_INVALID = "admin_resource_invalid"
    ADMIN_RESOURCE_UPLOAD = "admin_resource_upload_failed"
    COMPANY_DASHBOARD = "company_dashboard_unavailable"
    STUDENT_DASHBOARD = "student_dashboard_unavailable"
    DASHBOARD_STATS = "dashboard_stats_unavailable"
    JOB_SEARCH = "job_search_unavailable"

    # --- cross-cutting guards, published before the catalogue existed -------
    # Same rule as UNAUTHENTICATED: the wire value is what TASK-041, TASK-042
    # and TASK-054 already answer with, so it is adopted verbatim rather than
    # renamed. Folding them in is what makes the catalogue the single source of
    # truth the Definition of Done asks for — before this they were five loose
    # strings in three modules.
    CSRF_TOKEN_INVALID = "csrf_token_invalid"
    IDEMPOTENCY_KEY_INVALID = "idempotency_key_invalid"
    IDEMPOTENCY_KEY_REUSE = "idempotency_key_reuse"
    IDEMPOTENCY_IN_PROGRESS = "idempotency_request_in_progress"
    INTERNAL_TASK_UNAUTHORIZED = "internal_task_unauthorized"


# The pre-existing names stay bound to the enum members, so the routes that
# TASK-011 and TASK-032 already migrated keep working unchanged. ``StrEnum``
# means they compare equal to the wire string they always had.
CODE_INTERNAL = ErrorCode.INTERNAL
CODE_QUESTIONNAIRE_PROFILE = ErrorCode.QUESTIONNAIRE_PROFILE
CODE_RESOURCE_FILE = ErrorCode.RESOURCE_FILE
CODE_RESOURCE_STORAGE_UNCONFIGURED = ErrorCode.RESOURCE_STORAGE_UNCONFIGURED
CODE_RESUME_UPLOAD = ErrorCode.RESUME_UPLOAD
CODE_RESUME_STORAGE_UNCONFIGURED = ErrorCode.RESUME_STORAGE_UNCONFIGURED
CODE_ADMIN_RESOURCE_INVALID = ErrorCode.ADMIN_RESOURCE_INVALID
CODE_ADMIN_RESOURCE_UPLOAD = ErrorCode.ADMIN_RESOURCE_UPLOAD
CODE_INVALID_INPUT = ErrorCode.INVALID_INPUT
CODE_COMPANY_DASHBOARD = ErrorCode.COMPANY_DASHBOARD
CODE_STUDENT_DASHBOARD = ErrorCode.STUDENT_DASHBOARD
CODE_DASHBOARD_STATS = ErrorCode.DASHBOARD_STATS
CODE_JOB_SEARCH = ErrorCode.JOB_SEARCH

#: What a bare ``HTTPException(status_code=...)`` becomes. The 119 raise sites
#: that predate the catalogue answer with the family code for their status
#: rather than being rewritten one by one: rewriting them would change which
#: operations fail, and this task is explicitly only about the *shape*.
_STATUS_CODES: dict[int, ErrorCode] = {
    400: ErrorCode.INVALID_INPUT,
    401: ErrorCode.UNAUTHENTICATED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    409: ErrorCode.CONFLICT,
    413: ErrorCode.PAYLOAD_TOO_LARGE,
    422: ErrorCode.VALIDATION_FAILED,
    429: ErrorCode.RATE_LIMITED,
    503: ErrorCode.UNAVAILABLE,
}


def code_for_status(status_code: int) -> ErrorCode:
    """The catalogue code a status maps to when no route named one."""
    if status_code in _STATUS_CODES:
        return _STATUS_CODES[status_code]
    return ErrorCode.INVALID_INPUT if status_code < 500 else ErrorCode.INTERNAL

GENERIC_CLIENT_MESSAGE = "The request could not be processed."
GENERIC_SERVER_MESSAGE = "Something went wrong on our side. Please try again."

# A client-facing validation sentence is short and prose-like. Anything that
# smells of machinery is replaced instead of forwarded: the point is that no
# path, query or DSN can reach a caller by riding on an exception message.
MAX_CLIENT_MESSAGE_LENGTH = 200
_UNSAFE_MESSAGE = re.compile(
    r"""(
        :// |                              # any URI, credentials or not
        \[SQL: | \bDETAIL:\s | \bHINT:\s | # SQLAlchemy / libpq error framing
        \b(select|insert\s+into|update|delete\s+from|create\s+table)\b\s |
        \b(sqlalchemy|asyncpg|psycopg\d*|aiobotocore|botocore|boto3|supabase|httpx|urllib3)\b |
        \b\w*(Error|Exception|Timeout)\b\s*[:)] |  # "(psycopg2.OperationalError) ..."
        \btraceback\b |
        (^|\s)[/~][\w.\-]+/ |              # filesystem path
        [A-Za-z]:\\\\ |                    # windows path
        \bpassword\b | \bsecret\b | \btoken\b | \bcredential
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# Redaction for what *is* written to the log. The reference id makes the entry
# findable; the value behind a credential never needs to be in it.
_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    # An Authorization value is a credential to the end of the line, scheme
    # word included, so it is masked whole rather than token by token.
    (re.compile(r"(?P<key>\bauthorization\b\s*[=:]\s*)\S.*", re.I), r"\g<key>***"),
    # scheme://user:secret@host  ->  scheme://user:***@host
    (re.compile(r"(?P<prefix>[a-z][a-z0-9+.\-]*://[^\s:/@]+:)[^\s@]+(?=@)", re.I), r"\g<prefix>***"),
    # key=value / key: value for anything credential-shaped
    (
        re.compile(
            r"(?P<key>\b[\w.\-]*?(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?key|"
            r"secret[_-]?key|token|authorization|auth|bearer|session[_-]?id|cookie)"
            r"\b\s*[=:]\s*)(?P<quote>['\"]?)(?P<value>[^\s'\",;)]+)",
            re.I,
        ),
        r"\g<key>\g<quote>***",
    ),
    # Bare bearer tokens and AWS-style key ids that appear without a label.
    (re.compile(r"\bBearer\s+[A-Za-z0-9._\-]+", re.I), "Bearer ***"),
    (re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"), r"\1***"),
)

MAX_LOGGED_CAUSE_CHARS = 4000


def new_error_reference() -> str:
    """The id shared by the response and the log entry.

    It is the **request** id whenever a request is in flight. Before TASK-040
    this minted a fresh id per error, so a caller quoting "ref: 9f3c..." sent
    support to the error line but not to the request line that carried the
    method, route, status and duration — two ids for one event, joinable only
    by timestamp. Outside a request (a worker, a startup hook, a test) there is
    no request id, so one is still minted here.
    """
    request_id = current_request_id()
    return request_id if request_id != NO_REQUEST else uuid.uuid4().hex[:12]


def redact(text: str) -> str:
    """Mask credential-shaped values in text destined for the log."""
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def is_safe_client_message(message: str) -> bool:
    """True when a validation message may be shown to the caller verbatim."""
    message = (message or "").strip()
    if not message or len(message) > MAX_CLIENT_MESSAGE_LENGTH:
        return False
    return not _UNSAFE_MESSAGE.search(message)


def _public_detail(message: str, reference: str) -> str:
    # ``detail`` stays a string: every client in this app reads it as one.
    return f"{message} (ref: {reference})"


def _http_error(status_code: int, code: str, message: str, reference: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=_public_detail(message, reference),
        headers={"X-Error-Code": code, "X-Error-Id": reference},
    )


def log_cause(
    logger: Logger,
    exc: BaseException,
    *,
    code: str,
    reference: str,
    context: str = "",
) -> None:
    """Record the real cause, redacted, under ``reference``.

    The traceback is formatted and redacted here rather than handed to
    ``exc_info``: the credential usually lives in the exception's own message,
    which the standard formatter would print untouched.
    """
    cause = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    cause = redact(cause)[:MAX_LOGGED_CAUSE_CHARS]
    logger.error(
        "request failed code=%s ref=%s%s\n%s",
        code,
        reference,
        f" context={redact(context)}" if context else "",
        cause,
    )


async def _rollback(session: AsyncSession | None, logger: Logger, reference: str) -> None:
    if session is None:
        return
    try:
        await session.rollback()
    except Exception:  # pragma: no cover - defensive: never mask the real cause
        logger.warning("rollback after failure ref=%s did not complete", reference)


async def server_failure(
    exc: BaseException,
    *,
    logger: Logger,
    code: str = CODE_INTERNAL,
    message: str = GENERIC_SERVER_MESSAGE,
    status_code: int = 500,
    session: AsyncSession | None = None,
    context: str = "",
) -> HTTPException:
    """Map an unexpected failure to a safe answer. ``raise await server_failure(...)``.

    Rolls ``session`` back first: after a failed statement the session can only
    raise, and the request is not finished with it (dependencies, background
    hooks and the commit at teardown all still run).
    """
    reference = new_error_reference()
    log_cause(logger, exc, code=code, reference=reference, context=context)
    await _rollback(session, logger, reference)
    return _http_error(status_code, code, message, reference)


async def client_failure(
    exc: BaseException,
    *,
    logger: Logger,
    code: str = CODE_INVALID_INPUT,
    status_code: int = 400,
    fallback_message: str = GENERIC_CLIENT_MESSAGE,
    session: AsyncSession | None = None,
) -> HTTPException:
    """4xx for a validation error the caller can act on.

    The author-written message is preserved — that is the existing contract —
    but only after it is checked: an exception type says nothing about where its
    text came from, and ``ValueError`` is raised by libraries too.
    """
    reference = new_error_reference()
    raw = str(exc)
    safe = is_safe_client_message(raw)
    if not safe:
        log_cause(logger, exc, code=code, reference=reference, context="unsafe client message")
    await _rollback(session, logger, reference)
    return _http_error(status_code, code, raw.strip() if safe else fallback_message, reference)


# --- The single public error shape -----------------------------------------
#
# §5.1 of the plan fixes one body for every failing ``/api/v1`` request:
#
#     {"error": {"code", "message", "details", "request_id"}}
#
# ``details`` is for machine-readable specifics — which field failed validation
# and why — never for a second prose message and never for a cause. It is
# ``None`` when there is nothing structured to say, rather than ``{}``, so
# "no details" and "empty details" cannot be confused by a client.


class AppError(Exception):
    """A failure whose public shape the raiser has already decided.

    Raising this is preferred over ``HTTPException`` for new code: the code is
    drawn from the catalogue instead of being inferred from the status, and
    ``details`` survives to the client. The central handler renders it.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int = 400,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def error_envelope(
    code: ErrorCode | str,
    message: str,
    *,
    request_id: str | None = None,
    details: Any | None = None,
) -> dict[str, Any]:
    """Build the one body shape. The only place that spells these keys."""
    if request_id is None or request_id == NO_REQUEST:
        request_id = new_error_reference()
    return {
        "error": {
            "code": str(code),
            "message": message,
            "details": details,
            "request_id": request_id,
        }
    }
