"""The life of a pasted vacancy: its shared parse and its lease (TASK-077).

Two halves, matching the two tables:

* **The shared parse cache.** ``job_text_hash`` is the key, so its
  normalization decides the cache hit rate across users. ``store_parse`` lets
  the first writer win: two users pasting the same text at once produce one row.
* **The lease cycle**, copied from ``job_analysis`` (``cvAnalysisService``):
  a claim is one conditional UPDATE, a worker renews before slow steps, and
  recovery never re-runs a target that already reached the provider.
"""
from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import (
    clamp_page_size,
    encode_cursor,
    fetch_probe_limit,
    keyset_before,
    split_probe,
)

from app.models.jobTargetModel import (
    JOB_SOURCE_PASTED,
    JOB_TARGET_STATUS_FAILED,
    JOB_TARGET_STATUS_PARSING,
    JOB_TARGET_STATUS_PENDING,
    JOB_TARGET_STATUS_READY,
    JobDescriptionParseModel,
    JobTargetModel,
)

LOGGER = logging.getLogger(__name__)

#: Same reasoning as ``JOB_LEASE_SECONDS``: comfortably longer than a parse,
#: short enough that a target orphaned by a deploy is recovered in minutes.
JOB_TARGET_LEASE_SECONDS = 300
MAX_JOB_TARGET_ATTEMPTS = 3

INTERRUPTED_AFTER_SPEND_MESSAGE = (
    "The analysis of this job description was interrupted after it started and "
    "is not retried automatically. Please try again."
)
EXHAUSTED_ATTEMPTS_MESSAGE = (
    "The analysis of this job description was interrupted repeatedly and has "
    "stopped retrying. Please try again."
)

_HORIZONTAL_SPACE = re.compile(r"[ \t\f\v ]+")
_BLANK_RUN = re.compile(r"\n{3,}")


def normalize_job_text(text: str | None) -> str:
    """The canonical form of a pasted job description.

    Copying the same posting from two browsers differs in line endings,
    non-breaking spaces, trailing blanks and runs of empty lines, none of which
    changes what the posting says. Those are folded; letters, case and
    punctuation are kept, because they can change it.
    """
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_HORIZONTAL_SPACE.sub(" ", line).strip() for line in normalized.split("\n")]
    return _BLANK_RUN.sub("\n\n", "\n".join(lines)).strip()


def job_text_hash(text: str | None) -> str:
    return hashlib.sha256(normalize_job_text(text).encode("utf-8")).hexdigest()


class JobTargetService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # -- the shared parse cache ------------------------------------------------

    async def get_parse(self, text_hash: str) -> JobDescriptionParseModel | None:
        """The stored parse, reloaded over whatever the session already holds.

        Writes to this table go through Core UPDATEs, which bypass the identity
        map; a plain ``session.get`` would hand back the pre-write object.
        """
        result = await self.session.execute(
            select(JobDescriptionParseModel)
            .where(JobDescriptionParseModel.text_hash == text_hash)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def store_parse(
        self,
        *,
        text_hash: str,
        parsed: dict,
        model_id: str,
        prompt_version: str,
        source: str = JOB_SOURCE_PASTED,
        embedding: list[float] | None = None,
        embedding_model_name: str | None = None,
    ) -> JobDescriptionParseModel:
        """Store a parse unless one exists already; return the stored one.

        The first writer wins, decided by the primary key. A second writer for
        the same text gets the first's row back instead of an IntegrityError,
        and nothing it computed overwrites what other users already rely on.
        """
        if (embedding is None) != (embedding_model_name is None):
            raise ValueError("embedding and embedding_model_name go together")
        now = datetime.utcnow()
        values = {
            "text_hash": text_hash,
            "source": source,
            "parsed": parsed,
            "embedding": embedding,
            "embedding_model_name": embedding_model_name,
            "model_id": model_id,
            "prompt_version": prompt_version,
            "created_at": now,
            "updated_at": now,
        }
        dialect = self.session.bind.dialect.name if self.session.bind is not None else ""
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as dialect_insert
        else:
            from sqlalchemy.dialects.sqlite import insert as dialect_insert
        await self.session.execute(
            dialect_insert(JobDescriptionParseModel)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["text_hash"])
        )
        await self.session.commit()
        stored = await self.session.execute(
            select(JobDescriptionParseModel)
            .where(JobDescriptionParseModel.text_hash == text_hash)
            .execution_options(populate_existing=True)
        )
        return stored.scalar_one()

    # -- a user's targets --------------------------------------------------------

    async def create_target(
        self,
        *,
        user_id: UUID,
        raw_text: str,
        resume_id: UUID | None = None,
        source: str = JOB_SOURCE_PASTED,
    ) -> JobTargetModel:
        """A new pending target. The caller has already capped ``raw_text``."""
        target = JobTargetModel(
            user_id=user_id,
            resume_id=resume_id,
            raw_text=raw_text,
            text_hash=job_text_hash(raw_text),
            source=source,
            status=JOB_TARGET_STATUS_PENDING,
        )
        self.session.add(target)
        await self.session.commit()
        await self.session.refresh(target)
        return target

    async def get_user_target(self, *, target_id: UUID, user_id: UUID) -> JobTargetModel | None:
        return await self.session.scalar(
            select(JobTargetModel).where(
                JobTargetModel.id == target_id, JobTargetModel.user_id == user_id
            )
        )

    async def list_user_target_page(
        self, *, user_id: UUID, before: str | None = None, limit: int | None = None
    ) -> tuple[list[JobTargetModel], str | None, bool, int]:
        """One page of the user's targets, newest first.

        ``user_id`` is in the WHERE, so a cursor taken from someone else's list
        addresses nothing here. Raises ``InvalidCursor`` for a malformed one.
        """
        page_size = clamp_page_size(limit)
        conditions = [JobTargetModel.user_id == user_id]
        if before:
            conditions.append(keyset_before(JobTargetModel.created_at, JobTargetModel.id, before))
        result = await self.session.execute(
            select(JobTargetModel)
            .where(*conditions)
            .order_by(JobTargetModel.created_at.desc(), JobTargetModel.id.desc())
            .limit(fetch_probe_limit(page_size))
        )
        rows, has_more = split_probe(list(result.scalars().all()), page_size)
        next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if rows and has_more else None
        return rows, next_cursor, has_more, page_size

    # -- the lease cycle ---------------------------------------------------------

    async def claim(self, target_id: UUID) -> bool:
        """Take one lease on a target. False if another worker holds it.

        The row moves to ``parsing`` only from ``pending`` or from a lease that
        has run out, in a single UPDATE: two workers cannot both start it.
        """
        now = datetime.utcnow()
        result = await self.session.execute(
            update(JobTargetModel)
            .where(
                JobTargetModel.id == target_id,
                or_(
                    JobTargetModel.status == JOB_TARGET_STATUS_PENDING,
                    (JobTargetModel.status == JOB_TARGET_STATUS_PARSING)
                    & JobTargetModel.lease_expires_at.is_not(None)
                    & (JobTargetModel.lease_expires_at <= now),
                ),
            )
            .values(
                status=JOB_TARGET_STATUS_PARSING,
                attempts=JobTargetModel.attempts + 1,
                lease_expires_at=now + timedelta(seconds=JOB_TARGET_LEASE_SECONDS),
                updated_at=now,
            )
        )
        await self.session.commit()
        return bool(result.rowcount)

    async def renew_lease(self, target_id: UUID) -> None:
        now = datetime.utcnow()
        await self.session.execute(
            update(JobTargetModel)
            .where(JobTargetModel.id == target_id, JobTargetModel.status == JOB_TARGET_STATUS_PARSING)
            .values(lease_expires_at=now + timedelta(seconds=JOB_TARGET_LEASE_SECONDS), updated_at=now)
        )
        await self.session.commit()

    async def mark_provider_attempted(self, target_id: UUID) -> None:
        """Stamp *before* a paid call, and push the lease out for it.

        From here on an interruption is uncertain — the money may be spent —
        so recovery fails the target instead of paying again.
        """
        now = datetime.utcnow()
        await self.session.execute(
            update(JobTargetModel)
            .where(JobTargetModel.id == target_id, JobTargetModel.status == JOB_TARGET_STATUS_PARSING)
            .values(
                provider_attempted_at=now,
                lease_expires_at=now + timedelta(seconds=JOB_TARGET_LEASE_SECONDS),
                updated_at=now,
            )
        )
        await self.session.commit()

    async def complete(
        self,
        target_id: UUID,
        *,
        match_snapshot: dict | None = None,
        title: str | None = None,
        company: str | None = None,
        location: str | None = None,
        workplace_type: str | None = None,
    ) -> bool:
        """``parsing`` → ``ready``. False if this worker no longer holds it."""
        now = datetime.utcnow()
        values: dict = {
            "status": JOB_TARGET_STATUS_READY,
            "lease_expires_at": None,
            "error_message": None,
            "match_snapshot": match_snapshot,
            "updated_at": now,
        }
        for field, value in (
            ("title", title),
            ("company", company),
            ("location", location),
            ("workplace_type", workplace_type),
        ):
            if value is not None:
                values[field] = value
        result = await self.session.execute(
            update(JobTargetModel)
            .where(JobTargetModel.id == target_id, JobTargetModel.status == JOB_TARGET_STATUS_PARSING)
            .values(**values)
        )
        await self.session.commit()
        return bool(result.rowcount)

    async def fail(self, target_id: UUID, message: str) -> None:
        now = datetime.utcnow()
        await self.session.execute(
            update(JobTargetModel)
            .where(
                JobTargetModel.id == target_id,
                JobTargetModel.status.in_((JOB_TARGET_STATUS_PENDING, JOB_TARGET_STATUS_PARSING)),
            )
            .values(
                status=JOB_TARGET_STATUS_FAILED,
                error_message=message,
                lease_expires_at=None,
                updated_at=now,
            )
        )
        await self.session.commit()

    async def recover_stale(self) -> dict[str, int]:
        """Decide what to do with targets whose worker never came back.

        Same three outcomes as ``recover_stale_jobs``: after spending → failed
        with a reason; out of attempts → failed; otherwise back to pending.
        """
        now = datetime.utcnow()
        stale = (
            JobTargetModel.status == JOB_TARGET_STATUS_PARSING,
            JobTargetModel.lease_expires_at.is_not(None),
            JobTargetModel.lease_expires_at <= now,
        )
        uncertain = await self.session.execute(
            update(JobTargetModel)
            .where(*stale, JobTargetModel.provider_attempted_at.is_not(None))
            .values(
                status=JOB_TARGET_STATUS_FAILED,
                error_message=INTERRUPTED_AFTER_SPEND_MESSAGE,
                lease_expires_at=None,
                updated_at=now,
            )
        )
        exhausted = await self.session.execute(
            update(JobTargetModel)
            .where(
                *stale,
                JobTargetModel.provider_attempted_at.is_(None),
                JobTargetModel.attempts >= MAX_JOB_TARGET_ATTEMPTS,
            )
            .values(
                status=JOB_TARGET_STATUS_FAILED,
                error_message=EXHAUSTED_ATTEMPTS_MESSAGE,
                lease_expires_at=None,
                updated_at=now,
            )
        )
        requeued = await self.session.execute(
            update(JobTargetModel)
            .where(
                *stale,
                JobTargetModel.provider_attempted_at.is_(None),
                JobTargetModel.attempts < MAX_JOB_TARGET_ATTEMPTS,
            )
            .values(status=JOB_TARGET_STATUS_PENDING, lease_expires_at=None, updated_at=now)
        )
        await self.session.commit()
        outcome = {
            "failed_after_spend": int(uncertain.rowcount or 0),
            "failed_attempts_exhausted": int(exhausted.rowcount or 0),
            "requeued": int(requeued.rowcount or 0),
        }
        if any(outcome.values()):
            LOGGER.info("Recovered stale job targets: %s", outcome)
        return outcome

    async def due_target_ids(self, *, limit: int = 5) -> list[UUID]:
        result = await self.session.execute(
            select(JobTargetModel.id)
            .where(JobTargetModel.status == JOB_TARGET_STATUS_PENDING)
            .order_by(JobTargetModel.created_at)
            .limit(limit)
        )
        return list(result.scalars())
