from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.resume_analyzer.resume_audit_llm import (
    GeminiResumeAuditEvaluator,
    ResumeAuditEvaluator,
    serialize_resume_audit_result,
)
from app.core.resume_analyzer.prompts.resume_audit_prompt import PROMPT_VERSION
from app.core.resume_analyzer.resume_audit_schema import (
    ResumeAuditResult,
    format_resume_audit_report,
)
from app.core.resume_analyzer.resume_text_extractor import extract_resume_text_from_bytes
from app.models.resumeCourseEvaluationModel import (
    ResumeCourseEvaluationModel,
    ResumeCourseEvaluationStatus,
)
from app.services.ai.aiBudgetGuard import AIBudgetExhausted
from app.services.ai.aiUsageService import (
    RELEASE_AFTER_ATTEMPT,
    RELEASE_NO_SPEND,
    AIFeature,
    AIUsageService,
    QuotaReservation,
)
from app.services.resumes.resumeService import ResumeService

LOGGER = logging.getLogger(__name__)


class _EvaluationAborted(Exception):
    """One failed step of an audit, carrying what each party needs to know.

    ``provider_attempted`` is the part that cannot be guessed later: whether the
    evaluator actually reached the provider. It decides how the reservation is
    settled, so a provider outage and a file we could not read stop being the
    same event in the ledger.
    """

    def __init__(
        self,
        *,
        status_code: int,
        public_detail: str,
        failure_message: str,
        provider_attempted: bool,
    ) -> None:
        super().__init__(failure_message)
        self.status_code = status_code
        self.public_detail = public_detail
        self.failure_message = failure_message
        self.provider_attempted = provider_attempted


class ResumeCourseAuditService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        evaluator: ResumeAuditEvaluator | None = None,
    ) -> None:
        self.session = session
        self.resume_service = ResumeService(session)
        self.ai_usage_service = AIUsageService(session)
        self.evaluator = evaluator or GeminiResumeAuditEvaluator()

    async def get_daily_attempts(self, user_id: UUID) -> int:
        summary = await self.ai_usage_service.get_summary(
            user_id=user_id,
            feature=AIFeature.RESUME_COURSE_AUDIT,
        )
        return summary.used_today

    async def get_daily_limit(self, user_id: UUID) -> int:
        summary = await self.ai_usage_service.get_summary(
            user_id=user_id,
            feature=AIFeature.RESUME_COURSE_AUDIT,
        )
        return summary.daily_limit

    async def ensure_daily_limit(self, user_id: UUID) -> None:
        await self.ai_usage_service.ensure_available(
            user_id=user_id,
            feature=AIFeature.RESUME_COURSE_AUDIT,
        )

    async def reserve_slot(self, user_id: UUID) -> QuotaReservation:
        """Atomically claim a daily slot before any LLM spend (TOCTOU-safe)."""
        return await self.ai_usage_service.reserve(
            user_id=user_id,
            feature=AIFeature.RESUME_COURSE_AUDIT,
        )

    async def create_pending_evaluation(self, *, user_id: UUID, resume_id: UUID) -> ResumeCourseEvaluationModel:
        evaluation = ResumeCourseEvaluationModel(
            user_id=user_id,
            resume_id=resume_id,
            status=ResumeCourseEvaluationStatus.PENDING,
            prompt_version=PROMPT_VERSION,
        )
        self.session.add(evaluation)
        await self.session.commit()
        await self.session.refresh(evaluation)
        return evaluation

    async def complete_evaluation(
        self,
        evaluation: ResumeCourseEvaluationModel,
        result: ResumeAuditResult,
    ) -> ResumeCourseEvaluationModel:
        evaluation.status = ResumeCourseEvaluationStatus.COMPLETED
        evaluation.overall_score = result.overall_score
        evaluation.llm_confidence = result.llm_confidence
        evaluation.pass_status = result.pass_status
        evaluation.report_text = format_resume_audit_report(result)
        evaluation.structured_payload = serialize_resume_audit_result(result)
        evaluation.completed_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(evaluation)
        return evaluation

    async def fail_evaluation(self, evaluation: ResumeCourseEvaluationModel, message: str) -> None:
        evaluation.status = ResumeCourseEvaluationStatus.FAILED
        evaluation.error_message = message
        evaluation.completed_at = datetime.utcnow()
        await self.session.commit()

    async def upload_and_evaluate_resume(
        self,
        *,
        user_id: UUID,
        storage_location_id: str,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> tuple[dict, ResumeCourseEvaluationModel]:
        # Atomically claim a daily slot before any spend (TOCTOU-safe). From
        # here on *every* step is inside the try, so no failure can leave the
        # slot claimed: upload, evaluation row and text extraction used to run
        # outside it, and a failure in any of them held the user's quota until
        # midnight.
        reservation = await self.reserve_slot(user_id)
        evaluation: ResumeCourseEvaluationModel | None = None

        try:
            resume, file_info = await self.resume_service.create_resume_from_upload(
                user_id=user_id,
                storage_location_id=storage_location_id,
                file_bytes=file_bytes,
                file_name=filename,
                mime_type=content_type,
            )

            evaluation = await self.create_pending_evaluation(user_id=user_id, resume_id=resume.id)

            extracted_text = await extract_resume_text_from_bytes(
                file_bytes,
                filename=filename,
                content_type=content_type,
            )
            if len((extracted_text or "").strip()) < 80:
                raise _EvaluationAborted(
                    status_code=400,
                    public_detail=(
                        "The uploaded file does not contain enough readable text for evaluation."
                    ),
                    failure_message="Could not extract enough resume text for analysis.",
                    provider_attempted=False,
                )

            try:
                # The global attempt ceiling / kill switch is applied inside the
                # evaluator, immediately before each provider attempt, so a retry
                # is counted too. Gating here as well would double-count.
                result = await self.evaluator.evaluate(extracted_text)
            except AIBudgetExhausted as exc:
                # Refused before any attempt: the provider was never called.
                raise _EvaluationAborted(
                    status_code=503,
                    public_detail=(
                        "Our AI analyzer is temporarily unavailable. "
                        "Please try again later or use Manual mode."
                    ),
                    failure_message=str(exc),
                    provider_attempted=False,
                ) from exc
            except Exception as exc:  # noqa: BLE001
                raise _EvaluationAborted(
                    status_code=502,
                    public_detail="The AI evaluator is unavailable right now. Please try again later.",
                    failure_message=str(exc),
                    provider_attempted=True,
                ) from exc
        except _EvaluationAborted as aborted:
            await self._settle_failed_attempt(reservation, evaluation, aborted)
            raise HTTPException(status_code=aborted.status_code, detail=aborted.public_detail) from aborted
        except Exception:
            # Upload, storage or database failure: nothing was ever sent to the
            # provider, so the slot goes straight back and any half-created
            # evaluation is closed instead of being left PENDING forever.
            await self._settle_failed_attempt(
                reservation,
                evaluation,
                _EvaluationAborted(
                    status_code=500,
                    public_detail="",
                    failure_message="The evaluation could not be completed.",
                    provider_attempted=False,
                ),
            )
            raise

        # The charge and the result it pays for settle in the same transaction:
        # commit_usage only flushes, complete_evaluation commits both. There is
        # no window where the user is charged for a result that was never saved,
        # or handed a result that was never charged.
        await self.ai_usage_service.commit_usage(
            reservation,
            reference_type="resume_course_evaluation",
            reference_id=evaluation.id,
        )
        completed = await self.complete_evaluation(evaluation, result)
        usage_summary = await self.ai_usage_service.get_summary(
            user_id=user_id,
            feature=AIFeature.RESUME_COURSE_AUDIT,
        )
        return {
            "resume_id": str(resume.id),
            "file_url": file_info["view_url"],
            "original_filename": filename,
            "evaluation_id": str(completed.id),
            "overall_score": round(completed.overall_score or 0.0, 1),
            "llm_confidence": round(completed.llm_confidence or 0.0, 2),
            "pass_status": bool(completed.pass_status),
            "report": completed.report_text or "",
            "reason_for_score": result.reason_for_score,
            "main_weaknesses": result.main_weaknesses,
            "improvements": result.improvements,
            "scores": result.scores.model_dump(),
            "attempts_today": usage_summary.used_today,
            "daily_limit": usage_summary.daily_limit,
            "attempts_remaining": usage_summary.remaining_today,
        }, completed

    async def _settle_failed_attempt(
        self,
        reservation: QuotaReservation,
        evaluation: ResumeCourseEvaluationModel | None,
        aborted: _EvaluationAborted,
    ) -> None:
        """Close both halves of a failed attempt: the slot and the evaluation.

        The daily slot is a user entitlement, not a bill for provider spend, so
        it goes back either way — but the ledger row records *which* of the two
        happened, because only one of them cost money upstream. A failed attempt
        is already counted by the global budget guard.
        """
        reason = RELEASE_AFTER_ATTEMPT if aborted.provider_attempted else RELEASE_NO_SPEND
        await reservation.release(reason=reason)
        if evaluation is None:
            return
        try:
            await self.fail_evaluation(evaluation, aborted.failure_message)
        except SQLAlchemyError:
            # The database is what failed. Roll back so the session is usable
            # again for the caller's error handling; the evaluation stays PENDING
            # and is visible as such rather than being silently lost.
            LOGGER.exception("Could not mark evaluation %s as failed", evaluation.id)
            await self.session.rollback()
