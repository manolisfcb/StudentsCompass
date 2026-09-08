import pytest
from httpx import AsyncClient

import app.core.resume_analyzer.resume_text_extractor as text_extractor
import app.services.resumes.resumeService as resume_service_module
from app.models.resumeModel import ResumeModel
from app.services.analytics.capstoneAnalyticsSeedService import seed_capstone_analytics_minimum


@pytest.mark.asyncio
async def test_skill_sync_falls_back_to_cv_text_without_ai_summary(
    client: AsyncClient, db_session, test_user, auth_headers, monkeypatch
):
    """A CV uploaded without running the quota-limited Jobs analysis has no
    ai_summary. The Career Lab must still read real skills from the CV text."""
    await seed_capstone_analytics_minimum(db_session)
    resume = ResumeModel(
        view_url="https://storage.example/resume.pdf",
        user_id=test_user.id,
        storage_file_id="resumes/test.pdf",
        original_filename="resume.pdf",
        folder_id="resumes",
        ai_summary=None,  # never analyzed by the Jobs flow
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    async def fake_download(self, file_key):
        return b"%PDF-fake-bytes"

    async def fake_extract(file_bytes, filename=None, content_type=None):
        return "Experienced with SQL, Tableau and statistics for analytics dashboards."

    monkeypatch.setattr(resume_service_module.ResumeService, "download_resume_file", fake_download)
    monkeypatch.setattr(text_extractor, "extract_resume_text_from_bytes", fake_extract)

    response = await client.post(
        f"/api/v1/capstone/resumes/{resume.id}/skills/sync",
        headers=auth_headers,
    )

    assert response.status_code == 200
    names = {skill["normalized_name"] for skill in response.json()["extracted_skills"]}
    assert {"sql", "tableau", "statistics"}.issubset(names)
