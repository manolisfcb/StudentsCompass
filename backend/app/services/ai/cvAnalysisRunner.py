"""The worker that makes CV analysis survive the process that started it.

``BackgroundTasks`` runs inside the request's own process: a deploy, a crash or a
container restart between "job created" and "job finished" left the row on
PROCESSING forever, and — because a running job blocks new ones for the same CV
— the user could not start another analysis either.

The queue is ``job_analysis`` itself. It is small, already exists, and already
carries the state the API polls; adding Redis beside it would mean two places
that can disagree about the same job. What this runner adds is the part a table
alone cannot do: somebody who looks at it after a restart.

Two dispatchers reach for the same rows — the request's background task (for
latency) and this loop (for durability). That is safe because claiming is a
single conditional UPDATE, so exactly one of them ever starts a given job.
"""
from __future__ import annotations

import asyncio
import logging

from app.services.ai.cvAnalysisService import CVAnalysisService

LOGGER = logging.getLogger(__name__)

# How often the queue is swept when nothing wakes the runner. Recovery is not
# urgent — the request path handles the common case — so this stays lazy enough
# to cost one trivial query every few seconds.
POLL_INTERVAL_SECONDS = 5.0
# Analyses are expensive; the runner deliberately does not fan out.
MAX_JOBS_PER_SWEEP = 3


class CVAnalysisRunner:
    """Sweeps the job table: recovers what was abandoned, runs what is due."""

    def __init__(self, session_factory, *, poll_interval: float = POLL_INTERVAL_SECONDS) -> None:
        self._session_factory = session_factory
        self._poll_interval = poll_interval
        self._task: asyncio.Task | None = None
        self._wakeup = asyncio.Event()
        self._stopping = False

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stopping = False
        self._task = asyncio.create_task(self._loop(), name="cv-analysis-runner")
        LOGGER.info("CV analysis runner started")

    async def stop(self) -> None:
        """Stop cleanly: no work is abandoned mid-flight without a lease.

        A job still being processed when the process exits keeps its lease, so
        the next runner picks it up (or fails it explicitly if the provider had
        already been called) instead of it hanging forever.
        """
        self._stopping = True
        task = self._task
        self._task = None
        if task is None:
            return
        self._wakeup.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001
            LOGGER.exception("CV analysis runner did not shut down cleanly")
        LOGGER.info("CV analysis runner stopped")

    def wake(self) -> None:
        """Ask for a sweep now — a job was just enqueued."""
        self._wakeup.set()

    async def _loop(self) -> None:
        while not self._stopping:
            try:
                await self.sweep_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                # A sweep must never be the reason the runner dies.
                LOGGER.exception("CV analysis sweep failed")
            try:
                await asyncio.wait_for(self._wakeup.wait(), timeout=self._poll_interval)
            except asyncio.TimeoutError:
                pass
            finally:
                self._wakeup.clear()

    async def sweep_once(self) -> int:
        """Recover stale jobs, then run what is waiting. Returns jobs started."""
        async with self._session_factory() as session:
            service = CVAnalysisService(session)
            await service.recover_stale_jobs()
            job_ids = await service.due_job_ids(limit=MAX_JOBS_PER_SWEEP)

        started = 0
        for job_id in job_ids:
            # A session per job, opened and closed by the runner: nothing is
            # shared with a request, and a failure on one job cannot leave the
            # next one running inside a broken transaction.
            async with self._session_factory() as session:
                service = CVAnalysisService(session)
                job = await service.get_job(job_id)
                if job is None or job.resume_id is None:
                    continue
                await service.process_job(
                    job_id=job.id,
                    user_id=job.user_id,
                    resume_id=job.resume_id,
                )
                started += 1
        return started


_runner: CVAnalysisRunner | None = None


def get_runner() -> CVAnalysisRunner | None:
    return _runner


async def start_runner() -> CVAnalysisRunner:
    """Start the process-wide runner (called from the app lifespan)."""
    global _runner
    if _runner is None:
        from app.db import async_session

        _runner = CVAnalysisRunner(async_session)
    await _runner.start()
    return _runner


async def stop_runner() -> None:
    global _runner
    if _runner is not None:
        await _runner.stop()
        _runner = None


def wake_runner() -> None:
    """No-op when the runner is not running (tests, scripts)."""
    if _runner is not None:
        _runner.wake()
