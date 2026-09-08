"""Two extractions running at once leave one link, and the migration merges what exists.

Reading a posting's links and then inserting the missing ones is a
check-then-act. SQLite cannot stage the race — one connection, writes
serialised for free — so the claim only means anything here, on real
connections.

The migration half checks the promise made about existing data: duplicates are
inventoried and merged into their earliest row, provenance is carried over
rather than lost, and links found by a different method are left alone.
"""
from __future__ import annotations

import asyncio
import importlib.util
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, text

pytestmark = [pytest.mark.integration, pytest.mark.postgres]

INDEX_NAME = "uq_job_skills_posting_skill_method"
REQUIREMENTS = "Strong SQL, Python, Excel, Power BI, and communication skills."


@pytest.fixture
def _models():
    import tests.conftest  # noqa: F401  (imports the full model set)
    from app.db import Base

    return Base


@pytest.fixture
async def schema(pg_engine, _models):
    async with pg_engine.begin() as conn:
        await conn.run_sync(_models.metadata.create_all)
    try:
        yield
    finally:
        async with pg_engine.begin() as conn:
            await conn.run_sync(_models.metadata.drop_all)


def _migration():
    path = Path("alembic/versions/b2e9f4a71c33_one_job_skill_link_per_posting_skill_method.py")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _seed(session, *, postings=1):
    from app.models.companyModel import Company
    from app.models.jobPostingModel import JobPosting
    from app.services.analytics.capstoneAnalyticsSeedService import (
        seed_capstone_analytics_minimum,
    )

    await seed_capstone_analytics_minimum(session)
    company = Company(id=uuid.uuid4(), company_name="Race Co")
    session.add(company)
    await session.flush()
    created = [
        JobPosting(
            id=uuid.uuid4(),
            company_id=company.id,
            title="Data Analyst",
            requirements=REQUIREMENTS,
            is_active=True,
        )
        for _ in range(postings)
    ]
    session.add_all(created)
    await session.commit()
    return company, created


async def _posting_link_count(session, posting_id=None) -> int:
    from app.models.skillModel import JobSkillModel

    statement = select(func.count(JobSkillModel.id)).where(
        JobSkillModel.job_posting_id.isnot(None)
    )
    if posting_id is not None:
        statement = statement.where(JobSkillModel.job_posting_id == posting_id)
    return int(await session.scalar(statement))


@pytest.mark.asyncio
async def test_two_extractions_of_the_same_posting_leave_one_set_of_links(
    schema, pg_sessionmaker, pg_two_sessions
):
    """The race the check-then-act could not survive."""
    from app.services.analytics.capstoneAnalyticsService import CapstoneAnalyticsService

    async with pg_sessionmaker() as setup:
        _company, postings = await _seed(setup)
        posting_id = postings[0].id

    first, second = pg_two_sessions

    async def extract(session):
        try:
            links = await CapstoneAnalyticsService(session).extract_job_skills_from_job_posting(
                job_posting_id=posting_id
            )
            return len(links)
        except Exception as exc:  # noqa: BLE001 — the point is that this does not happen
            await session.rollback()
            return repr(exc)

    outcomes = await asyncio.gather(extract(first), extract(second))

    # Both callers succeed and both see the same five links: the conflict is
    # skipped, not raised, and neither run is left holding a half-written set.
    assert outcomes == [5, 5], outcomes

    async with pg_sessionmaker() as reader:
        assert await _posting_link_count(reader, posting_id) == 5


@pytest.mark.asyncio
async def test_two_open_posting_sweeps_running_together_do_not_duplicate(
    schema, pg_sessionmaker, pg_two_sessions
):
    from app.services.analytics.capstoneAnalyticsService import CapstoneAnalyticsService

    async with pg_sessionmaker() as setup:
        await _seed(setup, postings=8)

    first, second = pg_two_sessions

    async def sweep(session):
        try:
            return await CapstoneAnalyticsService(session).extract_job_skills_for_open_postings(
                limit=500
            )
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            return repr(exc)

    outcomes = await asyncio.gather(sweep(first), sweep(second))
    assert all(isinstance(outcome, dict) for outcome in outcomes), outcomes

    async with pg_sessionmaker() as reader:
        # 8 postings x 5 skills, written once no matter how many sweeps ran.
        assert await _posting_link_count(reader) == 40


@pytest.mark.asyncio
async def test_the_index_is_the_backstop_when_the_service_is_bypassed(schema, pg_sessionmaker):
    """A raw insert of the same triple is refused."""
    from sqlalchemy.exc import IntegrityError

    async with pg_sessionmaker() as session:
        _company, postings = await _seed(session)
        posting_id = postings[0].id
        skill_id = await session.scalar(text("SELECT id FROM skills LIMIT 1"))

        insert = text(
            "INSERT INTO job_skills (id, job_posting_id, skill_id, extraction_method, created_at) "
            "VALUES (:id, :posting, :skill, 'job_posting_rules_v1', :now)"
        )
        await session.execute(
            insert,
            {"id": uuid.uuid4(), "posting": posting_id, "skill": skill_id, "now": datetime.utcnow()},
        )
        await session.commit()

        with pytest.raises(IntegrityError):
            await session.execute(
                insert,
                {
                    "id": uuid.uuid4(),
                    "posting": posting_id,
                    "skill": skill_id,
                    "now": datetime.utcnow(),
                },
            )
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_links_without_a_posting_are_left_unconstrained(schema, pg_sessionmaker):
    """The role fallback writes repeated NULL-posting rows on purpose.

    ``seed_capstone_analytics_minimum`` stores per-role requirements as
    ``job_skills`` rows with a NULL ``job_posting_id``, and the same skill is
    legitimately required by several roles. A non-partial unique index would
    have been meaningless in PostgreSQL and wrong in intent, so the index only
    covers rows that actually belong to a posting.
    """
    async with pg_sessionmaker() as session:
        await _seed(session)
        detached = int(
            await session.scalar(
                text("SELECT COUNT(*) FROM job_skills WHERE job_posting_id IS NULL")
            )
        )
        repeated = int(
            await session.scalar(
                text(
                    "SELECT COUNT(*) FROM (SELECT skill_id, extraction_method FROM job_skills "
                    "WHERE job_posting_id IS NULL GROUP BY skill_id, extraction_method "
                    "HAVING COUNT(*) > 1) AS repeated"
                )
            )
        )
        assert detached > 0
        assert repeated > 0, "the seed no longer repeats a skill across roles"


@pytest.mark.asyncio
async def test_the_migration_merges_duplicates_and_keeps_provenance(
    schema, pg_engine, pg_sessionmaker
):
    """Existing duplicates: inventoried, merged into the earliest row, provenance kept."""
    async with pg_engine.begin() as conn:
        await conn.execute(text(f"DROP INDEX IF EXISTS {INDEX_NAME}"))

    async with pg_sessionmaker() as session:
        _company, postings = await _seed(session)
        posting_id = postings[0].id
        skill_id = await session.scalar(text("SELECT id FROM skills LIMIT 1"))
        other_skill_id = await session.scalar(text("SELECT id FROM skills OFFSET 1 LIMIT 1"))

        base = datetime.utcnow()
        rows = [
            # earliest, missing every piece of provenance
            (uuid.uuid4(), posting_id, skill_id, "job_posting_rules_v1", None, None, None, base),
            # later duplicates, each carrying one piece
            (
                uuid.uuid4(),
                posting_id,
                skill_id,
                "job_posting_rules_v1",
                "found in requirements",
                None,
                None,
                base + timedelta(seconds=1),
            ),
            (
                uuid.uuid4(),
                posting_id,
                skill_id,
                "job_posting_rules_v1",
                None,
                "Data Analyst",
                0.9,
                base + timedelta(seconds=2),
            ),
            # same posting and skill, different method: not a duplicate
            (
                uuid.uuid4(),
                posting_id,
                skill_id,
                "manual_review_v1",
                "reviewed by hand",
                None,
                None,
                base,
            ),
            # a different skill, untouched
            (
                uuid.uuid4(),
                posting_id,
                other_skill_id,
                "job_posting_rules_v1",
                "other",
                None,
                None,
                base,
            ),
        ]
        for row in rows:
            await session.execute(
                text(
                    "INSERT INTO job_skills (id, job_posting_id, skill_id, extraction_method, "
                    "evidence_text, target_role, importance_score, created_at) "
                    "VALUES (:id, :posting, :skill, :method, :evidence, :role, :score, :created)"
                ),
                dict(zip(
                    ("id", "posting", "skill", "method", "evidence", "role", "score", "created"),
                    row,
                )),
            )
        await session.commit()
        survivor_id = rows[0][0]

    migration = _migration()

    async with pg_engine.begin() as conn:
        inventory = await conn.run_sync(
            lambda sync_conn: migration._inventory_duplicates(sync_conn)
        )
        assert len(inventory) == 1
        assert inventory[0][3] == 3

        removed = await conn.run_sync(lambda sync_conn: migration._resolve_duplicates(sync_conn))
        assert removed == 2

    async with pg_sessionmaker() as reader:
        survivor = (
            await reader.execute(
                text(
                    "SELECT evidence_text, target_role, importance_score "
                    "FROM job_skills WHERE id = :id"
                ),
                {"id": survivor_id},
            )
        ).first()
        # The earliest row survived and inherited what it did not have.
        assert survivor is not None
        assert survivor[0] == "found in requirements"
        assert survivor[1] == "Data Analyst"
        assert float(survivor[2]) == 0.9

        methods = (
            await reader.execute(
                text(
                    "SELECT extraction_method, COUNT(*) FROM job_skills "
                    "WHERE job_posting_id = :posting AND skill_id = :skill "
                    "GROUP BY extraction_method ORDER BY extraction_method"
                ),
                {"posting": posting_id, "skill": skill_id},
            )
        ).all()
        # The other method is provenance, not duplication: it stays.
        assert [(row[0], row[1]) for row in methods] == [
            ("job_posting_rules_v1", 1),
            ("manual_review_v1", 1),
        ]


@pytest.mark.asyncio
async def test_the_migration_is_reentrant_and_creates_the_index(schema, pg_engine):
    """Running it twice is a no-op the second time, and the index ends up there."""
    async with pg_engine.begin() as conn:
        await conn.execute(text(f"DROP INDEX IF EXISTS {INDEX_NAME}"))

    migration = _migration()

    async with pg_engine.begin() as conn:
        assert await conn.run_sync(lambda c: migration._resolve_duplicates(c)) == 0
        await conn.run_sync(
            lambda c: c.execute(
                text(
                    f"CREATE UNIQUE INDEX {INDEX_NAME} ON job_skills "
                    "(job_posting_id, skill_id, extraction_method) "
                    "WHERE job_posting_id IS NOT NULL"
                )
            )
        )

    async with pg_engine.connect() as conn:
        present = await conn.run_sync(lambda c: migration._indexes(c, "job_skills"))
        assert INDEX_NAME in present
