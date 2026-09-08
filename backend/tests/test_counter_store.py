import pytest

from app.services.ratelimit.counterStore import InMemoryCounterStore


@pytest.mark.asyncio
async def test_reserve_incr_seeds_from_base_then_increments():
    store = InMemoryCounterStore()

    # First reservation of the day is seeded from existing DB usage (base=2).
    assert await store.reserve_incr("k", base=2, ttl_seconds=60) == 3
    # Subsequent reservations just increment.
    assert await store.reserve_incr("k", base=2, ttl_seconds=60) == 4


@pytest.mark.asyncio
async def test_decr_floors_at_zero():
    store = InMemoryCounterStore()
    await store.incr("k", ttl_seconds=60)
    assert await store.decr("k") == 0
    assert await store.decr("k") == 0


@pytest.mark.asyncio
async def test_sliding_window_blocks_after_max():
    store = InMemoryCounterStore()
    allowed1, _ = await store.sliding_window_allow("w", max_requests=2, window_seconds=60)
    allowed2, _ = await store.sliding_window_allow("w", max_requests=2, window_seconds=60)
    allowed3, retry = await store.sliding_window_allow("w", max_requests=2, window_seconds=60)

    assert allowed1 and allowed2
    assert not allowed3
    assert retry >= 1
