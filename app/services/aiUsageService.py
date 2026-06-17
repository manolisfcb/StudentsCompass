from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aiUsageModel import AIQuotaGrantModel, AIUsageEventModel
from app.models.jobAnalysisModel import JobAnalysisModel
from app.models.resumeCourseEvaluationModel import ResumeCourseEvaluationModel


class AIFeature:
    CV_JOB_SEARCH = "cv_job_search"
    RESUME_COURSE_AUDIT = "resume_course_audit"
    MOCK_INTERVIEW = "mock_interview"


@dataclass(frozen=True)
class AIUsageSummary:
    feature: str
    used_today: int
    daily_limit: int
    remaining_today: int
    reset_at: datetime


class AIUsageService:
    BASE_DAILY_LIMIT = 3

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def today_utc_bounds() -> tuple[datetime, datetime]:
        now = datetime.utcnow()
        start = datetime(now.year, now.month, now.day)
        end = start + timedelta(days=1)
        return start, end

    @staticmethod
    def time_until_next_utc_day_label() -> str:
        now = datetime.utcnow()
        _, next_day_start = AIUsageService.today_utc_bounds()
        remaining_seconds = max(0, int((next_day_start - now).total_seconds()))
        total_minutes = (remaining_seconds + 59) // 60
        hours = total_minutes // 60
        minutes = total_minutes % 60
        if hours <= 0:
            return f"{minutes}m"
        if minutes <= 0:
            return f"{hours}h"
        return f"{hours}h {minutes}m"

    async def get_daily_limit(self, *, user_id: UUID, feature: str) -> int:
        now = datetime.utcnow()
        result = await self.session.execute(
            select(func.coalesce(func.sum(AIQuotaGrantModel.daily_extra_units), 0)).where(
                AIQuotaGrantModel.user_id == user_id,
                AIQuotaGrantModel.is_active.is_(True),
                AIQuotaGrantModel.starts_at <= now,
                or_(AIQuotaGrantModel.ends_at.is_(None), AIQuotaGrantModel.ends_at > now),
                or_(AIQuotaGrantModel.feature.is_(None), AIQuotaGrantModel.feature == feature),
            )
        )
        extra_units = int(result.scalar_one() or 0)
        return self.BASE_DAILY_LIMIT + max(0, extra_units)

    async def get_used_today(self, *, user_id: UUID, feature: str) -> int:
        start, end = self.today_utc_bounds()
        result = await self.session.execute(
            select(func.coalesce(func.sum(AIUsageEventModel.units), 0)).where(
                AIUsageEventModel.user_id == user_id,
                AIUsageEventModel.feature == feature,
                AIUsageEventModel.created_at >= start,
                AIUsageEventModel.created_at < end,
            )
        )
        ledger_count = int(result.scalar_one() or 0)
        legacy_count = await self._get_legacy_used_today(user_id=user_id, feature=feature, start=start, end=end)
        return max(ledger_count, legacy_count)

    async def get_summary(self, *, user_id: UUID, feature: str) -> AIUsageSummary:
        _, reset_at = self.today_utc_bounds()
        daily_limit = await self.get_daily_limit(user_id=user_id, feature=feature)
        used_today = await self.get_used_today(user_id=user_id, feature=feature)
        return AIUsageSummary(
            feature=feature,
            used_today=used_today,
            daily_limit=daily_limit,
            remaining_today=max(0, daily_limit - used_today),
            reset_at=reset_at,
        )

    async def ensure_available(self, *, user_id: UUID, feature: str) -> AIUsageSummary:
        summary = await self.get_summary(user_id=user_id, feature=feature)
        if summary.remaining_today <= 0:
            retry_in = self.time_until_next_utc_day_label()
            raise HTTPException(
                status_code=429,
                detail=(
                    f"You reached your daily limit of {summary.daily_limit} AI requests. "
                    f"Try again in {retry_in}."
                ),
            )
        return summary

    async def record_usage(
        self,
        *,
        user_id: UUID,
        feature: str,
        units: int = 1,
        source: str = "base_daily",
        reference_type: str | None = None,
        reference_id: UUID | None = None,
    ) -> AIUsageEventModel:
        event = AIUsageEventModel(
            user_id=user_id,
            feature=feature,
            units=max(1, units),
            source=source,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def _get_legacy_used_today(
        self,
        *,
        user_id: UUID,
        feature: str,
        start: datetime,
        end: datetime,
    ) -> int:
        if feature == AIFeature.CV_JOB_SEARCH:
            result = await self.session.execute(
                select(func.count(JobAnalysisModel.id)).where(
                    JobAnalysisModel.user_id == user_id,
                    JobAnalysisModel.created_at >= start,
                    JobAnalysisModel.created_at < end,
                )
            )
            return int(result.scalar_one() or 0)

        if feature == AIFeature.RESUME_COURSE_AUDIT:
            result = await self.session.execute(
                select(func.count(ResumeCourseEvaluationModel.id)).where(
                    ResumeCourseEvaluationModel.user_id == user_id,
                    ResumeCourseEvaluationModel.created_at >= start,
                    ResumeCourseEvaluationModel.created_at < end,
                )
            )
            return int(result.scalar_one() or 0)

        return 0
