import pytest
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.resume_analyzer.resume_feature import ResumeFeatureRequest
from app.models.jobAnalysisModel import JobAnalysisModel, JobStatus
from app.models.resumeModel import ResumeModel
from app.models.userModel import User
from app.routes.jobRoute import process_cv_analysis


@pytest.mark.asyncio
async def test_process_cv_analysis_persists_summary_and_resume_phone(
    db_session: AsyncSession,
    test_user: User,
    monkeypatch,
):
    async def fake_download(self, file_key: str):
        assert file_key == "resumes/user.pdf"
        return b"resume file bytes"

    async def fake_extract_resume_text_from_bytes(file_bytes: bytes, *, filename: str, content_type: str):
        assert file_bytes == b"resume file bytes"
        assert filename == "candidate_resume.pdf"
        return "Manuel Rivera\nPhone: +1 416 555 0101\nPython FastAPI PostgreSQL engineer"

    async def fake_ask_llm_model(resume_text: str):
        assert "Python FastAPI PostgreSQL engineer" in resume_text
        return ResumeFeatureRequest(
            resume_text=resume_text,
            resume_summary="Backend-focused student with hands-on Python API experience.",
            resume_keywords=["Python", "FastAPI", "PostgreSQL"],
            resume_key_skills=["Python", "FastAPI"],
        )

    monkeypatch.setattr("app.services.resumes.resumeService.ResumeService.download_resume_file", fake_download)
    monkeypatch.setattr(
        "app.services.ai.cvAnalysisService.extract_resume_text_from_bytes",
        fake_extract_resume_text_from_bytes,
    )
    monkeypatch.setattr("app.services.ai.cvAnalysisService.ask_llm_model", fake_ask_llm_model)

    resume = ResumeModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        view_url="https://example.com/resume.pdf",
        storage_file_id="resumes/user.pdf",
        original_filename="candidate_resume.pdf",
        folder_id="test-bucket",
    )
    job = JobAnalysisModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        resume_id=resume.id,
        status=JobStatus.PENDING,
    )
    db_session.add_all([resume, job])
    await db_session.commit()

    async def session_factory():
        yield db_session

    await process_cv_analysis(job.id, test_user.id, resume.id, session_factory)

    refreshed_job = await db_session.scalar(select(JobAnalysisModel).where(JobAnalysisModel.id == job.id))
    refreshed_resume = await db_session.scalar(select(ResumeModel).where(ResumeModel.id == resume.id))

    assert refreshed_job.status == JobStatus.COMPLETED
    assert refreshed_job.keywords == "Python, FastAPI, PostgreSQL"
    assert refreshed_job.summary == "Backend-focused student with hands-on Python API experience."
    assert refreshed_resume.ai_summary == "Backend-focused student with hands-on Python API experience."
    assert refreshed_resume.contact_phone == "+1 416 555 0101"


@pytest.mark.asyncio
async def test_process_cv_analysis_reuses_cached_resume_analysis(
    db_session: AsyncSession,
    test_user: User,
):
    resume = ResumeModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        view_url="https://example.com/resume.pdf",
        storage_file_id="resumes/user.pdf",
        original_filename="candidate_resume.pdf",
        folder_id="test-bucket",
        ai_summary=None,
    )
    cached_job = JobAnalysisModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        resume_id=resume.id,
        status=JobStatus.COMPLETED,
        keywords="Python, FastAPI",
        summary="Cached backend resume summary.",
    )
    pending_job = JobAnalysisModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        resume_id=resume.id,
        status=JobStatus.PENDING,
    )
    db_session.add_all([resume, cached_job, pending_job])
    await db_session.commit()

    async def session_factory():
        yield db_session

    await process_cv_analysis(pending_job.id, test_user.id, resume.id, session_factory)

    refreshed_job = await db_session.scalar(select(JobAnalysisModel).where(JobAnalysisModel.id == pending_job.id))
    refreshed_resume = await db_session.scalar(select(ResumeModel).where(ResumeModel.id == resume.id))

    assert refreshed_job.status == JobStatus.COMPLETED
    assert refreshed_job.keywords == "Python, FastAPI"
    assert refreshed_job.summary == "Cached backend resume summary."
    assert refreshed_resume.ai_summary == "Cached backend resume summary."
