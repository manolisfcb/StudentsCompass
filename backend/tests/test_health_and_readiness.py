"""Liveness, readiness, and the log shape Cloud Run reads (TASK-045).

The distinction under test is the one that decides whether an outage is
recoverable: ``/healthz`` must keep answering while the database is down —
otherwise the platform restarts every container and a database outage becomes a
total one — and ``/readyz`` must stop answering, so the revision leaves the load
balancer instead of serving errors.

The rest is about what the log line says: structured fields rather than one
string, a pseudonymous actor rather than a user id, and nothing that identifies
a person.
"""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager

import pytest

from app.app import app
from app.core.health import database_ready
from app.core.observability import NO_ACTOR, anonymize_actor, stamp_actor, stamp_job
from app.db import get_session
from app.logging import CloudLoggingFormatter


class _SessionThatFails:
    """A session standing in for a database that is not answering."""

    def __init__(self, error: BaseException):
        self._error = error

    async def execute(self, *_args, **_kwargs):
        raise self._error


class _SessionThatHangs:
    async def execute(self, *_args, **_kwargs):
        import asyncio

        await asyncio.sleep(30)


@contextmanager
def _database_that(session):
    """Serve the readiness probe from a stand-in session for one test."""
    previous = app.dependency_overrides.get(get_session)

    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    try:
        yield
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_session, None)
        else:
            app.dependency_overrides[get_session] = previous


class TestLivenessIsIndependentOfEverything:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("path", ["/health", "/healthz"])
    async def test_healthz_answers_ok(self, client, path):
        response = await client.get(path)

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    @pytest.mark.parametrize("path", ["/health", "/healthz"])
    async def test_healthz_still_answers_when_the_database_is_down(self, client, path):
        """The point of separating the two probes.

        A liveness check that touched the database would fail here, the platform
        would kill the container, and the replacement would fail identically —
        turning a recoverable outage into a restart loop with nothing left
        running to recover.
        """
        with _database_that(_SessionThatFails(OSError("connection refused"))):
            response = await client.get(path)

        assert response.status_code == 200


class TestReadinessFollowsTheDatabase:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("path", ["/ready", "/readyz"])
    async def test_readyz_is_ready_when_the_database_answers(self, client, path):
        response = await client.get(path)

        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("path", ["/ready", "/readyz"])
    async def test_readyz_refuses_traffic_when_the_database_is_unavailable(self, client, path):
        with _database_that(_SessionThatFails(OSError("connection refused"))):
            response = await client.get(path)

        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("path", ["/ready", "/readyz"])
    async def test_readyz_leaks_no_infrastructure_detail(self, client, path):
        """The probe is reachable from the internet.

        A driver error names the host, the port and often the user, so the
        reason goes to the log and the caller gets a word.
        """
        leaky = OSError(
            "could not connect to server: ep-broad-mud.eu-central-1.aws.neon.tech:5432 user=sc_prod"
        )

        with _database_that(_SessionThatFails(leaky)):
            response = await client.get(path)

        assert response.status_code == 503
        body = response.text
        for leak in ("neon.tech", "5432", "sc_prod", "could not connect"):
            assert leak not in body, f"the probe leaked {leak!r}"

    @pytest.mark.asyncio
    async def test_a_hanging_database_times_out_rather_than_hanging_the_probe(self):
        """A probe that waits forever is a probe whose result is never read."""
        ready = await database_ready(_SessionThatHangs(), timeout=0.05)

        assert ready is False


class TestTheActorIsPseudonymousAndStable:
    def test_the_same_actor_hashes_to_the_same_string(self):
        first = anonymize_actor("student", "9f3c1a2b-0000-4000-8000-000000000001")
        second = anonymize_actor("student", "9f3c1a2b-0000-4000-8000-000000000001")

        assert first == second

    def test_different_actors_do_not_collide(self):
        one = anonymize_actor("student", "user-1")
        two = anonymize_actor("student", "user-2")

        assert one != two

    def test_the_user_id_never_appears_in_the_pseudonym(self):
        user_id = "9f3c1a2b-0000-4000-8000-000000000001"

        stamped = anonymize_actor("student", user_id)

        assert user_id not in stamped
        assert stamped.startswith("student:")

    def test_the_two_identities_are_distinguishable_without_being_identifiable(self):
        """Same underlying id, different kind: the kinds must not alias."""
        assert anonymize_actor("student", "1") != anonymize_actor("recruiter", "1")

    def test_stamping_survives_being_written_through_a_request_scope(self):
        scope = {"type": "http"}

        stamp_actor(scope, "student", "user-1")
        stamp_job(scope, "job-42")

        assert scope["state"]["actor"] == anonymize_actor("student", "user-1")
        assert scope["state"]["job_id"] == "job-42"


class TestTheLogLineIsQueryable:
    def _render(self, **fields):
        record = logging.LogRecord(
            "app.request", logging.INFO, __file__, 1, "request", None, None
        )
        record.request_id = "abc123"
        for key, value in fields.items():
            setattr(record, key, value)
        return json.loads(CloudLoggingFormatter().format(record))

    def test_severity_is_what_cloud_logging_filters_on(self):
        assert self._render()["severity"] == "INFO"

    def test_extras_become_fields_rather_than_a_string(self):
        payload = self._render(
            method="GET", endpoint="/api/v1/jobs", status=200, duration_ms=12.5
        )

        assert payload["endpoint"] == "/api/v1/jobs"
        assert payload["status"] == 200
        assert payload["duration_ms"] == 12.5

    def test_the_request_id_is_carried_so_a_report_and_a_line_can_be_joined(self):
        assert self._render()["request_id"] == "abc123"

    def test_the_line_is_one_json_object_per_line(self):
        record = logging.LogRecord(
            "app.request", logging.INFO, __file__, 1, "request", None, None
        )
        record.request_id = "abc123"

        rendered = CloudLoggingFormatter().format(record)

        assert "\n" not in rendered
        json.loads(rendered)

    @pytest.mark.asyncio
    async def test_an_unauthenticated_request_names_no_actor(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="app.request"):
            await client.get("/healthz")

        line = next(r for r in caplog.records if r.name == "app.request")
        assert getattr(line, "actor") == NO_ACTOR

    @pytest.mark.asyncio
    async def test_the_line_carries_the_route_template_not_the_path(self, client, caplog):
        """A path carries ids; a template aggregates and names nobody."""
        with caplog.at_level(logging.INFO, logger="app.request"):
            await client.get("/healthz")

        line = next(r for r in caplog.records if r.name == "app.request")
        assert getattr(line, "endpoint") == "/healthz"
