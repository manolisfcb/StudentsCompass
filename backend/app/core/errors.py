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
from logging import Logger

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# Stable machine-readable codes. Clients may branch on these; the human message
# beside them may be reworded at any time.
CODE_INTERNAL = "internal_error"
CODE_QUESTIONNAIRE_PROFILE = "questionnaire_profile_unavailable"
CODE_RESOURCE_FILE = "resource_file_unavailable"
CODE_RESOURCE_STORAGE_UNCONFIGURED = "resource_storage_unavailable"
CODE_RESUME_UPLOAD = "resume_upload_failed"
CODE_RESUME_STORAGE_UNCONFIGURED = "resume_storage_unavailable"
CODE_ADMIN_RESOURCE_INVALID = "admin_resource_invalid"
CODE_ADMIN_RESOURCE_UPLOAD = "admin_resource_upload_failed"
CODE_INVALID_INPUT = "invalid_input"

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
    """Short id shared by the response and the log entry."""
    return uuid.uuid4().hex[:12]


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
