from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import AI_BASE_DAILY_LIMIT
from app.models.aiUsageModel import AIQuotaGrantModel, AIUsageEventModel
from app.models.jobAnalysisModel import JobAnalysisModel
from app.models.resumeCourseEvaluationModel import ResumeCourseEvaluationModel
from app.services.ratelimit.counterStore import CounterStore, CounterStoreError, get_counter_store

LOGGER = logging.getLogger(__name__)

# Quota keys are date-stamped (UTC), so a fixed TTL comfortably past midnight is
# enough — the next day naturally lands on a fresh key.
_QUOTA_TTL_SECONDS = 36 * 3600


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


@dataclass
class QuotaReservation:
    """A single atomically-reserved AI request slot.

    Created by :meth:`AIUsageService.reserve` *before* the LLM call. Call
    :meth:`release` if the request fails before spending so the slot is handed
    back; otherwise persist it with :meth:`AIUsageService.commit_usage`.
    """

    user_id: UUID
    feature: str
    key: str
    store: CounterStore = field(repr=False)
    # When True the reservation is backed only by the DB fallback path (Redis
    # was unavailable), so there is no Redis counter to release.
    db_fallback: bool = False
    committed: bool = False
    released: bool = False

    async def release(self) -> None:
        if self.committed or self.released or self.db_fallback:
            return
        self.released = True
        try:
            await self.store.decr(self.key)
        except CounterStoreError:
            # Best-effort: the date-stamped key expires on its own.
            LOGGER.warning("Could not release AI quota reservation for key %s", self.key)


class AIUsageService:
    BASE_DAILY_LIMIT = AI_BASE_DAILY_LIMIT

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

    async def resolve_base_daily_limit(self, *, user_id: UUID, feature: str) -> int:
        """Per-user base daily allowance before time-bound grants are added.

        Single seam for paid plans: when billing exists, map the user's plan to
        a base limit here (e.g. read a ``plan`` column / subscription) instead of
        the flat free-tier value. Everything downstream already composes this
        with :class:`AIQuotaGrantModel` extra units, so nothing else changes.
        """
        return self.BASE_DAILY_LIMIT

    async def get_daily_limit(self, *, user_id: UUID, feature: str) -> int:
        base = await self.resolve_base_daily_limit(user_id=user_id, feature=feature)
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
        return base + max(0, extra_units)

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
            raise self._limit_exceeded(summary.daily_limit)
        return summary

    def _limit_exceeded(self, daily_limit: int) -> HTTPException:
        retry_in = self.time_until_next_utc_day_label()
        return HTTPException(
            status_code=429,
            detail=(
                f"You reached your daily limit of {daily_limit} AI requests. "
                f"Try again in {retry_in}."
            ),
        )

    @staticmethod
    def _quota_key(user_id: UUID, feature: str) -> str:
        day = datetime.utcnow().strftime("%Y%m%d")
        return f"ai:quota:{user_id}:{feature}:{day}"

    async def reserve(self, *, user_id: UUID, feature: str) -> QuotaReservation:
        """Atomically claim one daily AI slot *before* spending on the LLM.

        Uses an atomic counter (Redis when configured) so that N concurrent
        requests cannot all pass the check and overspend — only callers whose
        post-increment value stays within the resolved daily limit proceed.
        Closes the read-then-write (TOCTOU) race the old ``ensure_available``
        path had. The caller must :meth:`commit_usage` on success or
        ``reservation.release()`` on failure before the spend.
        """
        daily_limit = await self.get_daily_limit(user_id=user_id, feature=feature)
        store = get_counter_store()
        key = self._quota_key(user_id, feature)
        # Seed the atomic counter from durable DB usage so a counter reset
        # (process restart / fresh Redis) can never hand back already-spent quota.
        db_used = await self.get_used_today(user_id=user_id, feature=feature)

        try:
            new_value = await store.reserve_incr(key, base=db_used, ttl_seconds=_QUOTA_TTL_SECONDS)
        except CounterStoreError:
            # Redis unreachable: best-effort DB count (not atomic, but the global
            # budget guard remains the hard cost ceiling). Fail closed on limit.
            LOGGER.warning("AI quota counter unavailable; falling back to DB count for user %s", user_id)
            used = await self.get_used_today(user_id=user_id, feature=feature)
            if used >= daily_limit:
                raise self._limit_exceeded(daily_limit)
            return QuotaReservation(user_id=user_id, feature=feature, key=key, store=store, db_fallback=True)

        if new_value > daily_limit:
            try:
                await store.decr(key)
            except CounterStoreError:
                pass
            raise self._limit_exceeded(daily_limit)

        return QuotaReservation(user_id=user_id, feature=feature, key=key, store=store)

    async def commit_usage(
        self,
        reservation: QuotaReservation,
        *,
        units: int = 1,
        source: str = "base_daily",
        reference_type: str | None = None,
        reference_id: UUID | None = None,
    ) -> AIUsageEventModel:
        """Persist a reserved slot to the durable ledger after a successful spend."""
        reservation.committed = True
        return await self.record_usage(
            user_id=reservation.user_id,
            feature=reservation.feature,
            units=units,
            source=source,
            reference_type=reference_type,
            reference_id=reference_id,
        )

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
