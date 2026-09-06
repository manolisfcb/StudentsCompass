"""The harness itself is a control: if it stops isolating, everything downstream
is untrustworthy. These tests pin the three guarantees of tests/isolation.py.
"""
from __future__ import annotations

import os
import socket

import pytest

from tests.isolation import ExternalConnectionBlocked, assert_local_url


def test_dotenv_is_disabled_so_real_credentials_never_load():
    import dotenv

    assert dotenv.load_dotenv() is False
    assert dotenv.find_dotenv() == ""


def test_credentials_are_obvious_placeholders():
    for name in ("GENAI_API_KEY", "AWS_SECRET_ACCESS_KEY", "SECRET_KEY"):
        value = os.environ[name]
        assert value.startswith("test-"), f"{name} is not the harness placeholder"


def test_redis_url_is_empty_in_the_fast_lane():
    """The fast lane must use the in-memory counter store, not a real server."""
    assert os.environ["REDIS_URL"] == ""


def test_outbound_connection_to_external_host_is_blocked():
    with pytest.raises(ExternalConnectionBlocked):
        socket.create_connection(("example.com", 80), timeout=1)

    with pytest.raises(ExternalConnectionBlocked):
        sock = socket.socket()
        sock.connect(("93.184.216.34", 443))


def test_loopback_stays_reachable_for_disposable_services():
    """Blocking must not break SQLite, the ASGI transport or the test lanes."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    try:
        client = socket.create_connection(listener.getsockname(), timeout=1)
        client.close()
    finally:
        listener.close()


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://user:pw@db.example.com:5432/prod",
        "redis://cache.internal.example.com:6379/0",
    ],
)
def test_non_local_lane_url_is_rejected(url):
    """A stale env var must not aim the integration lane at a real deployment."""
    with pytest.raises(ExternalConnectionBlocked):
        assert_local_url(url, setting="TEST_DATABASE_URL_PG")


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://testuser:testpw@127.0.0.1:55432/studentscompass_test",
        "redis://localhost:56379/0",
    ],
)
def test_local_lane_url_is_accepted(url):
    assert assert_local_url(url, setting="TEST_DATABASE_URL_PG") == url


@pytest.mark.asyncio
async def test_query_counter_measures_statements(query_counter, db_session):
    """Query budgets for later tasks are expressed with this counter."""
    from sqlalchemy import text

    with query_counter() as counted:
        await db_session.execute(text("SELECT 1"))
        await db_session.execute(text("SELECT 2"))

    assert counted.selects == 2
    assert counted.writes == 0
    assert counted.matching("select 2")


@pytest.mark.asyncio
async def test_two_session_harness_yields_distinct_sessions(two_db_sessions):
    first, second = two_db_sessions
    assert first is not second
