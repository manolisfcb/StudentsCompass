"""Extracting job skills costs a fixed number of round trips per batch, and repeats are free.

The sweep already shared one skill lookup across the whole run, but everything
else was per posting: it re-read the posting by id, selected the links that
posting already had, and committed. So a 500-posting sweep was 500 SELECTs and
500 commits, and any failure halfway left a partially written run behind.

Idempotency was a check-then-act — read the existing links, insert the missing
ones — with nothing serialising the two halves. The uniqueness index added by
``b2e9f4a71c33`` is what actually makes it safe; here we pin the single-process
half of that (a second run inserts nothing) and the query shape. The concurrent
half needs real connections and lives in
``tests/integration/test_job_skill_uniqueness_pg.py``.
"""
from __future__ import annotations

import contextlib
import uuid

import pytest
from sqlalchemy import event, func, select

from app.models.companyModel import Company
from app.models.jobPostingModel import JobPosting
from app.models.skillModel import JobSkillModel
from app.services.analytics.capstoneAnalyticsSeedService import (
    seed_capstone_analytics_minimum,
)
from app.services.analytics.capstoneAnalyticsService import CapstoneAnalyticsService
from tests.harness import count_queries

REQUIREMENTS = "Strong SQL, Python, Excel, Power BI, and communication skills."


async def _seed_postings(session, count, *, company=None, requirements=REQUIREMENTS):
    if company is None:
        company = Company(id=uuid.uuid4(), company_name="Batch Co")
        session.add(company)
        await session.flush()
    postings = [
        JobPosting(
            id=uuid.uuid4(),
            company_id=company.id,
            title="Data Analyst",
            requirements=requirements,
            is_active=True,
        )
        for _ in range(count)
    ]
    session.add_all(postings)
    await session.commit()
    return company, postings


async def _link_count(session, posting_id=None) -> int:
    """Links attached to a posting.

    ``seed_capstone_analytics_minimum`` also writes ``job_skills`` rows with a
    NULL ``job_posting_id`` — the per-role fallback requirements — and those
    are legitimately repeated per role. They are exactly why the uniqueness
    index is partial, and they are not what this module counts.
    """
    statement = select(func.count(JobSkillModel.id)).where(
        JobSkillModel.job_posting_id.isnot(None)
    )
    if posting_id is not None:
        statement = statement.where(JobSkillModel.job_posting_id == posting_id)
    return int(await session.scalar(statement))


@contextlib.contextmanager
def _count_commits(engine):
    """Count real transaction commits.

    ``count_queries`` listens on cursor execution, and a COMMIT never reaches a
    cursor, so commits need the connection-level event.
    """
    counted = {"commits": 0}
    sync_engine = engine.sync_engine

    def on_commit(_conn):
        counted["commits"] += 1

    event.listen(sync_engine, "commit", on_commit)
    try:
        yield counted
    finally:
        event.remove(sync_engine, "commit", on_commit)


@pytest.mark.asyncio
@pytest.mark.parametrize("posting_count", [10, 100, 500])
async def test_the_sweep_commits_per_batch_not_per_posting(
    db_session, posting_count
):
    """Commits and selects follow the batch size, not the number of postings."""
    from tests.conftest import test_engine

    await seed_capstone_analytics_minimum(db_session)
    await _seed_postings(db_session, posting_count)

    service = CapstoneAnalyticsService(db_session)
    with count_queries(test_engine) as counter, _count_commits(test_engine) as commits:
        summary = await service.extract_job_skills_for_open_postings(limit=posting_count)

    expected_batches = -(-posting_count // service.JOB_SKILL_EXTRACTION_BATCH_SIZE)
    assert summary["jobs_scanned"] == posting_count
    assert summary["jobs_with_matches"] == posting_count

    assert commits["commits"] == expected_batches, (
        f"{commits['commits']} commits for {expected_batches} batches "
        f"over {posting_count} postings"
    )
    # Postings + lookup + one existing-links read and one insert per batch.
    assert counter.selects <= 4 + expected_batches, (
        f"{counter.selects} selects for {posting_count} postings"
    )
    assert counter.count("INSERT") == expected_batches


@pytest.mark.asyncio
async def test_the_query_cost_does_not_grow_with_the_number_of_postings(db_session):
    """Per-posting cost is flat: 10x the postings must not be 10x the selects."""
    from tests.conftest import test_engine

    await seed_capstone_analytics_minimum(db_session)
    company, _ = await _seed_postings(db_session, 50)
    service = CapstoneAnalyticsService(db_session)

    with count_queries(test_engine) as fifty:
        await service.extract_job_skills_for_open_postings(limit=500)

    await _seed_postings(db_session, 450, company=company)
    with count_queries(test_engine) as five_hundred:
        await service.extract_job_skills_for_open_postings(limit=500)

    per_posting_before = fifty.selects / 50
    per_posting_after = five_hundred.selects / 500
    assert per_posting_after < per_posting_before
    assert five_hundred.selects < 50, f"{five_hundred.selects} selects for 500 postings"


@pytest.mark.asyncio
async def test_a_second_sweep_inserts_nothing_and_reports_the_same_links(db_session):
    """Re-running the extraction is a no-op, not a duplicate."""
    await seed_capstone_analytics_minimum(db_session)
    await _seed_postings(db_session, 20)
    service = CapstoneAnalyticsService(db_session)

    first = await service.extract_job_skills_for_open_postings(limit=500)
    after_first = await _link_count(db_session)

    second = await service.extract_job_skills_for_open_postings(limit=500)
    after_second = await _link_count(db_session)

    assert first == second
    assert after_first == after_second == first["job_skill_links"]


@pytest.mark.asyncio
async def test_a_second_single_posting_extraction_returns_the_same_links(db_session):
    await seed_capstone_analytics_minimum(db_session)
    _company, postings = await _seed_postings(db_session, 1)
    posting = postings[0]
    service = CapstoneAnalyticsService(db_session)

    first = await service.extract_job_skills_from_job_posting(job_posting_id=posting.id)
    second = await service.extract_job_skills_from_job_posting(job_posting_id=posting.id)

    assert first
    assert [link.id for link in first] == [link.id for link in second]
    assert await _link_count(db_session, posting.id) == len(first)


@pytest.mark.asyncio
async def test_a_posting_with_no_text_is_skipped_even_when_it_already_has_links(db_session):
    """Blank postings were never counted, links or no links. That does not change."""
    await seed_capstone_analytics_minimum(db_session)
    _company, postings = await _seed_postings(db_session, 1)
    posting = postings[0]
    service = CapstoneAnalyticsService(db_session)
    await service.extract_job_skills_from_job_posting(job_posting_id=posting.id)
    assert await _link_count(db_session, posting.id) > 0

    posting.title = ""
    posting.requirements = ""
    posting.description = None
    posting.responsibilities = None
    await db_session.commit()

    assert await service.extract_job_skills_from_job_posting(job_posting_id=posting.id) == []
    summary = await service.extract_job_skills_for_open_postings(limit=500)
    assert summary["jobs_scanned"] == 1
    assert summary["jobs_with_matches"] == 0
    assert summary["job_skill_links"] == 0


@pytest.mark.asyncio
async def test_links_found_by_a_different_method_are_not_touched(db_session):
    """The method is part of the key: another extraction's rows survive."""
    await seed_capstone_analytics_minimum(db_session)
    _company, postings = await _seed_postings(db_session, 1)
    posting = postings[0]
    service = CapstoneAnalyticsService(db_session)

    rules = await service.extract_job_skills_from_job_posting(job_posting_id=posting.id)
    manual = await service.extract_job_skills_from_job_posting(
        job_posting_id=posting.id, extraction_method="manual_review_v1"
    )

    assert rules and manual
    assert {link.extraction_method for link in rules} == {"job_posting_rules_v1"}
    assert {link.extraction_method for link in manual} == {"manual_review_v1"}
    assert await _link_count(db_session, posting.id) == len(rules) + len(manual)


@pytest.mark.asyncio
async def test_the_sweep_reports_the_same_totals_as_the_per_posting_path(db_session):
    """Batched and one-at-a-time extraction agree on what exists."""
    await seed_capstone_analytics_minimum(db_session)
    _company, postings = await _seed_postings(db_session, 12)
    service = CapstoneAnalyticsService(db_session)

    per_posting_total = 0
    for posting in postings:
        per_posting_total += len(
            await service.extract_job_skills_from_job_posting(job_posting_id=posting.id)
        )

    summary = await service.extract_job_skills_for_open_postings(limit=500)
    assert summary["job_skill_links"] == per_posting_total
    assert summary["jobs_with_matches"] == 12
    assert await _link_count(db_session) == per_posting_total
