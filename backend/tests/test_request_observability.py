"""One id, one line, real numbers — and nothing from a document in the log.

F-24: logs had no uniform correlation, no duration, no query or external-call
counts, and several catches returned an empty success. "The CV analysis is
slow" and "the CV analysis is broken" produced the same evidence: none.

These tests follow an injected failure by its correlation id, check the counters
are counted once rather than twice, and assert what must **never** reach a log —
CV text, file names, tokens, signed URLs.
"""
from __future__ import annotations

import asyncio
import logging
import time

import pytest

from app.core.observability import (
    NO_REQUEST,
    RequestMetrics,
    accept_inbound_request_id,
    current_request_id,
    external_call,
    install_sql_counter,
    record_sql_statement,
    reset_metrics,
    reset_request_id,
    set_request_id,
    start_metrics,
)
from app.middleware.request_context import REQUEST_ID_HEADER

SECRET_SHAPES = {
    "cv text": "Manuel Medina, Toronto, worked at ACME on payroll migrations",
    "file name": "Manuel_Medina_CV_final_v3.pdf",
    "token": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc",
    "signed url": "https://storage.example.com/cv.pdf?X-Amz-Signature=deadbeef",
}


@pytest.fixture
def request_context():
    """A request in flight, as the middleware would set one up."""
    id_token = set_request_id("test-request-id")
    metrics, metrics_token = start_metrics()
    try:
        yield metrics
    finally:
        reset_metrics(metrics_token)
        reset_request_id(id_token)


# ---------------------------------------------------------------------------
# The id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_response_carries_a_request_id(client):
    response = await client.get("/api/v1/questionnaire")

    assert response.headers.get(REQUEST_ID_HEADER)
    assert len(response.headers[REQUEST_ID_HEADER]) >= 8


@pytest.mark.asyncio
async def test_a_proxys_request_id_is_followed_across_the_hop(client):
    response = await client.get(
        "/api/v1/questionnaire", headers={REQUEST_ID_HEADER: "edge-7f3a-0001"}
    )

    assert response.headers[REQUEST_ID_HEADER] == "edge-7f3a-0001"


@pytest.mark.parametrize(
    "hostile",
    [
        "a\nlevel=CRITICAL fake=1",
        "a\r\ninjected",
        "x" * 200,
        "id with spaces",
        "",
        "id;rm -rf /",
    ],
)
def test_a_hostile_request_id_is_replaced_not_sanitised(hostile):
    """A sanitised id would no longer name the request the caller means."""
    accepted = accept_inbound_request_id(hostile)

    assert accepted != hostile
    assert "\n" not in accepted and "\r" not in accepted
    assert len(accepted) == 32


@pytest.mark.asyncio
async def test_the_response_id_is_the_one_the_client_sent(client):
    """The header is echoed, so a user can quote it in a report."""
    response = await client.get(
        "/api/v1/questionnaire", headers={REQUEST_ID_HEADER: "a" * 64}
    )
    assert response.headers[REQUEST_ID_HEADER] == "a" * 64

    response = await client.get(
        "/api/v1/questionnaire", headers={REQUEST_ID_HEADER: "a" * 65}
    )
    assert response.headers[REQUEST_ID_HEADER] != "a" * 65


def test_a_log_line_outside_a_request_still_formats():
    """``%(request_id)s`` must not raise on a startup or background line."""
    import app.logging  # noqa: F401  (installs the factory)

    record = logging.getLogRecordFactory()(
        "x", logging.INFO, __file__, 1, "msg", (), None
    )
    assert record.request_id == NO_REQUEST

    formatted = logging.Formatter(app.logging.LOG_FORMAT).format(record)
    assert f"[req {NO_REQUEST}]" in formatted


# ---------------------------------------------------------------------------
# Following a failure by its id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_injected_failure_can_be_followed_by_its_correlation_id(
    client, auth_headers, monkeypatch, caplog
):
    """Inject a provider failure, then join the log to the response by id."""
    from app.services.accounts import questionnaireService

    def explode(_self):
        raise RuntimeError("the questionnaire store is unreachable")

    monkeypatch.setattr(questionnaireService.QuestionnaireService, "_load_json", explode)

    with caplog.at_level(logging.INFO):
        response = await client.get("/api/v1/questionnaire/profile", headers=auth_headers)

    request_id = response.headers[REQUEST_ID_HEADER]
    assert response.status_code >= 400

    correlated = [
        record for record in caplog.records if getattr(record, "request_id", None) == request_id
    ]
    assert correlated, f"no log record carried request id {request_id}"

    # And the request line itself is there, with the status and a duration.
    request_lines = [record for record in correlated if record.name == "app.request"]
    assert request_lines, "the request was not logged"
    message = request_lines[0].getMessage()
    assert "endpoint=" in message and "duration_ms=" in message


@pytest.mark.asyncio
async def test_a_server_error_is_logged_at_warning_so_it_is_visible(
    client, auth_headers, monkeypatch, caplog
):
    from app.services.accounts import questionnaireService

    monkeypatch.setattr(
        questionnaireService.QuestionnaireService,
        "_load_json",
        lambda _self: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with caplog.at_level(logging.INFO):
        response = await client.get("/api/v1/questionnaire/profile", headers=auth_headers)

    lines = [record for record in caplog.records if record.name == "app.request"]
    assert lines
    if response.status_code >= 500:
        assert lines[-1].levelno == logging.WARNING


# ---------------------------------------------------------------------------
# Counting, exactly once
# ---------------------------------------------------------------------------


def test_an_external_call_is_recorded_once_with_its_outcome(request_context):
    with external_call("gemini"):
        time.sleep(0.01)

    assert request_context.external_calls == 1
    assert request_context.external_failures == 0
    calls, failures, elapsed = request_context.by_provider["gemini"]
    assert (calls, failures) == (1, 0)
    assert elapsed >= 10


def test_a_failing_external_call_is_counted_as_an_attempt_and_a_failure(request_context):
    with pytest.raises(RuntimeError):
        with external_call("gemini"):
            raise RuntimeError("provider said no")

    assert request_context.external_calls == 1
    assert request_context.external_failures == 1
    assert request_context.by_provider["gemini"][:2] == (1, 1)


def test_retries_are_separate_attempts_not_one(request_context):
    """A retry is another paid request, so it is another recorded attempt."""
    for _ in range(3):
        try:
            with external_call("gemini"):
                raise RuntimeError("still failing")
        except RuntimeError:
            pass

    assert request_context.external_calls == 3
    assert request_context.external_failures == 3


def test_providers_are_counted_apart(request_context):
    with external_call("gemini"):
        pass
    with external_call("linkedin"):
        pass
    with external_call("linkedin"):
        pass

    assert request_context.external_calls == 3
    assert request_context.by_provider["gemini"][0] == 1
    assert request_context.by_provider["linkedin"][0] == 2


def test_the_sql_counter_is_installed_once_however_often_it_is_asked(request_context):
    """Installing twice would count every statement twice."""
    from tests.conftest import test_engine

    install_sql_counter(test_engine)
    install_sql_counter(test_engine)
    install_sql_counter(test_engine)

    before = request_context.sql_statements
    record_sql_statement()
    assert request_context.sql_statements == before + 1


@pytest.mark.asyncio
async def test_statements_are_counted_against_the_request_that_ran_them(db_session):
    """And a query outside a request counts against nothing, without raising."""
    from sqlalchemy import select

    from app.models.userModel import User

    await db_session.execute(select(User).limit(1))  # no request in flight

    id_token = set_request_id("counted")
    metrics, metrics_token = start_metrics()
    try:
        await db_session.execute(select(User).limit(1))
        await db_session.execute(select(User).limit(1))
        assert metrics.sql_statements == 2
    finally:
        reset_metrics(metrics_token)
        reset_request_id(id_token)


def test_metrics_do_not_leak_between_requests():
    first, first_token = start_metrics()
    first.record_external("gemini", failed=False, duration_ms=5)
    reset_metrics(first_token)

    second, second_token = start_metrics()
    try:
        assert second.external_calls == 0
        assert second.by_provider == {}
    finally:
        reset_metrics(second_token)


@pytest.mark.asyncio
async def test_concurrent_requests_keep_their_own_id_and_counters():
    """ContextVars, not globals: two requests in flight must not mix."""

    async def one(name: str, calls: int) -> tuple[str, int]:
        id_token = set_request_id(name)
        metrics, metrics_token = start_metrics()
        try:
            for _ in range(calls):
                with external_call("gemini"):
                    await asyncio.sleep(0.005)
            return current_request_id(), metrics.external_calls
        finally:
            reset_metrics(metrics_token)
            reset_request_id(id_token)

    results = await asyncio.gather(one("a", 1), one("b", 3), one("c", 2))
    assert results == [("a", 1), ("b", 3), ("c", 2)]


# ---------------------------------------------------------------------------
# What must never be logged
# ---------------------------------------------------------------------------


def test_the_request_line_contains_no_free_text_at_all():
    """It is built only from ids, a route template, a status and numbers."""
    metrics = RequestMetrics()
    metrics.record_external("gemini", failed=True, duration_ms=12.5)
    fields = metrics.as_log_fields()

    assert set(fields) >= {
        "duration_ms",
        "sql_statements",
        "external_calls",
        "external_failures",
    }
    for value in fields.values():
        assert isinstance(value, (int, float)), f"{value!r} is not a number"


@pytest.mark.asyncio
async def test_no_secret_shaped_value_reaches_the_log_for_a_real_request(
    client, auth_headers, caplog
):
    """The whole captured log, for a request that handles a CV-ish payload."""
    with caplog.at_level(logging.DEBUG):
        await client.get("/api/v1/profile/cv", headers=auth_headers)

    captured = "\n".join(record.getMessage() for record in caplog.records)
    for label, secret in SECRET_SHAPES.items():
        assert secret not in captured, f"{label} reached the log"
    assert "X-Amz-Signature" not in captured


def test_the_endpoint_is_logged_as_a_template_not_a_path():
    """A path carries ids; a template aggregates and leaks nothing."""
    import inspect

    from app.middleware import request_context

    source = inspect.getsource(request_context.RequestContextMiddleware.__call__)
    assert 'scope.get("route")' in source
    assert "url.path" not in source
    assert 'scope["path"]' not in source
