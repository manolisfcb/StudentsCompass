"""The local stand-in for Cloud Tasks.

In production the outbox is drained by whatever the deployment configured —
Cloud Tasks, with its own retries and its own OIDC. Locally there is no Google,
and the plan is explicit that the compose stack must not need one: this process
reads the same table, calls the same endpoint and carries a shared secret
instead of a signed token.

What it is *not* is a second implementation of the work. It delivers a
dispatch; the endpoint claims the lease and runs the analysis, exactly as the
queue's delivery would. That is the whole reason the outbox is a table and not
a queue-specific artefact.

    python -m app.workers.taskOutboxWorker
"""
from __future__ import annotations

import asyncio
import logging
import signal

from app.config import TASK_OUTBOX_POLL_SECONDS
from app.services.tasks.outbox import deliver_pending
from app.services.tasks.transports import build_transport

LOGGER = logging.getLogger("app.workers.task_outbox")


async def run_forever(*, poll_seconds: int = TASK_OUTBOX_POLL_SECONDS) -> None:
    from app.db import async_session

    transport = build_transport()
    stopping = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stopping.set)
        except NotImplementedError:  # pragma: no cover - not on this platform
            pass

    LOGGER.info("Outbox worker started with transport %s", type(transport).__name__)
    while not stopping.is_set():
        try:
            async with async_session() as session:
                delivered = await deliver_pending(session, transport)
            if delivered:
                LOGGER.info("Delivered %s dispatches", delivered)
        except Exception:  # noqa: BLE001
            # A failed sweep must never be the reason the worker dies; the rows
            # it did not deliver are still there, with their backoff.
            LOGGER.exception("Outbox sweep failed")
        try:
            await asyncio.wait_for(stopping.wait(), timeout=poll_seconds)
        except asyncio.TimeoutError:
            pass
    LOGGER.info("Outbox worker stopped")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
