"""``job_analysis`` as a durable queue: claim, lease, recovery, bounded retries.

The failures these pin are the ones a restart used to cause. A job left on
PROCESSING blocked every later analysis of the same CV, because "is one already
running?" is also how the API decides to refuse a new one — so the bug was
self-perpetuating until someone edited the row by hand.

The one rule that outranks "make it recover": a job interrupted *after* the
provider was called is never re-run on a guess. Money may already have been
spent, and the app cannot know.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.resume_analyzer.resume_feature import ResumeFeatureRequest
from app.models.jobAnalysisModel import JobAnalysisModel, JobStatus
from app.models.resumeModel import ResumeModel
from app.services.ai.cvAnalysisRunner import CVAnalysisRunner
from app.services.ai.cvAnalysisService import (
    EXHAUSTED_ATTEMPTS_MESSAGE,
    INTERRUPTED_AFTER_SPEND_MESSAGE,
    MAX_JOB_ATTEMPTS,
    CVAnalysisService,
)
from app.services.ratelimit.counterStore import reset_counter_store


@pytest.fixture
async def resume(db_session, test_user):
    model = ResumeModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        view_url="https://example.invalid/resume.pdf",
        storage_file_id="resumes/user.pdf",
        original_filename="candidate_resume.pdf",
        folder_id="test-bucket",
    )
    db_session.add(model)
    await db_session.commit()
    return model


async def _job(session, job_id) -> JobAnalysisModel:
    return await session.scalar(
        select(JobAnalysisModel)
        .where(JobAnalysisModel.id == job_id)
        .execution_options(populate_existing=True)
    )


async def _active_jobs(session, user_id) -> list[JobAnalysisModel]:
    result = await session.execute(
        select(JobAnalysisModel)
        .where(
            JobAnalysisModel.user_id == user_id,
            JobAnalysisModel.status.in_([JobStatus.PENDING, JobStatus.PROCESSING]),
        )
        .execution_options(populate_existing=True)
    )
    return list(result.scalars())


@pytest.mark.asyncio
async def test_two_enqueues_return_the_same_job(db_session, test_user, resume):
    """Two POSTs for one CV must converge on one analysis, not two."""
    service = CVAnalysisService(db_session)

    first = await service.create_pending_analysis(user_id=test_user.id, resume_id=resume.id)
    second = await service.create_pending_analysis(user_id=test_user.id, resume_id=resume.id)

    assert first.id == second.id
    assert len(await _active_jobs(db_session, test_user.id)) == 1


@pytest.mark.asyncio
async def test_only_one_worker_can_claim_a_job(db_session, test_user, resume):
    service = CVAnalysisService(db_session)
    job = await service.create_pending_analysis(user_id=test_user.id, resume_id=resume.id)

    assert await service.claim_job(job.id) is True
    assert await service.claim_job(job.id) is False, "a live lease is not up for grabs"

    claimed = await _job(db_session, job.id)
    assert claimed.status == JobStatus.PROCESSING
    assert claimed.attempts == 1
    assert claimed.lease_expires_at is not None


@pytest.mark.asyncio
async def test_an_expired_lease_can_be_claimed_again(db_session, test_user, resume):
    service = CVAnalysisService(db_session)
    job = await service.create_pending_analysis(user_id=test_user.id, resume_id=resume.id)
    await service.claim_job(job.id)

    stale = await _job(db_session, job.id)
    stale.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)
    await db_session.commit()

    assert await service.claim_job(job.id) is True
    reclaimed = await _job(db_session, job.id)
    assert reclaimed.attempts == 2


@pytest.mark.asyncio
async def test_recovery_requeues_a_job_that_never_reached_the_provider(
    db_session, test_user, resume
):
    service = CVAnalysisService(db_session)
    job = await service.create_pending_analysis(user_id=test_user.id, resume_id=resume.id)
    await service.claim_job(job.id)

    abandoned = await _job(db_session, job.id)
    abandoned.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)
    await db_session.commit()

    outcome = await service.recover_stale_jobs()

    assert outcome == {"failed_after_spend": 0, "failed_attempts_exhausted": 0, "requeued": 1}
    recovered = await _job(db_session, job.id)
    assert recovered.status == JobStatus.PENDING
    assert recovered.lease_expires_at is None


@pytest.mark.asyncio
async def test_recovery_never_reruns_a_job_that_had_already_called_the_provider(
    db_session, test_user, resume
):
    """Uncertain spend is stated, not retried."""
    service = CVAnalysisService(db_session)
    job = await service.create_pending_analysis(user_id=test_user.id, resume_id=resume.id)
    await service.claim_job(job.id)

    interrupted = await _job(db_session, job.id)
    interrupted.provider_attempted_at = datetime.utcnow()
    interrupted.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)
    await db_session.commit()

    outcome = await service.recover_stale_jobs()

    assert outcome["failed_after_spend"] == 1
    assert outcome["requeued"] == 0
    failed = await _job(db_session, job.id)
    assert failed.status == JobStatus.FAILED
    assert failed.error_message == INTERRUPTED_AFTER_SPEND_MESSAGE
    # And the CV is free again: a terminal job blocks nothing.
    assert await _active_jobs(db_session, test_user.id) == []


@pytest.mark.asyncio
async def test_retries_are_bounded(db_session, test_user, resume):
    service = CVAnalysisService(db_session)
    job = await service.create_pending_analysis(user_id=test_user.id, resume_id=resume.id)

    for _ in range(MAX_JOB_ATTEMPTS):
        assert await service.claim_job(job.id) is True
        stale = await _job(db_session, job.id)
        stale.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)
        await db_session.commit()
        outcome = await service.recover_stale_jobs()

    assert outcome["failed_attempts_exhausted"] == 1
    exhausted = await _job(db_session, job.id)
    assert exhausted.status == JobStatus.FAILED
    assert exhausted.error_message == EXHAUSTED_ATTEMPTS_MESSAGE


@pytest.mark.asyncio
async def test_a_stale_job_no_longer_blocks_the_next_analysis(db_session, test_user, resume):
    """The symptom users actually hit: one dead job, no more AI analyses."""
    service = CVAnalysisService(db_session)
    blocked = await service.create_pending_analysis(user_id=test_user.id, resume_id=resume.id)
    await service.claim_job(blocked.id)
    stuck = await _job(db_session, blocked.id)
    stuck.provider_attempted_at = datetime.utcnow()
    stuck.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)
    await db_session.commit()

    await service.recover_stale_jobs()

    fresh = await service.create_pending_analysis(user_id=test_user.id, resume_id=resume.id)
    assert fresh.id != blocked.id
    assert fresh.status == JobStatus.PENDING


@pytest.mark.asyncio
async def test_processing_an_already_claimed_job_does_nothing(db_session, test_user, resume):
    """The two dispatchers overlap by design; only one may do the work."""
    service = CVAnalysisService(db_session)
    job = await service.create_pending_analysis(user_id=test_user.id, resume_id=resume.id)
    await service.claim_job(job.id)

    async def explode(*args, **kwargs):
        raise AssertionError("a claimed job must not be processed twice")

    service.resume_service.download_resume_file = explode

    await service.process_job(job_id=job.id, user_id=test_user.id, resume_id=resume.id)

    untouched = await _job(db_session, job.id)
    assert untouched.status == JobStatus.PROCESSING
    assert untouched.attempts == 1


@pytest.mark.asyncio
async def test_the_runner_finishes_a_job_left_behind_by_a_dead_process(
    db_session, test_user, resume, monkeypatch
):
    """The whole point of the runner: nobody has to re-POST for work to finish."""
    await reset_counter_store()

    async def fake_download(self, file_key: str):
        return b"resume file bytes"

    async def fake_extract(file_bytes, *, filename, content_type):
        return "Manuel Rivera\nPython FastAPI PostgreSQL engineer with API experience"

    async def fake_ask_llm_model(resume_text: str):
        return ResumeFeatureRequest(
            resume_text=resume_text,
            resume_summary="Backend-focused student.",
            resume_keywords=["Python", "FastAPI"],
            resume_key_skills=["Python"],
        )

    monkeypatch.setattr(
        "app.services.resumes.resumeService.ResumeService.download_resume_file", fake_download
    )
    monkeypatch.setattr(
        "app.services.ai.cvAnalysisService.extract_resume_text_from_bytes", fake_extract
    )
    monkeypatch.setattr("app.services.ai.cvAnalysisService.ask_llm_model", fake_ask_llm_model)

    service = CVAnalysisService(db_session)
    job = await service.create_pending_analysis(user_id=test_user.id, resume_id=resume.id)
    # The request that created it claimed it and then the process died.
    await service.claim_job(job.id)
    abandoned = await _job(db_session, job.id)
    abandoned.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)
    await db_session.commit()

    class _Factory:
        """Hands the runner the test session without closing it."""

        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *exc_info):
            return False

    started = await CVAnalysisRunner(_Factory()).sweep_once()

    assert started == 1
    finished = await _job(db_session, job.id)
    assert finished.status == JobStatus.COMPLETED
    assert finished.keywords == "Python, FastAPI"
    assert finished.lease_expires_at is None


@pytest.mark.asyncio
async def test_a_recovered_job_charges_the_user_once(db_session, test_user, resume, monkeypatch):
    """A job the runner adopts has no reservation, so it claims one itself."""
    await reset_counter_store()

    calls: list[str] = []

    async def fake_download(self, file_key: str):
        return b"resume file bytes"

    async def fake_extract(file_bytes, *, filename, content_type):
        return "Manuel Rivera\nPython FastAPI PostgreSQL engineer with API experience"

    async def fake_ask_llm_model(resume_text: str):
        calls.append("llm")
        return ResumeFeatureRequest(
            resume_text=resume_text,
            resume_summary="Backend-focused student.",
            resume_keywords=["Python"],
            resume_key_skills=["Python"],
        )

    monkeypatch.setattr(
        "app.services.resumes.resumeService.ResumeService.download_resume_file", fake_download
    )
    monkeypatch.setattr(
        "app.services.ai.cvAnalysisService.extract_resume_text_from_bytes", fake_extract
    )
    monkeypatch.setattr("app.services.ai.cvAnalysisService.ask_llm_model", fake_ask_llm_model)

    from app.services.ai.aiUsageService import AIFeature, AIUsageService

    service = CVAnalysisService(db_session)
    job = await service.create_pending_analysis(user_id=test_user.id, resume_id=resume.id)
    await service.process_job(job_id=job.id, user_id=test_user.id, resume_id=resume.id)

    assert calls == ["llm"]
    usage = AIUsageService(db_session)
    assert await usage.get_used_today(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH) == 1

    # Replaying the same job (a re-delivered task) charges nothing more: the
    # ledger is idempotent by job id, and the job is no longer claimable.
    await service.process_job(job_id=job.id, user_id=test_user.id, resume_id=resume.id)
    assert calls == ["llm"]
    assert await usage.get_used_today(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH) == 1
