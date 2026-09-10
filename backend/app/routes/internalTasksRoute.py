"""The endpoints a task queue calls, and nobody else.

Plan 08 §6.3 moves the CV-analysis runner out of the web replica. What replaces
it is this: the queue delivers one HTTP call per job, authenticated as a
specific service account, and the handler claims the job's lease exactly the
way the old loop did.

The claim is unchanged on purpose — TASK-013 built it, and this task is only
about who pulls the trigger. That is also what makes a replay safe: a task the
queue delivers twice finds the job already claimed or already terminal, and is
answered ``200`` so the queue stops retrying something that is finished.
"""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.internalAuth import require_task_caller
from app.db import get_session
from app.models.jobAnalysisModel import JobStatus
from app.services.ai.cvAnalysisService import CVAnalysisService
from app.services.tasks import outbox

LOGGER = logging.getLogger(__name__)

router = APIRouter()

TERMINAL_STATUSES = (JobStatus.COMPLETED, JobStatus.FAILED)


@router.post("/internal/tasks/cv-analyses/{job_id}")
async def run_cv_analysis_task(
    job_id: UUID,
    caller: str = Depends(require_task_caller),
    session: AsyncSession = Depends(get_session),
):
    """Run one queued analysis. Idempotent by way of the job's own lease."""
    service = CVAnalysisService(session)
    job = await service.get_job(job_id)
    if job is None:
        # 200, not 404: a task for a job that no longer exists is finished
        # business, and a 404 would make the queue retry it to exhaustion.
        LOGGER.info("Task for unknown analysis %s (caller=%s)", job_id, caller)
        return {"job_id": str(job_id), "status": "unknown", "ran": False}

    if job.status in TERMINAL_STATUSES:
        # The replay case the ficha names: succeed, spend nothing.
        return {"job_id": str(job_id), "status": job.status.value, "ran": False}

    if job.resume_id is None:
        raise HTTPException(status_code=422, detail="The analysis has no resume attached.")

    await service.process_job(
        job_id=job.id,
        user_id=job.user_id,
        resume_id=job.resume_id,
    )
    refreshed = await service.get_job(job_id)
    status = refreshed.status.value if refreshed else "unknown"
    return {"job_id": str(job_id), "status": status, "ran": True}


@router.post("/internal/tasks/cv-analyses-reconcile")
async def reconcile_cv_analyses(
    caller: str = Depends(require_task_caller),
    session: AsyncSession = Depends(get_session),
):
    """Re-enqueue what was lost. Runs no AI itself.

    Scale-to-zero, a killed instance or a task the queue dropped all end the
    same way: a job that is still unfinished with nobody working on it. This
    releases those leases and makes their dispatch due again — and stops there,
    deliberately. A reconciliation loop that also *processed* would be a second
    place where AI is spent, and the plan puts that out of scope.
    """
    service = CVAnalysisService(session)
    recovered = await service.recover_stale_jobs()
    due = await service.due_job_ids(limit=50)
    requeued = 0
    for job_id in due:
        if await outbox.requeue_for_job(session, job_id=job_id):
            requeued += 1
    await session.commit()
    LOGGER.info("Reconcile by %s: recovered=%s requeued=%s", caller, recovered, requeued)
    return {"recovered": recovered, "requeued": requeued}
