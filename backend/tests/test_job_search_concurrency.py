"""A slow provider must cost its own request, not the worker it runs on.

``JobSearchService.search`` awaited ``fetch_linkedin_jobs`` directly, and that
function is ``requests.get`` and ``time.sleep`` in a paging loop. Awaiting a
blocking call does not yield: the event loop sat inside it, so one search
against a slow LinkedIn stalled every other request sharing the process —
health checks and dashboard reads included.

These tests measure that from the outside: how far behind a 10 ms ticker falls
while a 2 s search is in flight. On the blocking implementation the ticker
simply stops. They never touch the real site; the provider is always a fake.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from app.services.jobs.jobSearchService import (
    JobSearchQuery,
    JobSearchService,
    OffloadRejected,
    BoundedOffload,
    SCRAPER_MAX_QUEUED,
    SCRAPER_MAX_WORKERS,
)

PROVIDER_LATENCY_SECONDS = 2.0
TICK_INTERVAL = 0.01


class _FakeJob:
    """The scraper's dataclass shape, without importing the scraper."""

    def __init__(self, index: int):
        self.title = f"External Role {index}"
        self.company = "Example Corp"
        self.location = "Toronto, ON"
        self.url = f"https://linkedin.example/jobs/{index}"
        self.listed_at = "2026-09-08"


def _slow_provider(latency=PROVIDER_LATENCY_SECONDS, results=1, record=None):
    """A blocking provider, exactly like the real one: it sleeps in a thread."""

    def provider(**kwargs):
        if record is not None:
            record.append(kwargs)
        time.sleep(latency)
        return [_FakeJob(index) for index in range(results)]

    return provider


async def _measure_loop_lag(stop: asyncio.Event) -> float:
    """Worst delay a 10 ms ticker sees while something else is running."""
    worst = 0.0
    while not stop.is_set():
        started = time.perf_counter()
        await asyncio.sleep(TICK_INTERVAL)
        worst = max(worst, time.perf_counter() - started - TICK_INTERVAL)
    return worst


@pytest.mark.asyncio
async def test_a_two_second_provider_does_not_stall_other_requests(
    db_session, monkeypatch
):
    monkeypatch.setattr(
        "app.services.jobs.jobSearchService.fetch_linkedin_jobs", _slow_provider()
    )
    service = JobSearchService(db_session)
    stop = asyncio.Event()
    ticker = asyncio.create_task(_measure_loop_lag(stop))

    started = time.perf_counter()
    payload = await service.search(
        JobSearchQuery(keywords="python", location="Toronto", limit=10)
    )
    elapsed = time.perf_counter() - started

    stop.set()
    worst_lag = await ticker

    assert len(payload["linkedin"]) == 1
    assert elapsed >= PROVIDER_LATENCY_SECONDS
    # The search really did take two seconds; the loop did not.
    assert worst_lag < 0.5, f"event loop blocked for {worst_lag:.3f}s"


@pytest.mark.asyncio
async def test_a_light_request_finishes_while_a_slow_search_is_in_flight(
    db_session, monkeypatch
):
    """The point of the whole task, stated as a race."""
    monkeypatch.setattr(
        "app.services.jobs.jobSearchService.fetch_linkedin_jobs", _slow_provider()
    )
    service = JobSearchService(db_session)

    async def light_request():
        await asyncio.sleep(0.05)
        return time.perf_counter()

    search = asyncio.create_task(
        service.search(JobSearchQuery(keywords="python", location="Toronto", limit=10))
    )
    light_finished_at = await light_request()
    assert not search.done()

    await search
    search_finished_at = time.perf_counter()

    assert search_finished_at - light_finished_at > 1.0


@pytest.mark.asyncio
async def test_the_provider_receives_the_normalised_limit(db_session, monkeypatch):
    """The internal search was capped at 100; the provider was not."""
    seen: list[dict] = []
    monkeypatch.setattr(
        "app.services.jobs.jobSearchService.fetch_linkedin_jobs",
        _slow_provider(latency=0, record=seen),
    )
    service = JobSearchService(db_session)

    await service.search(JobSearchQuery(keywords="python", location="Toronto", limit=5000))
    await service.search(JobSearchQuery(keywords="python", location="Toronto", limit=0))

    assert [call["limit"] for call in seen] == [100, 1]
    assert all(call["budget_seconds"] is not None for call in seen)


@pytest.mark.asyncio
async def test_a_provider_timeout_returns_the_internal_results(db_session, monkeypatch):
    """Timing out costs the LinkedIn half, not the search."""
    monkeypatch.setattr(
        "app.services.jobs.jobSearchService.fetch_linkedin_jobs", _slow_provider(latency=5)
    )
    monkeypatch.setattr("app.services.jobs.jobSearchService.SCRAPER_TIMEOUT_SECONDS", 0.2)
    service = JobSearchService(db_session)

    started = time.perf_counter()
    payload = await service.search(
        JobSearchQuery(keywords="python", location="Toronto", limit=10)
    )
    elapsed = time.perf_counter() - started

    assert payload["linkedin"] == []
    assert "students_compass" in payload
    assert elapsed < 2.0, "the caller waited for the abandoned thread"


@pytest.mark.asyncio
async def test_a_failing_provider_does_not_fail_the_search(db_session, monkeypatch):
    def exploding(**_kwargs):
        raise RuntimeError("LinkedIn changed its markup again")

    monkeypatch.setattr(
        "app.services.jobs.jobSearchService.fetch_linkedin_jobs", exploding
    )
    payload = await JobSearchService(db_session).search(
        JobSearchQuery(keywords="python", location="Toronto", limit=10)
    )

    assert payload["linkedin"] == []


@pytest.mark.asyncio
async def test_the_queue_is_bounded_and_sheds_instead_of_growing():
    """Past capacity the work is refused, not queued."""
    offload = BoundedOffload(max_workers=1, max_queued=1, thread_name_prefix="test-pool")

    release = asyncio.Event()
    loop = asyncio.get_running_loop()

    def blocking():
        # Held until the test lets go, so the two slots stay occupied.
        asyncio.run_coroutine_threadsafe(_wait(release), loop).result(timeout=10)
        return "done"

    async def _wait(event):
        await event.wait()

    accepted = [
        asyncio.create_task(offload.run(blocking, timeout=10)),
        asyncio.create_task(offload.run(blocking, timeout=10)),
    ]
    await asyncio.sleep(0.05)
    assert offload.in_flight == 2

    with pytest.raises(OffloadRejected):
        await offload.run(blocking, timeout=10)

    release.set()
    assert await asyncio.gather(*accepted) == ["done", "done"]
    await asyncio.sleep(0.05)
    assert offload.in_flight == 0


@pytest.mark.asyncio
async def test_a_timed_out_call_does_not_hand_its_slot_back_early():
    """A stream of timeouts must not hand out unlimited slots."""
    offload = BoundedOffload(max_workers=2, max_queued=0, thread_name_prefix="test-pool")
    release = asyncio.Event()
    loop = asyncio.get_running_loop()

    def blocking():
        asyncio.run_coroutine_threadsafe(release.wait(), loop).result(timeout=10)
        return "done"

    with pytest.raises(asyncio.TimeoutError):
        await offload.run(blocking, timeout=0.1)

    # The thread is still running, so the slot is still taken.
    assert offload.in_flight == 1

    release.set()
    await asyncio.sleep(0.1)
    assert offload.in_flight == 0


@pytest.mark.asyncio
async def test_a_full_queue_returns_internal_results_rather_than_erroring(
    db_session, monkeypatch
):
    monkeypatch.setattr(
        "app.services.jobs.jobSearchService.fetch_linkedin_jobs", _slow_provider(latency=0)
    )

    class _AlwaysFull:
        in_flight = 99
        is_full = True

        async def run(self, work, *, timeout):
            raise OffloadRejected(99, 20)

    monkeypatch.setattr("app.services.jobs.jobSearchService.LINKEDIN_OFFLOAD", _AlwaysFull())
    payload = await JobSearchService(db_session).search(
        JobSearchQuery(keywords="python", location="Toronto", limit=10)
    )

    assert payload["linkedin"] == []


def test_the_pool_bounds_are_stated_and_finite():
    assert 0 < SCRAPER_MAX_WORKERS <= 16
    assert 0 <= SCRAPER_MAX_QUEUED <= 128
