from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
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
from app.services.ai.aiBudgetGuard import AIBudgetExhausted, ensure_llm_budget
from app.services.ai.aiUsageService import AIFeature, AIUsageService, QuotaReservation
from app.services.resumes.resumeService import ResumeService


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
        # Atomically claim a daily slot before any spend (TOCTOU-safe).
        reservation = await self.reserve_slot(user_id)

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
            # No LLM call happens, so the reserved slot is returned.
            await reservation.release()
            await self.fail_evaluation(
                evaluation,
                "Could not extract enough resume text for analysis.",
            )
            raise HTTPException(
                status_code=400,
                detail="The uploaded file does not contain enough readable text for evaluation.",
            )

        try:
            # Global cost ceiling / kill switch — fail closed to "Manual mode".
            await ensure_llm_budget()
            result = await self.evaluator.evaluate(extracted_text)
        except AIBudgetExhausted as exc:
            await reservation.release()
            await self.fail_evaluation(evaluation, str(exc))
            raise HTTPException(
                status_code=503,
                detail="Our AI analyzer is temporarily unavailable. Please try again later or use Manual mode.",
            ) from exc
        except Exception as exc:  # noqa: BLE001
            await reservation.release()
            await self.fail_evaluation(evaluation, str(exc))
            raise HTTPException(
                status_code=502,
                detail="The AI evaluator is unavailable right now. Please try again later.",
            ) from exc

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
