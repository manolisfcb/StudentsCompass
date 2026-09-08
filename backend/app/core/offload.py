"""Running blocking work off the event loop, with the bounds stated.

Two places in this codebase call code that blocks for seconds inside an
``async def``: the LinkedIn scraper (``requests.get`` plus ``time.sleep`` in a
paging loop) and the CP-SAT solver. Awaiting a blocking call does not yield —
the event loop sits inside it — so one such request stalls every other request
sharing the worker.

Moving the work to a thread fixes that and introduces a new way to fail: an
unbounded pool with an unbounded queue turns a slow dependency into memory
exhaustion. Hence one class with three explicit bounds rather than a bare
``run_in_executor`` at each call site.

Introduced by TASK-020 inside ``jobSearchService`` and lifted here by TASK-022
so the solver could reuse it instead of growing a second copy.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeVar

T = TypeVar("T")


class OffloadRejected(RuntimeError):
    """The bounded queue was full; the work was never scheduled."""

    def __init__(self, in_flight: int, capacity: int):
        super().__init__(f"offload queue full ({in_flight}/{capacity})")
        self.in_flight = in_flight
        self.capacity = capacity


class BoundedOffload:
    """Runs blocking work in a bounded pool of threads, off the event loop.

    Three separate bounds, because they fail differently:

    * ``max_workers`` — how much blocking work runs at once;
    * ``max_queued`` — how much may wait for it. Over this, callers are refused
      immediately instead of piling up;
    * a per-call timeout the caller passes in.

    A thread cannot be cancelled, so the timeout releases the *caller*, never
    the slot. The slot is returned when the thread actually finishes, which is
    what keeps the bound honest: otherwise a stream of timeouts would hand out
    unlimited slots while the threads behind them were all still running.
    """

    def __init__(self, *, max_workers: int, max_queued: int, thread_name_prefix: str):
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix=thread_name_prefix
        )
        self._capacity = max_workers + max_queued
        self._in_flight = 0

    @property
    def in_flight(self) -> int:
        return self._in_flight

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def is_full(self) -> bool:
        return self._in_flight >= self._capacity

    async def run(self, work: Callable[[], T], *, timeout: float) -> T:
        """Run ``work`` in a worker thread.

        Raises :class:`OffloadRejected` when the queue is full and
        :class:`asyncio.TimeoutError` when the call outlives ``timeout``.
        """
        if self.is_full:
            raise OffloadRejected(self._in_flight, self._capacity)

        self._in_flight += 1
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(self._executor, work)
        future.add_done_callback(self._release)
        try:
            # Shielded: cancelling the wrapper would mark the future done while
            # its thread was still running, and the slot would come back early.
            return await asyncio.wait_for(asyncio.shield(future), timeout)
        except asyncio.CancelledError:
            # The client went away. The thread keeps its slot until it finishes,
            # which is exactly the back-pressure this class exists to provide.
            raise

    def _release(self, _future) -> None:
        self._in_flight -= 1
