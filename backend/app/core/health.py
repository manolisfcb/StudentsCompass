"""Liveness and readiness, which are not the same question.

Liveness asks "is this process running", and the only correct answer involves no
dependencies at all. A ``/healthz`` that touches the database turns a database
outage into a restart loop: the platform kills a container that was working
perfectly, the replacement fails the same check, and an outage that was
recoverable becomes one where nothing is left running to recover.

Readiness asks "should traffic go here *now*", and that one has to touch the
database, because a replica that cannot reach it will answer every request with
an error. Cloud Run uses the distinction to decide whether a revision joins the
load balancer at all, which is what makes the deploy gate in TASK-056 possible:
a revision that never becomes ready is never promoted.

The check is deliberately the cheapest possible round trip. It proves a session
can be acquired and the server answers — not that any table exists, which is the
migration Job's business (TASK-056), not a probe's.

It runs through the *same* session dependency a request uses, rather than
reaching for the engine directly. A probe that opens its own connection can
report a database that is perfectly reachable while every real request fails on
a pool that is exhausted or a session factory that was replaced — it would be
answering a question nobody asked.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

LOGGER = logging.getLogger(__name__)

#: Short on purpose. A probe that waits longer than the platform's own probe
#: timeout is a probe whose result is never read; and a database that needs more
#: than a couple of seconds to answer ``SELECT 1`` is not one this replica
#: should be receiving traffic on either way.
DEFAULT_READINESS_TIMEOUT_SECONDS = 2.0


async def database_ready(
    session: AsyncSession, timeout: float = DEFAULT_READINESS_TIMEOUT_SECONDS
) -> bool:
    """True when the session reaches the server and it answers in time.

    Every failure is the same answer — not ready — and none of them reaches the
    caller. The reason is logged, where operators can see it; it is not
    returned, because the probe is reachable from the internet and the shape of
    a driver error names the host, the port and often the user.
    """
    try:
        async with asyncio.timeout(timeout):
            await session.execute(text("SELECT 1"))
    except TimeoutError:
        LOGGER.warning("readiness: database did not answer within %.1fs", timeout)
        return False
    except Exception:
        # Logged with the traceback because this is the one place the operator
        # gets to find out *why* the replica is refusing traffic.
        LOGGER.warning("readiness: database check failed", exc_info=True)
        return False
    return True
