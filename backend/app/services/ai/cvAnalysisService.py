from __future__ import annotations

import logging
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.resume_analyzer.contact_parser import extract_phone_number
from app.core.resume_analyzer.llm_model import ask_llm_model
from app.core.resume_analyzer.resume_text_extractor import extract_resume_text_from_bytes
from app.models.jobAnalysisModel import JobAnalysisModel, JobStatus
from app.models.resumeModel import ResumeModel
from app.services.ai.aiUsageService import AIFeature, AIUsageService, QuotaReservation
from app.services.analytics.embeddingService import ResumeEmbeddingService
from app.services.resumes.resumeService import ResumeService

LOGGER = logging.getLogger(__name__)

DAILY_LIMIT_MESSAGE = (
    "You reached your daily limit of AI CV analyses. "
    "Please try again tomorrow or use Manual mode."
)
LLM_QUOTA_MESSAGE = (
    "Our AI analyzer has reached its provider limit right now. "
    "Please try again later or continue with Manual mode."
)
LLM_TIMEOUT_MESSAGE = (
    "AI analysis is taking longer than expected. Please try again in a few minutes."
)
LLM_GENERAL_FAILURE_MESSAGE = (
    "We could not analyze your CV right now. Please try again later or use Manual mode."
)
INTERRUPTED_AFTER_SPEND_MESSAGE = (
    "The analysis was interrupted after the AI had already been called, so it was not "
    "retried automatically. Please start a new analysis."
)
EXHAUSTED_ATTEMPTS_MESSAGE = (
    "The analysis was interrupted repeatedly and has stopped retrying. Please start a new one."
)

# How long a worker owns a claimed job. Comfortably longer than an analysis
# (seconds), short enough that a job orphaned by a deploy is recovered within
# minutes rather than blocking the user's CV until someone notices.
JOB_LEASE_SECONDS = 300
# A job interrupted before spending gets a few tries, then stops. Looping
# forever on a job that always dies the same way is how a queue melts.
MAX_JOB_ATTEMPTS = 3


def friendly_analysis_error_message(error: Exception) -> str:
    raw = str(error or "").strip().lower()

    quota_markers = (
        "quota",
        "credit",
        "resource_exhausted",
        "insufficient",
        "billing",
        "rate limit",
        "429",
    )
    if any(marker in raw for marker in quota_markers):
        return LLM_QUOTA_MESSAGE

    timeout_markers = ("timeout", "timed out", "deadline exceeded")
    if any(marker in raw for marker in timeout_markers):
        return LLM_TIMEOUT_MESSAGE

    return LLM_GENERAL_FAILURE_MESSAGE


class CVAnalysisService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.resume_service = ResumeService(session)
        self.ai_usage_service = AIUsageService(session)

    async def reserve_slot(self, user_id: UUID) -> QuotaReservation:
        """Atomically claim a daily slot before any LLM spend (TOCTOU-safe)."""
        try:
            return await self.ai_usage_service.reserve(
                user_id=user_id,
                feature=AIFeature.CV_JOB_SEARCH,
            )
        except HTTPException as exc:
            if exc.status_code == 429:
                raise HTTPException(status_code=429, detail=DAILY_LIMIT_MESSAGE) from exc
            raise

    async def _commit_usage(self, reservation: QuotaReservation, *, job_id: UUID) -> None:
        await self.ai_usage_service.commit_usage(
            reservation,
            reference_type="job_analysis",
            reference_id=job_id,
        )

    async def get_latest_resume(self, user_id: UUID) -> ResumeModel | None:
        return await self.session.scalar(
            select(ResumeModel)
            .where(ResumeModel.user_id == user_id)
            .order_by(ResumeModel.created_at.desc())
            .limit(1)
        )

    async def get_cached_analysis(self, *, user_id: UUID, resume_id: UUID) -> JobAnalysisModel | None:
        return await self.session.scalar(
            select(JobAnalysisModel)
            .where(JobAnalysisModel.user_id == user_id)
            .where(JobAnalysisModel.resume_id == resume_id)
            .where(JobAnalysisModel.status == JobStatus.COMPLETED)
            .where(JobAnalysisModel.keywords.is_not(None))
            .order_by(JobAnalysisModel.completed_at.desc())
            .limit(1)
        )

    async def get_running_analysis(self, *, user_id: UUID, resume_id: UUID) -> JobAnalysisModel | None:
        return await self.session.scalar(
            select(JobAnalysisModel)
            .where(JobAnalysisModel.user_id == user_id)
            .where(JobAnalysisModel.resume_id == resume_id)
            .where(JobAnalysisModel.status.in_([JobStatus.PENDING, JobStatus.PROCESSING]))
            .order_by(JobAnalysisModel.created_at.desc())
            .limit(1)
        )

    async def create_pending_analysis(self, *, user_id: UUID, resume_id: UUID) -> JobAnalysisModel:
        """Enqueue an analysis, or join the one that is already queued.

        The unique index over active jobs is what decides: two simultaneous
        POSTs both get past the "is one running?" read, and exactly one INSERT
        survives. The loser returns the winner's job, so both callers poll the
        same ``job_id`` instead of two analyses running for one CV.
        """
        job_id = uuid4()
        now = datetime.utcnow()
        statement = insert(JobAnalysisModel).values(
            id=job_id,
            user_id=user_id,
            resume_id=resume_id,
            status=JobStatus.PENDING,
            attempts=0,
            created_at=now,
            updated_at=now,
        )
        try:
            # A Core INSERT inside a savepoint, not an ORM flush: a failed flush
            # marks the whole session for rollback, and this request still has a
            # response to build. Only the savepoint is undone here.
            async with self.session.begin_nested():
                await self.session.execute(statement)
        except IntegrityError:
            existing = await self.get_running_analysis(user_id=user_id, resume_id=resume_id)
            if existing is None:
                raise
            LOGGER.info("Joined the analysis already queued for resume %s", resume_id)
            return existing
        await self.session.commit()
        return await self._get_job(job_id)

    async def claim_job(self, job_id: UUID) -> bool:
        """Take ownership of a job for one lease. False if someone else has it.

        A single conditional UPDATE is the whole handover — the row moves to
        PROCESSING only from PENDING or from a lease that has run out, so two
        workers reaching for the same job cannot both start it.
        """
        now = datetime.utcnow()
        result = await self.session.execute(
            update(JobAnalysisModel)
            .where(
                JobAnalysisModel.id == job_id,
                or_(
                    JobAnalysisModel.status == JobStatus.PENDING,
                    (JobAnalysisModel.status == JobStatus.PROCESSING)
                    & JobAnalysisModel.lease_expires_at.is_not(None)
                    & (JobAnalysisModel.lease_expires_at <= now),
                ),
            )
            .values(
                status=JobStatus.PROCESSING,
                attempts=JobAnalysisModel.attempts + 1,
                lease_expires_at=now + timedelta(seconds=JOB_LEASE_SECONDS),
                updated_at=now,
            )
        )
        await self.session.commit()
        return bool(result.rowcount)

    async def renew_lease(self, job_id: UUID) -> None:
        """Push the lease out before a step that may take a while."""
        now = datetime.utcnow()
        await self.session.execute(
            update(JobAnalysisModel)
            .where(JobAnalysisModel.id == job_id, JobAnalysisModel.status == JobStatus.PROCESSING)
            .values(lease_expires_at=now + timedelta(seconds=JOB_LEASE_SECONDS), updated_at=now)
        )
        await self.session.commit()

    async def recover_stale_jobs(self) -> dict[str, int]:
        """Decide what to do with jobs whose worker never came back.

        The distinction that matters is whether the provider was already called.
        A job interrupted *before* that is safe to run again; one interrupted
        *after* it may already have cost money and produced a result nobody
        stored, so it is failed explicitly rather than re-run on a guess. The
        user sees a reason and can start a new analysis; nothing restarts spend
        by itself.
        """
        now = datetime.utcnow()
        stale = (
            JobAnalysisModel.status == JobStatus.PROCESSING,
            JobAnalysisModel.lease_expires_at.is_not(None),
            JobAnalysisModel.lease_expires_at <= now,
        )

        uncertain = await self.session.execute(
            update(JobAnalysisModel)
            .where(*stale, JobAnalysisModel.provider_attempted_at.is_not(None))
            .values(
                status=JobStatus.FAILED,
                error_message=INTERRUPTED_AFTER_SPEND_MESSAGE,
                lease_expires_at=None,
                completed_at=now,
                updated_at=now,
            )
        )
        exhausted = await self.session.execute(
            update(JobAnalysisModel)
            .where(
                *stale,
                JobAnalysisModel.provider_attempted_at.is_(None),
                JobAnalysisModel.attempts >= MAX_JOB_ATTEMPTS,
            )
            .values(
                status=JobStatus.FAILED,
                error_message=EXHAUSTED_ATTEMPTS_MESSAGE,
                lease_expires_at=None,
                completed_at=now,
                updated_at=now,
            )
        )
        requeued = await self.session.execute(
            update(JobAnalysisModel)
            .where(
                *stale,
                JobAnalysisModel.provider_attempted_at.is_(None),
                JobAnalysisModel.attempts < MAX_JOB_ATTEMPTS,
            )
            .values(status=JobStatus.PENDING, lease_expires_at=None, updated_at=now)
        )
        await self.session.commit()

        outcome = {
            "failed_after_spend": int(uncertain.rowcount or 0),
            "failed_attempts_exhausted": int(exhausted.rowcount or 0),
            "requeued": int(requeued.rowcount or 0),
        }
        if any(outcome.values()):
            LOGGER.info("Recovered stale CV analysis jobs: %s", outcome)
        return outcome

    async def due_job_ids(self, *, limit: int = 5) -> list[UUID]:
        """Jobs waiting for a worker, oldest first."""
        result = await self.session.execute(
            select(JobAnalysisModel.id)
            .where(JobAnalysisModel.status == JobStatus.PENDING)
            .order_by(JobAnalysisModel.created_at)
            .limit(limit)
        )
        return list(result.scalars())

    async def get_job(self, job_id: UUID) -> JobAnalysisModel | None:
        """One job by id, regardless of owner — the runner's entry point."""
        return await self._get_job(job_id)

    async def get_user_job(self, *, job_id: UUID, user_id: UUID) -> JobAnalysisModel | None:
        return await self.session.scalar(
            select(JobAnalysisModel)
            .where(JobAnalysisModel.id == job_id)
            .where(JobAnalysisModel.user_id == user_id)
        )

    async def get_keyword_snapshot(
        self,
        *,
        user_id: UUID,
        first_name: str | None,
        last_name: str | None,
    ) -> dict:
        resume = await self.get_latest_resume(user_id)
        if not resume:
            fallback_name = " ".join(part for part in (first_name, last_name) if part)
            return {
                "keywords": fallback_name or "developer",
                "has_cv": False,
            }

        last_job = await self.get_cached_analysis(user_id=user_id, resume_id=resume.id)

        # Backward compatibility: if old rows didn't store resume_id, fallback to latest completed.
        if not last_job:
            last_job = await self.session.scalar(
                select(JobAnalysisModel)
                .where(JobAnalysisModel.user_id == user_id)
                .where(JobAnalysisModel.status == JobStatus.COMPLETED)
                .order_by(JobAnalysisModel.completed_at.desc())
                .limit(1)
            )

        if last_job and last_job.keywords:
            return {
                "keywords": last_job.keywords,
                "has_cv": True,
                "cv_filename": resume.original_filename,
                "summary": resume.ai_summary or last_job.summary,
            }

        return {
            "keywords": "",
            "has_cv": True,
            "cv_filename": resume.original_filename,
            "summary": resume.ai_summary,
        }

    async def process_job(
        self,
        *,
        job_id: UUID,
        user_id: UUID,
        resume_id: UUID,
        reservation: QuotaReservation | None = None,
    ) -> None:
        """Run one queued analysis, if this worker manages to claim it.

        Claiming first is what makes the job safe to hand to more than one
        dispatcher: the request's own background task and the durable runner can
        both reach for it, and only one of them starts work.
        """
        if not await self.claim_job(job_id):
            LOGGER.info("Job %s is already claimed by another worker", job_id)
            await self._release(reservation)
            return

        try:
            job = await self._get_job(job_id)
            if not job:
                LOGGER.error("Job %s not found", job_id)
                await self._release(reservation)
                return

            resume = await self._get_user_resume(user_id=user_id, resume_id=resume_id)
            if not resume:
                await self._fail_job(job, "No CV found")
                await self._release(reservation)
                LOGGER.warning("No CV found for user %s with resume_id %s", user_id, resume_id)
                return

            cached_job = await self._get_cached_completed_job(
                user_id=user_id,
                resume_id=resume_id,
                current_job_id=job_id,
            )
            if cached_job and cached_job.keywords:
                # No LLM call happens on a cache hit, so the reserved slot is freed.
                await self._release(reservation)
                await self._complete_from_cache(job=job, resume=resume, cached_job=cached_job)
                LOGGER.info("Job %s completed from cache (resume_id=%s)", job_id, resume_id)
                return

            await self._process_resume(job=job, resume=resume, user_id=user_id, reservation=reservation)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Error processing job %s", job_id)
            await self._release(reservation)
            await self._fail_current_job(job_id, friendly_analysis_error_message(exc))

    @staticmethod
    async def _release(reservation: QuotaReservation | None) -> None:
        if reservation is not None:
            await reservation.release()

    async def _process_resume(
        self,
        *,
        job: JobAnalysisModel,
        resume: ResumeModel,
        user_id: UUID,
        reservation: QuotaReservation | None = None,
    ) -> None:
        LOGGER.info("Downloading CV for job %s: %s", job.id, resume.storage_file_id)
        file_content = await self.resume_service.download_resume_file(resume.storage_file_id)

        LOGGER.info("Extracting text from CV for job %s", job.id)
        resume_text = await extract_resume_text_from_bytes(
            file_content,
            filename=resume.original_filename,
            content_type="",
        )
        extracted_phone = extract_phone_number(resume_text)

        if not resume_text or len(resume_text.strip()) < 50:
            # No LLM call for unusable text, so the reserved slot is returned.
            await self._release(reservation)
            job.status = JobStatus.COMPLETED
            job.keywords = "developer"
            job.summary = None
            job.lease_expires_at = None
            resume.contact_phone = extracted_phone
            job.completed_at = datetime.utcnow()
            await self.session.commit()
            LOGGER.warning("CV text too short for job %s", job.id)
            return

        # A job recovered by the runner arrives without the reservation the
        # original request held, so entitlement is claimed here, immediately
        # before the spend it pays for. Over-quota fails the job instead of
        # spending.
        if reservation is None:
            reservation = await self.reserve_slot(user_id)

        # The global attempt ceiling / kill switch is applied inside
        # ask_llm_model, immediately before each provider attempt, so a retry
        # is counted too. Gating here as well would double-count. An
        # AIBudgetExhausted from there is handled by the caller's error path,
        # which releases the reserved slot and maps to "Manual mode".
        LOGGER.info("Analyzing CV with LLM for job %s", job.id)
        # Stamped *before* the call and committed on its own: if the process
        # dies mid-call, recovery can see that money may already have been
        # spent and refuses to repeat it blindly.
        job.provider_attempted_at = datetime.utcnow()
        job.lease_expires_at = datetime.utcnow() + timedelta(seconds=JOB_LEASE_SECONDS)
        await self.session.commit()

        resume_feature = await ask_llm_model(resume_text)
        # Idempotent by job id: a replay of this job records one charge.
        await self._commit_usage(reservation, job_id=job.id)

        if resume_feature.resume_keywords:
            keywords = ", ".join(resume_feature.resume_keywords[:5])
        elif resume_feature.resume_key_skills:
            keywords = ", ".join(resume_feature.resume_key_skills[:5])
        else:
            keywords = "developer"

        summary = (resume_feature.resume_summary or "").strip() or None

        job.status = JobStatus.COMPLETED
        job.keywords = keywords
        job.summary = summary
        job.lease_expires_at = None
        job.completed_at = datetime.utcnow()
        resume.ai_summary = summary
        resume.contact_phone = extracted_phone
        await self.session.commit()
        await self._sync_resume_embedding(resume=resume, text=summary or resume_text)

        LOGGER.info("Job %s completed successfully with keywords: %s", job.id, keywords)

    async def _sync_resume_embedding(self, *, resume: ResumeModel, text: str | None) -> None:
        try:
            embedding_service = ResumeEmbeddingService(self.session)
            await embedding_service.upsert_resume_embedding_from_text(
                resume_id=resume.id,
                text=text,
            )
        except Exception:  # noqa: BLE001
            LOGGER.exception("Resume embedding sync failed for resume %s", resume.id)

    async def _get_job(self, job_id: UUID) -> JobAnalysisModel | None:
        return await self.session.scalar(select(JobAnalysisModel).where(JobAnalysisModel.id == job_id))

    async def _get_user_resume(self, *, user_id: UUID, resume_id: UUID) -> ResumeModel | None:
        return await self.session.scalar(
            select(ResumeModel)
            .where(ResumeModel.user_id == user_id)
            .where(ResumeModel.id == resume_id)
            .limit(1)
        )

    async def _get_cached_completed_job(
        self,
        *,
        user_id: UUID,
        resume_id: UUID,
        current_job_id: UUID,
    ) -> JobAnalysisModel | None:
        return await self.session.scalar(
            select(JobAnalysisModel)
            .where(JobAnalysisModel.user_id == user_id)
            .where(JobAnalysisModel.resume_id == resume_id)
            .where(JobAnalysisModel.status == JobStatus.COMPLETED)
            .where(JobAnalysisModel.keywords.is_not(None))
            .where(JobAnalysisModel.id != current_job_id)
            .order_by(JobAnalysisModel.completed_at.desc())
            .limit(1)
        )

    async def _complete_from_cache(
        self,
        *,
        job: JobAnalysisModel,
        resume: ResumeModel,
        cached_job: JobAnalysisModel,
    ) -> None:
        job.status = JobStatus.COMPLETED
        job.keywords = cached_job.keywords
        job.summary = cached_job.summary
        if not resume.ai_summary and cached_job.summary:
            resume.ai_summary = cached_job.summary
        job.lease_expires_at = None
        job.completed_at = datetime.utcnow()
        await self.session.commit()

    async def _fail_job(self, job: JobAnalysisModel, message: str) -> None:
        job.status = JobStatus.FAILED
        job.error_message = message
        # A terminal job holds no lease: nothing is left for recovery to find.
        job.lease_expires_at = None
        job.completed_at = datetime.utcnow()
        await self.session.commit()

    async def _fail_current_job(self, job_id: UUID, message: str) -> None:
        try:
            job = await self._get_job(job_id)
            if job:
                await self._fail_job(job, message)
        except Exception:
            LOGGER.exception("Failed to update job %s status after error", job_id)
