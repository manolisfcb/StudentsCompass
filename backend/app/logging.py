"""Logging setup: every line carries the request it belongs to, in the shape
whoever is reading can actually query.

The format gained ``request_id`` in TASK-028. It is filled by a log record
factory rather than by each call site or by a per-handler filter, so a handler
added later — pytest's ``caplog``, a JSON handler, a library's own — still
produces records the format can render. A line logged outside a request says
``-``.

TASK-045 adds the JSON rendering Cloud Run needs. Cloud Logging parses a JSON
object on stdout into a structured entry: ``severity`` becomes the level you can
filter on, ``message`` becomes the summary line, and every other key becomes a
field you can query. Printed as text, the same information is one string that
can only be grepped — which is the difference between "show me the 500s for this
actor" and reading a log.

Text stays the default outside production because a developer reads these lines
directly, and JSON is unreadable at that size.
"""
import json
import logging

from app.core.observability import install_request_id_log_factory

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [req %(request_id)s] %(message)s"

#: Python's level names are already what Cloud Logging calls severities, with
#: one exception: it has no WARN and no FATAL.
_SEVERITY = {
    "WARN": "WARNING",
    "FATAL": "CRITICAL",
}

#: Attributes ``logging`` puts on every record. Anything *not* here was passed
#: by a call site through ``extra=`` and is therefore a field worth emitting.
_STANDARD_RECORD_FIELDS = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | {"asctime", "message", "request_id", "taskName"}


class CloudLoggingFormatter(logging.Formatter):
    """One JSON object per line, with the extras as real fields.

    Fields come from ``extra=`` rather than from a fixed list so that a call
    site that has something worth recording does not have to be anticipated
    here. What must never arrive this way is PII: the request line passes a
    pseudonymous actor and a route *template*, and the redaction that free text
    goes through lives in ``app.core.errors``, not in the formatter — a
    formatter that scrubbed would be a second, quieter place to get it wrong.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "severity": _SEVERITY.get(record.levelname, record.levelname),
            "message": record.getMessage(),
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
        }

        if record.exc_info:
            # Under its own key rather than appended to the message, so the
            # summary stays one line and the traceback stays readable.
            payload["exception"] = self.formatException(record.exc_info)

        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_FIELDS or key in payload:
                continue
            payload[key] = value if isinstance(value, (str, int, float, bool, type(None))) else str(value)

        # default=str so a stray non-serialisable value degrades to its repr
        # instead of taking down the log line that was reporting the problem.
        return json.dumps(payload, default=str)


def _json_logs_enabled() -> bool:
    # Imported here rather than at module import: app.config loads .env, and
    # this module is imported early enough that the order matters.
    from app.config import IS_PRODUCTION, env_flag

    return env_flag("JSON_LOGS", "1" if IS_PRODUCTION else "0")


def setup_logging():
    install_request_id_log_factory()
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    if _json_logs_enabled():
        formatter = CloudLoggingFormatter()
        for handler in logging.getLogger().handlers:
            handler.setFormatter(formatter)

    return logging.getLogger(__name__)


logger = setup_logging()
