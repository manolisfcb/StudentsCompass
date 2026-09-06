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


@pytest.mark.asyncio
async def test_legacy_release_sequence_drops_a_concurrent_reservation(redis_client):
    """Why release had to become a single Lua script.

    The previous implementation issued DECRBY and then, only when the result
    went negative, SET 0. A reservation (INCR) landing between those two
    commands was erased by the SET. Replayed here against the real server in
    the exact order two clients can produce it.
    """
    await redis_client.set("quota:legacy", 1)

    # Client A releases the outstanding slot.
    assert int(await redis_client.decrby("quota:legacy", 1)) == 0
    # Client B releases a slot that is no longer there (a duplicate release).
    assert int(await redis_client.decrby("quota:legacy", 1)) == -1
    # Client C reserves a new slot before B gets to its floor step.
    assert int(await redis_client.incr("quota:legacy")) == 0
    # B's floor step lands last and overwrites C's reservation.
    await redis_client.set("quota:legacy", 0, keepttl=True)

    assert int(await redis_client.get("quota:legacy")) == 0  # C's slot is gone


@pytest.mark.asyncio
async def test_atomic_release_keeps_a_concurrent_reservation(store, redis_client):
    """Same sequence through the store: the reservation survives."""
    await store.incr("quota:atomic", ttl_seconds=60)

    assert await store.decr("quota:atomic") == 0
    assert await store.decr("quota:atomic") == 0  # duplicate release, floored
    assert await store.incr("quota:atomic", ttl_seconds=60) == 1

    assert await store.get_int("quota:atomic") == 1


@pytest.mark.asyncio
async def test_interleaved_release_and_reserve_conserve_the_count(store):
    """Twenty releases against twenty reservations, all in flight at once."""
    await store.incr("quota:mixed", ttl_seconds=60, amount=20)

    await asyncio.gather(
        *(store.decr("quota:mixed") for _ in range(20)),
        *(store.incr("quota:mixed", ttl_seconds=60) for _ in range(20)),
    )

    assert await store.get_int("quota:mixed") == 20


@pytest.mark.asyncio
async def test_two_replicas_share_the_global_attempt_ceiling(redis_url, redis_client, monkeypatch):
    """Two store objects on separate connections stand in for two replicas."""
    import app.config as config
    import app.services.ratelimit.counterStore as counter_store
    from app.services.ai.aiBudgetGuard import AIBudgetExhausted, ensure_llm_attempt_allowed
    from app.services.ratelimit.counterStore import RedisCounterStore

    replica_a = RedisCounterStore(redis_url)
    replica_b = RedisCounterStore(redis_url)
    monkeypatch.setattr(config, "AI_GLOBAL_DAILY_ATTEMPTS", 2)
    monkeypatch.setattr(config, "AI_LLM_ATTEMPTS_PER_MIN", 1000)

    monkeypatch.setattr(counter_store, "_store", replica_a)
    await ensure_llm_attempt_allowed()
    monkeypatch.setattr(counter_store, "_store", replica_b)
    await ensure_llm_attempt_allowed()

    # The ceiling is global: the third attempt is refused on either replica.
    with pytest.raises(AIBudgetExhausted):
        await ensure_llm_attempt_allowed()
    monkeypatch.setattr(counter_store, "_store", replica_a)
    with pytest.raises(AIBudgetExhausted):
        await ensure_llm_attempt_allowed()

    monkeypatch.setattr(counter_store, "_store", None)
