from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import and_, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import AI_BASE_DAILY_LIMIT
from app.models.aiUsageModel import AIQuotaGrantModel, AIUsageEventModel, AIUsageStatus
from app.models.jobAnalysisModel import JobAnalysisModel
from app.models.resumeCourseEvaluationModel import ResumeCourseEvaluationModel
from app.services.ratelimit.counterStore import CounterStore, CounterStoreError, get_counter_store

LOGGER = logging.getLogger(__name__)

# Quota keys are date-stamped (UTC), so a fixed TTL comfortably past midnight is
# enough — the next day naturally lands on a fresh key.
_QUOTA_TTL_SECONDS = 36 * 3600

# How long a claimed-but-unsettled slot keeps counting against the daily
# allowance. Long enough for the slowest analysis to finish, short enough that a
# process killed mid-request does not cost the user a slot for the rest of the
# day. Reclaiming is what closes the "retained quota" hole: an abandoned
# reservation is reclaimed on the owner's next attempt, not at midnight.
RESERVATION_LEASE_SECONDS = 15 * 60

# Reasons recorded on the ledger row when a reservation is handed back. They
# separate *provider spend* from *user entitlement*: a failed attempt may well
# have cost money at the provider (the global budget guard counts every attempt,
# including retries), but the user's daily slot is only consumed by a result.
RELEASE_NO_SPEND = "released_no_spend"
RELEASE_AFTER_ATTEMPT = "released_after_provider_attempt"
RELEASE_DUPLICATE = "released_duplicate_reference"


class AIFeature:
    CV_JOB_SEARCH = "cv_job_search"
    RESUME_COURSE_AUDIT = "resume_course_audit"
    MOCK_INTERVIEW = "mock_interview"


# Legacy tables that recorded an AI spend before the ledger existed. Each entry
# maps a feature to the table whose rows *are* the historical attempts, and to
# the ``reference_type`` a ledger row uses to point back at one. Reconciliation
# is by identity through that reference, never by comparing bare counts.
LEGACY_SOURCES: dict[str, tuple[type, str]] = {
    AIFeature.CV_JOB_SEARCH: (JobAnalysisModel, "job_analysis"),
    AIFeature.RESUME_COURSE_AUDIT: (ResumeCourseEvaluationModel, "resume_course_evaluation"),
}


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

    Created by :meth:`AIUsageService.reserve` *before* the LLM call, and backed
    by a durable ledger row (``status='reserved'``) so the claim survives the
    request that made it. Exactly one thing may happen to it afterwards:

    * :meth:`AIUsageService.commit_usage` — the spend produced a result, so the
      row becomes ``committed`` and counts against the daily allowance.
    * :meth:`release` — no result, so the slot goes back.
    * neither, because the process died: the lease expires and the slot is
      reclaimed on the user's next reservation.
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
    # The durable half of the reservation. None only if the ledger row could not
    # be written, in which case the Redis counter is the sole record.
    event_id: UUID | None = None
    # Where the ledger row can be settled from. The reservation outlives the
    # request that created it (the CV analysis runs in a background task with
    # its own session), so both a live session and its engine are kept.
    session: AsyncSession | None = field(default=None, repr=False)
    bind: AsyncEngine | None = field(default=None, repr=False)

    async def release(self, *, reason: str = RELEASE_NO_SPEND) -> None:
        """Hand the slot back.

        ``reason`` is recorded on the ledger row so the difference between "no
        provider call happened" and "a provider call was attempted and failed"
        stays visible in the data instead of being flattened into a deletion.
        """
        if self.committed or self.released:
            return
        self.released = True
        await self._settle_ledger_row(AIUsageStatus.RELEASED, reason)
        if self.db_fallback:
            return
        try:
            await self.store.decr(self.key)
        except CounterStoreError:
            # Best-effort: the date-stamped key expires on its own, and the
            # ledger row above is already the authoritative record.
            LOGGER.warning("Could not release AI quota reservation for key %s", self.key)

    async def _settle_ledger_row(self, status: str, reason: str) -> None:
        if self.event_id is None:
            return
        statement = (
            update(AIUsageEventModel)
            .where(
                AIUsageEventModel.id == self.event_id,
                AIUsageEventModel.status == AIUsageStatus.RESERVED,
            )
            .values(status=status, source=reason, expires_at=None)
        )

        # Inside a live transaction, join it: the caller commits (it is about to
        # record the failure anyway) and the release lands with that record.
        session = self.session
        if session is not None:
            try:
                if session.in_transaction():
                    await session.execute(statement)
                    return
            except SQLAlchemyError:
                LOGGER.warning("Could not release ledger row %s on the owning session", self.event_id)

        # Otherwise the owning request is long gone (background task): settle in
        # a short transaction of its own on the same engine.
        bind = self.bind
        if bind is None:
            return
        try:
            factory = async_sessionmaker(bind, class_=AsyncSession, expire_on_commit=False)
            async with factory() as own_session:
                await own_session.execute(statement)
                await own_session.commit()
        except SQLAlchemyError:
            # The lease is the backstop: the row is reclaimed on the next reserve.
            LOGGER.warning("Could not release ledger row %s; leaving it to the lease", self.event_id)


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

    @staticmethod
    def _counts_against_quota(now: datetime):
        """Rows that consume allowance: settled spends and live reservations.

        Released, expired and superseded rows are history, not consumption; an
        expired reservation stops counting the moment its lease passes, with no
        write required, so a read path never has to repair state.
        """
        return or_(
            AIUsageEventModel.status == AIUsageStatus.COMMITTED,
            and_(
                AIUsageEventModel.status == AIUsageStatus.RESERVED,
                or_(AIUsageEventModel.expires_at.is_(None), AIUsageEventModel.expires_at > now),
            ),
        )

    async def get_used_today(self, *, user_id: UUID, feature: str) -> int:
        """Allowance consumed today, read from the ledger alone.

        The ledger is the only authority: legacy rows were reconciled into it by
        identity (see the ``ai_usage_events`` reservation-cycle migration), so
        the old ``max(ledger, legacy_count)`` guess — which could not tell a
        missing ledger row from a legitimately cheaper day — is gone.
        """
        start, end = self.today_utc_bounds()
        result = await self.session.execute(
            select(func.coalesce(func.sum(AIUsageEventModel.units), 0)).where(
                AIUsageEventModel.user_id == user_id,
                AIUsageEventModel.feature == feature,
                AIUsageEventModel.created_at >= start,
                AIUsageEventModel.created_at < end,
                self._counts_against_quota(datetime.utcnow()),
            )
        )
        return int(result.scalar_one() or 0)

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

    async def _reclaim_expired_reservations(self, *, user_id: UUID, feature: str, store: CounterStore, key: str) -> int:
        """Close out reservations nobody ever settled, and give back their slots.

        The UPDATE is the arbiter: only the caller whose statement actually
        matched a row may decrement the shared counter for it, so two concurrent
        reservations can never release the same abandoned slot twice. It runs in
        a transaction of its own — committed before the counter moves, and never
        entangled with whatever the caller is about to do.
        """
        bind = self._async_bind()
        if bind is None:
            # Without an engine to open an independent transaction on there is no
            # safe way to make the reclaim durable before lowering the shared
            # counter. Skipping it costs nothing correctness-wise: an expired
            # reservation already stops counting in the database by predicate.
            return 0

        now = datetime.utcnow()
        statement = (
            update(AIUsageEventModel)
            .where(
                AIUsageEventModel.user_id == user_id,
                AIUsageEventModel.feature == feature,
                AIUsageEventModel.status == AIUsageStatus.RESERVED,
                AIUsageEventModel.expires_at.is_not(None),
                AIUsageEventModel.expires_at <= now,
            )
            .values(status=AIUsageStatus.EXPIRED, expires_at=None)
        )
        factory = async_sessionmaker(bind, class_=AsyncSession, expire_on_commit=False)
        async with factory() as own_session:
            result = await own_session.execute(statement)
            reclaimed = int(result.rowcount or 0)
            await own_session.commit()
        if not reclaimed:
            return 0

        try:
            # Only lower an existing counter. Decrementing a missing key would
            # create it without a TTL and, worse, make the next reservation seed
            # from 1 instead of from real usage.
            current = await store.get_int(key)
            if current > 0:
                await store.decr(key, amount=min(reclaimed, current))
        except CounterStoreError:
            LOGGER.warning("Could not return %s reclaimed AI slots to key %s", reclaimed, key)
        LOGGER.info("Reclaimed %s expired AI reservation(s) for user %s / %s", reclaimed, user_id, feature)
        return reclaimed

    async def reserve(self, *, user_id: UUID, feature: str) -> QuotaReservation:
        """Atomically claim one daily AI slot *before* spending on the LLM.

        Two records back a reservation. An atomic counter (Redis when
        configured) closes the read-then-write race across replicas, so N
        concurrent requests cannot all pass the check. A ledger row makes the
        claim durable and auditable, and carries the lease that reclaims it if
        the caller never settles. The caller must :meth:`commit_usage` on
        success or ``reservation.release()`` on failure before the spend.
        """
        daily_limit = await self.get_daily_limit(user_id=user_id, feature=feature)
        store = get_counter_store()
        key = self._quota_key(user_id, feature)

        await self._reclaim_expired_reservations(user_id=user_id, feature=feature, store=store, key=key)

        # Seed the atomic counter from durable DB usage so a counter reset
        # (process restart / fresh Redis) can never hand back already-spent quota.
        db_used = await self.get_used_today(user_id=user_id, feature=feature)

        db_fallback = False
        try:
            new_value = await store.reserve_incr(key, base=db_used, ttl_seconds=_QUOTA_TTL_SECONDS)
        except CounterStoreError:
            # Redis unreachable: best-effort DB count (not atomic, but the global
            # budget guard remains the hard cost ceiling). Fail closed on limit.
            LOGGER.warning("AI quota counter unavailable; falling back to DB count for user %s", user_id)
            if db_used >= daily_limit:
                raise self._limit_exceeded(daily_limit)
            db_fallback = True
        else:
            if new_value > daily_limit:
                try:
                    await store.decr(key)
                except CounterStoreError:
                    pass
                raise self._limit_exceeded(daily_limit)

        event = AIUsageEventModel(
            user_id=user_id,
            feature=feature,
            units=1,
            source="reserved",
            status=AIUsageStatus.RESERVED,
            expires_at=datetime.utcnow() + timedelta(seconds=RESERVATION_LEASE_SECONDS),
        )
        self.session.add(event)
        await self.session.flush()

        return QuotaReservation(
            user_id=user_id,
            feature=feature,
            key=key,
            store=store,
            db_fallback=db_fallback,
            event_id=event.id,
            session=self.session,
            bind=self._async_bind(),
        )

    def _async_bind(self) -> AsyncEngine | None:
        bind = getattr(self.session, "bind", None)
        return bind if isinstance(bind, AsyncEngine) else None

    async def commit_usage(
        self,
        reservation: QuotaReservation,
        *,
        units: int = 1,
        source: str = "base_daily",
        reference_type: str | None = None,
        reference_id: UUID | None = None,
    ) -> AIUsageEventModel:
        """Settle a reservation as a spend, exactly once per referenced result.

        Idempotent by reference: a replayed commit (retried background task,
        re-delivered job) finds the existing ledger row, hands its own slot back
        and charges nothing extra. Writes through the caller's session on
        purpose, so the charge and the result it pays for commit together.
        """
        if reservation.committed:
            # Called twice on the same reservation: return what it already paid
            # for. Falling through would write a second charge for one result.
            already = await self._find_committed(reference_type, reference_id)
            if already is None and reservation.event_id is not None:
                already = await self.session.get(AIUsageEventModel, reservation.event_id)
            if already is not None:
                return already

        duplicate = await self._find_committed(reference_type, reference_id)
        if duplicate is not None:
            LOGGER.info(
                "AI usage for %s %s is already on the ledger; releasing the duplicate reservation",
                reference_type,
                reference_id,
            )
            await reservation.release(reason=RELEASE_DUPLICATE)
            return duplicate

        reserved = await self._load_reserved_row(reservation)
        if reserved is None:
            # The reservation row never made it to the database (its transaction
            # rolled back, or Redis was the only record): the spend still has to
            # be recorded, so write the settled row directly.
            charged = await self.record_usage(
                user_id=reservation.user_id,
                feature=reservation.feature,
                units=units,
                source=source,
                reference_type=reference_type,
                reference_id=reference_id,
            )
            reservation.committed = True
            return charged

        settled = await self._settle_reserved(
            reservation.event_id,
            units=units,
            source=source,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        if not settled:
            # Lost the race for this reference: the other transaction's row is
            # the charge, and this reservation gives its slot back.
            winner = await self._find_committed(reference_type, reference_id)
            await reservation.release(reason=RELEASE_DUPLICATE)
            if winner is not None:
                return winner
            raise RuntimeError("the reservation could not be settled and no charge was found")

        reservation.committed = True
        await self.session.refresh(reserved)
        return reserved

    async def _settle_reserved(
        self,
        event_id: UUID | None,
        *,
        units: int,
        source: str,
        reference_type: str | None,
        reference_id: UUID | None,
    ) -> bool:
        """Turn a reserved row into a charge; False if the reference is taken.

        Deliberately a Core UPDATE inside a SAVEPOINT rather than an ORM flush.
        A failed *flush* poisons the whole session — the caller would lose the
        result it was about to commit — while a failed statement inside a
        savepoint only rolls back to the savepoint and leaves the session usable.
        """
        statement = (
            update(AIUsageEventModel)
            .where(
                AIUsageEventModel.id == event_id,
                AIUsageEventModel.status == AIUsageStatus.RESERVED,
            )
            .values(
                units=max(1, units),
                source=source,
                reference_type=reference_type,
                reference_id=reference_id,
                status=AIUsageStatus.COMMITTED,
                expires_at=None,
            )
        )
        try:
            async with self.session.begin_nested():
                result = await self.session.execute(statement)
        except IntegrityError:
            return False
        return bool(result.rowcount)

    async def _load_reserved_row(self, reservation: QuotaReservation) -> AIUsageEventModel | None:
        if reservation.event_id is None:
            return None
        event = await self.session.get(AIUsageEventModel, reservation.event_id)
        if event is None or event.status != AIUsageStatus.RESERVED:
            return None
        return event

    async def _find_committed(
        self,
        reference_type: str | None,
        reference_id: UUID | None,
    ) -> AIUsageEventModel | None:
        if reference_type is None or reference_id is None:
            return None
        return await self.session.scalar(
            select(AIUsageEventModel).where(
                AIUsageEventModel.reference_type == reference_type,
                AIUsageEventModel.reference_id == reference_id,
                AIUsageEventModel.status == AIUsageStatus.COMMITTED,
            )
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
        """Write a settled charge, at most once per referenced object."""
        existing = await self._find_committed(reference_type, reference_id)
        if existing is not None:
            return existing

        event_id = uuid4()
        statement = insert(AIUsageEventModel).values(
            id=event_id,
            user_id=user_id,
            feature=feature,
            units=max(1, units),
            source=source,
            reference_type=reference_type,
            reference_id=reference_id,
            status=AIUsageStatus.COMMITTED,
            created_at=datetime.utcnow(),
        )
        try:
            # Same reason as _settle_reserved: a losing INSERT must cost the
            # caller a savepoint, not its whole transaction.
            async with self.session.begin_nested():
                await self.session.execute(statement)
        except IntegrityError:
            winner = await self._find_committed(reference_type, reference_id)
            if winner is None:
                raise
            return winner
        return await self.session.get(AIUsageEventModel, event_id)

    async def legacy_parity_gaps(self, *, feature: str, user_id: UUID | None = None) -> list[dict]:
        """Rows in a legacy table with no ledger row pointing at them.

        The reconciliation evidence: an empty result means every historical
        attempt of ``feature`` is represented on the ledger by identity, which
        is the precondition for reading usage from the ledger alone. Kept in the
        service (not only in the migration) so the check can be re-run later.
        """
        source = LEGACY_SOURCES.get(feature)
        if source is None:
            return []
        model, reference_type = source
        matched = select(AIUsageEventModel.id).where(
            AIUsageEventModel.reference_type == reference_type,
            AIUsageEventModel.reference_id == model.id,
            AIUsageEventModel.status.in_([AIUsageStatus.COMMITTED, AIUsageStatus.SUPERSEDED]),
        )
        query = select(model.id, model.user_id, model.created_at).where(~matched.exists())
        if user_id is not None:
            query = query.where(model.user_id == user_id)
        rows = (await self.session.execute(query.order_by(model.created_at))).all()
        return [
            {"reference_type": reference_type, "reference_id": row[0], "user_id": row[1], "created_at": row[2]}
            for row in rows
        ]

    async def _get_legacy_used_today(
        self,
        *,
        user_id: UUID,
        feature: str,
        start: datetime,
        end: datetime,
    ) -> int:
        """Count of legacy rows for the day — reconciliation evidence only.

        No longer part of the quota read path: the ledger answers that. It stays
        as the "before" side of the parity comparison.
        """
        source = LEGACY_SOURCES.get(feature)
        if source is None:
            return 0
        model, _ = source
        result = await self.session.execute(
            select(func.count(model.id)).where(
                model.user_id == user_id,
                model.created_at >= start,
                model.created_at < end,
            )
        )
        return int(result.scalar_one() or 0)
