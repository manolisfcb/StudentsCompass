"""Correlation and counters for the flows that can fail slowly or silently.

F-24: logs had no uniform correlation, no duration, no query or external-call
counts, and several catches returned an empty success. So "the CV analysis is
slow" and "the CV analysis is broken" produced the same evidence — none.

What this module adds, and deliberately no more:

* a **request id** carried in a ``ContextVar``, stamped on every log record, and
  returned to the caller so a user report and a log line can be joined;
* per-request **duration**, **SQL statement count** and **external call count**,
  emitted once at the end of the request rather than per row or per statement;
* a way to record an external attempt with its outcome and duration, so a
  provider that is failing looks different from one that is slow.

It is not tracing. There are no spans, no exporter and no per-row logging: the
task's own scope rules that out, and TASK-045 is what shapes these fields for
Cloud Run. One telemetry, not two.

**Nothing here logs a value that came from a document.** CV text, file names,
tokens and signed URLs are excluded by construction: the only strings this
module writes are ids it generated, a route template, a provider name and an
outcome word. Free text that reaches a log elsewhere goes through
``app.core.errors.redact`` — this module reuses it rather than growing a second
redaction.
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

#: A request id is echoed into logs and headers, so it must not be able to carry
#: anything but its own identity: no newlines (log injection), no unbounded
#: length, no control characters.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")

#: The value used when no request is in flight — a background job, a test, a
#: module imported at startup. Named rather than blank so a log line without
#: correlation is obvious instead of looking truncated.
NO_REQUEST = "-"

_request_id: ContextVar[str] = ContextVar("request_id", default=NO_REQUEST)


@dataclass
class RequestMetrics:
    """What one request cost. Reset per request, emitted once at the end."""

    started_at: float = field(default_factory=time.perf_counter)
    sql_statements: int = 0
    external_calls: int = 0
    external_failures: int = 0
    #: ``provider -> (calls, failures, milliseconds)``. Providers are names this
    #: code chose, never anything a caller supplied.
    by_provider: dict[str, tuple[int, int, float]] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        return (time.perf_counter() - self.started_at) * 1000

    def record_external(self, provider: str, *, failed: bool, duration_ms: float) -> None:
        self.external_calls += 1
        if failed:
            self.external_failures += 1
        calls, failures, elapsed = self.by_provider.get(provider, (0, 0, 0.0))
        self.by_provider[provider] = (
            calls + 1,
            failures + (1 if failed else 0),
            elapsed + duration_ms,
        )

    def as_log_fields(self) -> dict:
        fields = {
            "duration_ms": round(self.duration_ms, 2),
            "sql_statements": self.sql_statements,
            "external_calls": self.external_calls,
            "external_failures": self.external_failures,
        }
        for provider, (calls, failures, elapsed) in sorted(self.by_provider.items()):
            fields[f"provider.{provider}.calls"] = calls
            fields[f"provider.{provider}.failures"] = failures
            fields[f"provider.{provider}.ms"] = round(elapsed, 2)
        return fields


_metrics: ContextVar[RequestMetrics | None] = ContextVar("request_metrics", default=None)


def new_request_id() -> str:
    return uuid.uuid4().hex


def accept_inbound_request_id(value: str | None) -> str:
    """Reuse a caller's id only if it is safe to echo, otherwise mint one.

    A proxy that already assigned an id is worth following across the hop. A
    client that sends ``X-Request-ID: foo\\nlevel=CRITICAL`` is not: the value
    ends up in a log line, so anything but a short, plain token is replaced
    rather than sanitised, because a *sanitised* id no longer identifies the
    request the caller thinks it does.
    """
    if value and _SAFE_REQUEST_ID.match(value):
        return value
    return new_request_id()


def current_request_id() -> str:
    return _request_id.get()


def set_request_id(value: str):
    return _request_id.set(value)


def reset_request_id(token) -> None:
    _request_id.reset(token)


def current_metrics() -> RequestMetrics | None:
    return _metrics.get()


def start_metrics() -> tuple[RequestMetrics, object]:
    metrics = RequestMetrics()
    return metrics, _metrics.set(metrics)


def reset_metrics(token) -> None:
    _metrics.reset(token)


def record_sql_statement() -> None:
    """One statement executed. Counted at the driver, so retries count too."""
    metrics = _metrics.get()
    if metrics is not None:
        metrics.sql_statements += 1


@contextmanager
def external_call(provider: str):
    """Time one call to something outside this process, and record its outcome.

    Counted **once**, here, at the boundary. A caller that also incremented a
    counter of its own would double count, which is the thing the task's
    validation asks about; the rule is that the ``with`` block is the only place
    an external attempt is recorded.
    """
    started = time.perf_counter()
    failed = False
    try:
        yield
    except BaseException:
        failed = True
        raise
    finally:
        metrics = _metrics.get()
        if metrics is not None:
            metrics.record_external(
                provider, failed=failed, duration_ms=(time.perf_counter() - started) * 1000
            )


def install_request_id_log_factory() -> None:
    """Stamp the current request id on every record, wherever it is created.

    A ``logging.Filter`` would have to be attached to each handler, and a
    handler added later — pytest's ``caplog``, a JSON handler in TASK-045, a
    library's own — would produce records without the attribute and
    ``%(request_id)s`` would raise on them. The record factory is the one place
    every record passes through, so the attribute always exists.

    Idempotent: installing twice would chain the factory onto itself.
    """
    global _previous_factory
    if _previous_factory is not None:
        return

    _previous_factory = logging.getLoggerClass() and logging.getLogRecordFactory()
    previous = _previous_factory

    def factory(*args, **kwargs):
        record = previous(*args, **kwargs)
        record.request_id = current_request_id()
        return record

    logging.setLogRecordFactory(factory)


_previous_factory = None


def install_sql_counter(engine) -> None:
    """Count statements on ``engine`` into whatever request is in flight.

    Attached to the driver-level event rather than to the ORM so that raw SQL,
    the ORM's own flushes and a retried statement all count once each — which is
    what "how many round trips did this request make" means.
    """
    from sqlalchemy import event

    sync_engine = getattr(engine, "sync_engine", engine)

    if getattr(sync_engine, "_sc_sql_counter_installed", False):
        # Installing twice would count every statement twice, which is exactly
        # the double counting this task has to avoid.
        return

    def before_cursor_execute(_conn, _cursor, _statement, _parameters, _context, _executemany):
        record_sql_statement()

    event.listen(sync_engine, "before_cursor_execute", before_cursor_execute)
    sync_engine._sc_sql_counter_installed = True
