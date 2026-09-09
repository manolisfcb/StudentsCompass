"""Reading job postings for the skills they ask for.

Split out of ``CapstoneAnalyticsService`` by TASK-023, which F-19 named among
the eight responsibilities that class held at once. The batching and the
idempotency here are TASK-019's and are unchanged: the sweep works in bounded
batches with one read and one insert each, and
``uq_job_skills_posting_skill_method`` plus ``ON CONFLICT DO NOTHING`` are what
make a repeated or concurrent extraction a no-op rather than a duplicate.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.jobPostingModel import JobPosting
from app.models.skillModel import JobSkillModel, SkillModel
from app.services.analytics.jobPostingText import job_posting_text
from app.services.analytics.skillExtractionService import SkillExtractionService


class JobSkillExtractionService:
    """Extract the skills a posting asks for, once, however often it is asked."""

    #: Postings whose links are written and committed together. Bounds both the
    #: size of a single INSERT and how much work a failure throws away; the
    #: sweep is capped at 500 postings, so this is at most 10 commits.
    JOB_SKILL_EXTRACTION_BATCH_SIZE = 50

    def __init__(self, session: AsyncSession):
        self.session = session
        self.skill_extraction_service = SkillExtractionService(session)

    async def build_skill_lookup(self) -> dict[str, SkillModel]:
        return await self.skill_extraction_service.build_skill_lookup()

    async def _existing_job_skill_links(
        self, job_posting_ids: list[UUID], extraction_method: str
    ) -> dict[UUID, dict[UUID, JobSkillModel]]:
        """Links already stored for these postings, keyed by posting then skill.

        One query for the whole batch. The per-posting version of this read is
        what made the sweep cost a query per job.
        """
        if not job_posting_ids:
            return {}
        result = await self.session.execute(
            select(JobSkillModel).where(
                JobSkillModel.job_posting_id.in_(job_posting_ids),
                JobSkillModel.extraction_method == extraction_method,
            )
        )
        by_posting: dict[UUID, dict[UUID, JobSkillModel]] = {}
        for link in result.scalars().all():
            by_posting.setdefault(link.job_posting_id, {})[link.skill_id] = link
        return by_posting

    async def _insert_job_skill_links(self, rows: list[dict]) -> None:
        """Insert links, ignoring the ones a concurrent extraction already wrote.

        ``uq_job_skills_posting_skill_method`` is what actually makes the
        extraction idempotent: reading the existing links and then inserting the
        missing ones is a check-then-act, and two sweeps running together both
        read the same empty set. Conflicts are skipped rather than raised so one
        racing row does not abort the whole batch.
        """
        if not rows:
            return
        dialect = self.session.bind.dialect.name if self.session.bind is not None else ""
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as dialect_insert
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as dialect_insert
        else:  # pragma: no cover — no other engine is supported by the project
            self.session.add_all([JobSkillModel(**row) for row in rows])
            return

        statement = dialect_insert(JobSkillModel).values(rows)
        await self.session.execute(
            statement.on_conflict_do_nothing(
                index_elements=["job_posting_id", "skill_id", "extraction_method"],
                index_where=JobSkillModel.__table__.c.job_posting_id.isnot(None),
            )
        )

    async def _job_skill_rows_for(
        self,
        job_posting: JobPosting,
        *,
        extraction_method: str,
        lookup: dict[str, SkillModel] | None,
        existing_by_skill_id: dict[UUID, JobSkillModel],
    ) -> tuple[list[UUID], list[dict]] | None:
        """``(skill ids matched, rows to insert)``, or ``None`` for a posting with no text.

        ``None`` is not the same as an empty match: a posting whose text is
        blank is skipped entirely, which is what the per-posting extraction
        always did, links or no links. Touches no database.
        """
        text = job_posting_text(job_posting)
        if not text.strip():
            return None

        matches = await self.skill_extraction_service.extract_known_skills_from_text(
            text,
            lookup=lookup,
            extraction_method=extraction_method,
        )
        target_role = self._infer_target_role(job_posting.title)
        now = datetime.utcnow()

        matched_skill_ids: list[UUID] = []
        rows: list[dict] = []
        seen: set[UUID] = set()
        for match in matches:
            if match.skill.id in seen:
                continue
            seen.add(match.skill.id)
            matched_skill_ids.append(match.skill.id)
            if match.skill.id in existing_by_skill_id:
                continue
            rows.append(
                {
                    "id": uuid4(),
                    "job_posting_id": job_posting.id,
                    "skill_id": match.skill.id,
                    "target_role": target_role,
                    "importance_score": 0.75,
                    "extraction_method": match.extraction_method,
                    "evidence_text": match.evidence_text,
                    "created_at": now,
                }
            )
        return matched_skill_ids, rows

    async def extract_job_skills_from_job_posting(
        self,
        *,
        job_posting_id: UUID,
        extraction_method: str = "job_posting_rules_v1",
        lookup: dict[str, SkillModel] | None = None,
    ) -> list[JobSkillModel]:
        job_posting = await self.session.get(JobPosting, job_posting_id)
        if job_posting is None:
            return []

        existing = await self._existing_job_skill_links([job_posting.id], extraction_method)
        extracted = await self._job_skill_rows_for(
            job_posting,
            extraction_method=extraction_method,
            lookup=lookup,
            existing_by_skill_id=existing.get(job_posting.id, {}),
        )
        if extracted is None:
            return []
        matched_skill_ids, rows = extracted
        await self._insert_job_skill_links(rows)
        await self.session.commit()

        # Read back rather than returning the objects just built: a concurrent
        # extraction may have won the conflict, and the caller must see the row
        # that is actually stored. One link per match, in match order, as before.
        stored = (await self._existing_job_skill_links([job_posting.id], extraction_method)).get(
            job_posting.id, {}
        )
        return [stored[skill_id] for skill_id in matched_skill_ids if skill_id in stored]

    async def extract_job_skills_for_open_postings(self, *, limit: int = 100) -> dict[str, int]:
        extraction_method = "job_posting_rules_v1"
        result = await self.session.execute(
            select(JobPosting)
            .where(JobPosting.is_active.is_(True))
            .order_by(JobPosting.created_at.desc())
            .limit(max(1, min(limit, 500)))
        )
        jobs = list(result.scalars().all())
        if not jobs:
            return {"jobs_scanned": 0, "jobs_with_matches": 0, "job_skill_links": 0}

        # Build the skill lookup once for the whole batch instead of reloading
        # the full skills + aliases tables for every job.
        lookup = await self.build_skill_lookup()

        jobs_with_matches = 0
        total_links = 0
        batch_size = self.JOB_SKILL_EXTRACTION_BATCH_SIZE
        for start in range(0, len(jobs), batch_size):
            batch = jobs[start : start + batch_size]
            # One read and one write per batch, not per posting.
            existing = await self._existing_job_skill_links(
                [job.id for job in batch], extraction_method
            )
            pending: list[dict] = []
            for job in batch:
                already = existing.get(job.id, {})
                extracted = await self._job_skill_rows_for(
                    job,
                    extraction_method=extraction_method,
                    lookup=lookup,
                    existing_by_skill_id=already,
                )
                if extracted is None:
                    # A posting with no text contributes nothing and is not
                    # counted as matched, exactly as before.
                    continue
                matched_skill_ids, rows = extracted
                total_links += len(matched_skill_ids)
                if matched_skill_ids:
                    jobs_with_matches += 1
                pending.extend(rows)

            await self._insert_job_skill_links(pending)
            await self.session.commit()

        return {
            "jobs_scanned": len(jobs),
            "jobs_with_matches": jobs_with_matches,
            "job_skill_links": total_links,
        }

    async def get_job_skills(self, job_posting_id: UUID) -> list[dict]:
        result = await self.session.execute(
            select(JobSkillModel)
            .options(selectinload(JobSkillModel.skill))
            .where(JobSkillModel.job_posting_id == job_posting_id)
        )
        job_skills = result.scalars().all()
        return [
            {
                "skill_id": str(job_skill.skill_id),
                "normalized_name": job_skill.skill.normalized_name,
                "display_name": job_skill.skill.display_name,
                "category": job_skill.skill.category,
                "importance_score": job_skill.importance_score,
                "evidence_text": job_skill.evidence_text,
                "extraction_method": job_skill.extraction_method,
            }
            for job_skill in sorted(job_skills, key=lambda item: item.skill.display_name.lower())
        ]

    @staticmethod
    def _infer_target_role(title: str | None) -> str | None:
        normalized_title = (title or "").lower()
        if "business analyst" in normalized_title:
            return "Business Analyst"
        if "data scientist" in normalized_title:
            return "Junior Data Scientist"
        if "data analyst" in normalized_title:
            return "Data Analyst"
        return None
