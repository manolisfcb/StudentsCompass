"""RedisCounterStore against a real Redis.

The fast lane exercises InMemoryCounterStore only. Cross-replica behaviour —
atomic Lua scripts, TTL set once on creation, floor-at-zero release — is what
makes the AI budget and rate limits hold when the app is scaled, so it is
verified here against the actual server.
"""
from __future__ import annotations

import asyncio

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.redis]


@pytest.fixture
def store(redis_url, redis_client):
    from app.services.ratelimit.counterStore import RedisCounterStore

    return RedisCounterStore(redis_url)


@pytest.mark.asyncio
async def test_incr_sets_ttl_once_and_is_shared(store, redis_client):
    assert await store.incr("budget:day", ttl_seconds=60) == 1
    first_ttl = await redis_client.ttl("budget:day")

    await asyncio.sleep(0)
    assert await store.incr("budget:day", ttl_seconds=3600) == 2
    # The daily window must not be extended by later increments.
    assert await redis_client.ttl("budget:day") <= first_ttl

    assert await store.get_int("budget:day") == 2
    assert store.is_shared is True


@pytest.mark.asyncio
async def test_reserve_incr_seeds_from_database_usage(store):
    """A fresh Redis must not hand back quota already spent in the DB."""
    assert await store.reserve_incr("quota:user", base=2, ttl_seconds=60) == 3
    assert await store.reserve_incr("quota:user", base=2, ttl_seconds=60) == 4


@pytest.mark.asyncio
async def test_decr_releases_reservation_and_floors_at_zero(store):
    await store.incr("quota:user", ttl_seconds=60)
    assert await store.decr("quota:user") == 0
    assert await store.decr("quota:user") == 0


@pytest.mark.asyncio
async def test_sliding_window_is_atomic_under_concurrency(store):
    """Twenty concurrent callers, limit five: exactly five are allowed."""
    results = await asyncio.gather(
        *(
            store.sliding_window_allow("ip:1.2.3.4", max_requests=5, window_seconds=60)
            for _ in range(20)
        )
    )

    allowed = [allowed for allowed, _ in results if allowed]
    assert len(allowed) == 5
    retry_after = [retry for allowed, retry in results if not allowed]
    assert all(retry > 0 for retry in retry_after)


@pytest.mark.asyncio
async def test_unreachable_redis_raises_so_guards_can_fail_closed():
    from tests.isolation import allow_test_service
    from app.services.ratelimit.counterStore import CounterStoreError, RedisCounterStore

    # Loopback port with nothing listening: connection refused, not a timeout.
    allow_test_service("redis://127.0.0.1:6390/0")
    store = RedisCounterStore("redis://127.0.0.1:6390/0")

    with pytest.raises(CounterStoreError):
        await store.incr("anything", ttl_seconds=60)
