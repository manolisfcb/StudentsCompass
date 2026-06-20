"""Shared atomic counter / rate-limit primitives.

Two interchangeable backends sit behind a single async interface:

* ``RedisCounterStore`` — counters are shared across every process/replica, so
  daily quotas, the global LLM budget and IP rate limits hold even when the app
  is scaled horizontally. Selected automatically when ``REDIS_URL`` is set.
* ``InMemoryCounterStore`` — per-process fallback for local dev and tests. No
  external dependency; counters reset on restart.

Callers decide the failure policy: ``incr``/``sliding_window_allow`` raise
``CounterStoreError`` if the Redis backend is unreachable so cost-sensitive
guards can *fail closed* while best-effort rate limits can *fail open*.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections import deque
from typing import Optional

LOGGER = logging.getLogger(__name__)


class CounterStoreError(RuntimeError):
    """Raised when the backing store (Redis) is unavailable."""


class CounterStore(ABC):
    is_shared: bool = False

    @abstractmethod
    async def incr(self, key: str, *, ttl_seconds: int, amount: int = 1) -> int:
        """Atomically increment ``key`` (creating it with ``ttl_seconds``) and
        return the new value."""

    @abstractmethod
    async def reserve_incr(self, key: str, *, base: int, ttl_seconds: int) -> int:
        """Atomically increment ``key`` by one, seeding it to ``base`` when the
        key does not yet exist (so the returned value is ``base + 1`` on the
        first call). Used to make a daily reservation while staying consistent
        with usage already recorded in the database — this way a counter reset
        (process restart / fresh Redis) cannot hand back already-spent quota."""

    @abstractmethod
    async def decr(self, key: str, *, amount: int = 1) -> int:
        """Atomically decrement ``key``, flooring at zero. Used to release a
        reservation that did not end up spending."""

    @abstractmethod
    async def get_int(self, key: str) -> int:
        ...

    @abstractmethod
    async def sliding_window_allow(
        self, key: str, *, max_requests: int, window_seconds: int
    ) -> tuple[bool, int]:
        """Return ``(allowed, retry_after_seconds)`` for a sliding-window limit."""

    async def reset(self) -> None:  # pragma: no cover - overridden where needed
        """Clear all state. Only meaningful for the in-memory backend (tests)."""


class InMemoryCounterStore(CounterStore):
    is_shared = False

    def __init__(self) -> None:
        # key -> (value, expires_at_epoch)
        self._counters: dict[str, tuple[int, float]] = {}
        # key -> deque[event_epoch]
        self._windows: dict[str, deque[float]] = {}

    def _purge_if_expired(self, key: str, now: float) -> None:
        entry = self._counters.get(key)
        if entry and entry[1] <= now:
            self._counters.pop(key, None)

    async def incr(self, key: str, *, ttl_seconds: int, amount: int = 1) -> int:
        now = time.time()
        self._purge_if_expired(key, now)
        value, expires_at = self._counters.get(key, (0, now + ttl_seconds))
        value += amount
        self._counters[key] = (value, expires_at)
        return value

    async def reserve_incr(self, key: str, *, base: int, ttl_seconds: int) -> int:
        now = time.time()
        self._purge_if_expired(key, now)
        if key in self._counters:
            value = self._counters[key][0] + 1
            self._counters[key] = (value, self._counters[key][1])
        else:
            value = base + 1
            self._counters[key] = (value, now + ttl_seconds)
        return value

    async def decr(self, key: str, *, amount: int = 1) -> int:
        now = time.time()
        self._purge_if_expired(key, now)
        entry = self._counters.get(key)
        if not entry:
            return 0
        value = max(0, entry[0] - amount)
        self._counters[key] = (value, entry[1])
        return value

    async def get_int(self, key: str) -> int:
        now = time.time()
        self._purge_if_expired(key, now)
        entry = self._counters.get(key)
        return entry[0] if entry else 0

    async def sliding_window_allow(
        self, key: str, *, max_requests: int, window_seconds: int
    ) -> tuple[bool, int]:
        now = time.time()
        events = self._windows.setdefault(key, deque())
        cutoff = now - window_seconds
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= max_requests:
            retry_after = max(1, int(window_seconds - (now - events[0])))
            return False, retry_after
        events.append(now)
        if not events:
            self._windows.pop(key, None)
        return True, 0

    async def reset(self) -> None:
        self._counters.clear()
        self._windows.clear()


# Atomic sliding-window check, evaluated entirely inside Redis so concurrent
# callers cannot race between the count and the add.
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count >= max_requests then
  local earliest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local retry = window
  if earliest[2] then
    retry = math.ceil(window - (now - tonumber(earliest[2])))
  end
  if retry < 1 then retry = 1 end
  return {0, retry}
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, window + 1)
return {1, 0}
"""


_RESERVE_INCR_LUA = """
local key = KEYS[1]
local base = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
if redis.call('EXISTS', key) == 0 then
  local val = base + 1
  redis.call('SET', key, val, 'EX', ttl)
  return val
end
return redis.call('INCR', key)
"""


class RedisCounterStore(CounterStore):
    is_shared = True

    def __init__(self, url: str) -> None:
        # Imported lazily so the dependency is only required when REDIS_URL is set.
        from redis import asyncio as redis_asyncio

        self._redis = redis_asyncio.from_url(url, encoding="utf-8", decode_responses=True)
        self._sliding_window = self._redis.register_script(_SLIDING_WINDOW_LUA)
        self._reserve_incr = self._redis.register_script(_RESERVE_INCR_LUA)

    async def reserve_incr(self, key: str, *, base: int, ttl_seconds: int) -> int:
        try:
            value = await self._reserve_incr(keys=[key], args=[base, ttl_seconds])
            return int(value)
        except Exception as exc:  # noqa: BLE001
            raise CounterStoreError(str(exc)) from exc

    async def incr(self, key: str, *, ttl_seconds: int, amount: int = 1) -> int:
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.incrby(key, amount)
                # Only set the TTL when the key is first created so the daily
                # window is not extended on every increment.
                pipe.expire(key, ttl_seconds, nx=True)
                result = await pipe.execute()
            return int(result[0])
        except Exception as exc:  # noqa: BLE001
            raise CounterStoreError(str(exc)) from exc

    async def decr(self, key: str, *, amount: int = 1) -> int:
        try:
            value = int(await self._redis.decrby(key, amount))
            if value < 0:
                await self._redis.set(key, 0, keepttl=True)
                return 0
            return value
        except Exception as exc:  # noqa: BLE001
            raise CounterStoreError(str(exc)) from exc

    async def get_int(self, key: str) -> int:
        try:
            value = await self._redis.get(key)
            return int(value) if value is not None else 0
        except Exception as exc:  # noqa: BLE001
            raise CounterStoreError(str(exc)) from exc

    async def sliding_window_allow(
        self, key: str, *, max_requests: int, window_seconds: int
    ) -> tuple[bool, int]:
        now = time.time()
        member = f"{now:.6f}:{id(object())}"
        try:
            allowed, retry = await self._sliding_window(
                keys=[key],
                args=[now, window_seconds, max_requests, member],
            )
            return bool(int(allowed)), int(retry)
        except Exception as exc:  # noqa: BLE001
            raise CounterStoreError(str(exc)) from exc


_store: Optional[CounterStore] = None


def get_counter_store() -> CounterStore:
    """Process-wide singleton. Redis when configured, in-memory otherwise."""
    global _store
    if _store is None:
        from app.config import REDIS_URL

        if REDIS_URL:
            try:
                _store = RedisCounterStore(REDIS_URL)
                LOGGER.info("CounterStore: using Redis backend (shared across replicas).")
            except Exception:  # noqa: BLE001
                LOGGER.exception("CounterStore: Redis init failed; falling back to in-memory.")
                _store = InMemoryCounterStore()
        else:
            _store = InMemoryCounterStore()
            LOGGER.info("CounterStore: REDIS_URL not set; using in-memory backend.")
    return _store


def set_counter_store(store: CounterStore) -> None:
    """Override the singleton (used by tests)."""
    global _store
    _store = store


async def reset_counter_store() -> None:
    """Reset in-memory state between tests (no-op for Redis)."""
    store = get_counter_store()
    await store.reset()
