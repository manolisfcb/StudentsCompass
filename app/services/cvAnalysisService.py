from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.resume_analyzer.contact_parser import extract_phone_number
from app.core.resume_analyzer.llm_model import ask_llm_model
from app.core.resume_analyzer.resume_text_extractor import extract_resume_text_from_bytes
from app.models.jobAnalysisModel import JobAnalysisModel, JobStatus
from app.models.resumeModel import ResumeModel
from app.services.aiUsageService import AIFeature, AIUsageService
from app.services.resumeService import ResumeService

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

    async def ensure_daily_limit(self, user_id: UUID) -> None:
        try:
            await self.ai_usage_service.ensure_available(
                user_id=user_id,
                feature=AIFeature.CV_JOB_SEARCH,
            )
        except HTTPException as exc:
            if exc.status_code == 429:
                raise HTTPException(status_code=429, detail=DAILY_LIMIT_MESSAGE) from exc
            raise

    async def record_usage(self, *, user_id: UUID, job_id: UUID) -> None:
        await self.ai_usage_service.record_usage(
            user_id=user_id,
            feature=AIFeature.CV_JOB_SEARCH,
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
        job = JobAnalysisModel(
            user_id=user_id,
            resume_id=resume_id,
            status=JobStatus.PENDING,
        )
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

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

    async def process_job(self, *, job_id: UUID, user_id: UUID, resume_id: UUID) -> None:
        try:
            job = await self._get_job(job_id)
            if not job:
                LOGGER.error("Job %s not found", job_id)
                return

            job.status = JobStatus.PROCESSING
            await self.session.commit()

            resume = await self._get_user_resume(user_id=user_id, resume_id=resume_id)
            if not resume:
                await self._fail_job(job, "No CV found")
                LOGGER.warning("No CV found for user %s with resume_id %s", user_id, resume_id)
                return

            cached_job = await self._get_cached_completed_job(
                user_id=user_id,
                resume_id=resume_id,
                current_job_id=job_id,
            )
            if cached_job and cached_job.keywords:
                await self._complete_from_cache(job=job, resume=resume, cached_job=cached_job)
                LOGGER.info("Job %s completed from cache (resume_id=%s)", job_id, resume_id)
                return

            await self._process_resume(job=job, resume=resume, user_id=user_id)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Error processing job %s", job_id)
            await self._fail_current_job(job_id, friendly_analysis_error_message(exc))

    async def _process_resume(self, *, job: JobAnalysisModel, resume: ResumeModel, user_id: UUID) -> None:
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
            job.status = JobStatus.COMPLETED
            job.keywords = "developer"
            job.summary = None
            resume.contact_phone = extracted_phone
            job.completed_at = datetime.utcnow()
            await self.session.commit()
            LOGGER.warning("CV text too short for job %s", job.id)
            return

        LOGGER.info("Analyzing CV with LLM for job %s", job.id)
        await self.record_usage(user_id=user_id, job_id=job.id)
        resume_feature = await ask_llm_model(resume_text)

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
        job.completed_at = datetime.utcnow()
        resume.ai_summary = summary
        resume.contact_phone = extracted_phone
        await self.session.commit()

        LOGGER.info("Job %s completed successfully with keywords: %s", job.id, keywords)

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
        job.completed_at = datetime.utcnow()
        await self.session.commit()

    async def _fail_job(self, job: JobAnalysisModel, message: str) -> None:
        job.status = JobStatus.FAILED
        job.error_message = message
        job.completed_at = datetime.utcnow()
        await self.session.commit()

    async def _fail_current_job(self, job_id: UUID, message: str) -> None:
        try:
            job = await self._get_job(job_id)
            if job:
                await self._fail_job(job, message)
        except Exception:
            LOGGER.exception("Failed to update job %s status after error", job_id)
