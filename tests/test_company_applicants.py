import pytest
import uuid
import io
import zipfile

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.applicationModel import ApplicationModel, ApplicationStatus
from app.models.jobPostingModel import JobPosting
from app.models.resumeModel import ResumeModel
from app.models.userModel import User
from app.services.resumeService import ResumeService


@pytest.mark.asyncio
async def test_company_can_list_applicants_with_resume_details(
    client: AsyncClient,
    company_auth_headers: dict,
    test_user: User,
    test_company,
    db_session: AsyncSession,
):
    resume = ResumeModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        view_url="https://example.com/resume.pdf",
        storage_file_id="resumes/candidate.pdf",
        original_filename="candidate_resume.pdf",
        folder_id="test-bucket",
        ai_summary="Junior backend candidate with Python and FastAPI experience.",
        contact_phone="+1 647 555 0100",
    )
    job_posting = JobPosting(
        id=uuid.uuid4(),
        company_id=test_company.id,
        title="Backend Developer",
        description="Role",
    )
    application = ApplicationModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        company_id=test_company.id,
        job_posting_id=job_posting.id,
        resume_id=resume.id,
        job_title="Backend Developer",
        status=ApplicationStatus.APPLIED,
    )
    db_session.add_all([resume, job_posting, application])
    await db_session.commit()

    response = await client.get("/api/v1/companies/me/applicants", headers=company_auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["candidate"]["email"] == test_user.email
    assert data[0]["candidate"]["phone"] == "+1 647 555 0100"
    assert data[0]["application"]["job_title"] == "Backend Developer"
    assert data[0]["resume"]["summary"] == "Junior backend candidate with Python and FastAPI experience."
    assert data[0]["resume"]["preview_url"].endswith(f"/api/v1/companies/me/applications/{application.id}/resume/preview")
    assert data[0]["resume"]["download_url"].endswith(f"/api/v1/companies/me/applications/{application.id}/resume/download")


@pytest.mark.asyncio
async def test_company_resume_download_requires_company_access_and_streams_file(
    client: AsyncClient,
    company_auth_headers: dict,
    test_user: User,
    test_company,
    db_session: AsyncSession,
    monkeypatch,
):
    async def fake_download(self, file_key: str):
        assert file_key == "resumes/candidate.pdf"
        return b"%PDF-1.4 candidate resume"

    monkeypatch.setattr(ResumeService, "download_file_from_s3", fake_download)

    resume = ResumeModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        view_url="https://example.com/resume.pdf",
        storage_file_id="resumes/candidate.pdf",
        original_filename="candidate_resume.pdf",
        folder_id="test-bucket",
    )
    job_posting = JobPosting(
        id=uuid.uuid4(),
        company_id=test_company.id,
        title="Backend Developer",
        description="Role",
    )
    application = ApplicationModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        company_id=test_company.id,
        job_posting_id=job_posting.id,
        resume_id=resume.id,
        job_title="Backend Developer",
        status=ApplicationStatus.APPLIED,
    )
    db_session.add_all([resume, job_posting, application])
    await db_session.commit()

    response = await client.get(
        f"/api/v1/companies/me/applications/{application.id}/resume/download",
        headers=company_auth_headers,
    )

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 candidate resume"
    assert "attachment; filename=\"candidate_resume.pdf\"" == response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_company_resume_preview_streams_pdf_inline(
    client: AsyncClient,
    company_auth_headers: dict,
    test_user: User,
    test_company,
    db_session: AsyncSession,
    monkeypatch,
):
    async def fake_download(self, file_key: str):
        assert file_key == "resumes/candidate.pdf"
        return b"%PDF-1.4 candidate resume"

    monkeypatch.setattr(ResumeService, "download_file_from_s3", fake_download)

    resume = ResumeModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        view_url="https://example.com/resume.pdf",
        storage_file_id="resumes/candidate.pdf",
        original_filename="candidate_resume.pdf",
        folder_id="test-bucket",
    )
    job_posting = JobPosting(
        id=uuid.uuid4(),
        company_id=test_company.id,
        title="Backend Developer",
        description="Role",
    )
    application = ApplicationModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        company_id=test_company.id,
        job_posting_id=job_posting.id,
        resume_id=resume.id,
        job_title="Backend Developer",
        status=ApplicationStatus.APPLIED,
    )
    db_session.add_all([resume, job_posting, application])
    await db_session.commit()

    response = await client.get(
        f"/api/v1/companies/me/applications/{application.id}/resume/preview",
        headers=company_auth_headers,
    )

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 candidate resume"
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["content-disposition"] == 'inline; filename="candidate_resume.pdf"'


@pytest.mark.asyncio
async def test_company_resume_preview_renders_docx_as_html(
    client: AsyncClient,
    company_auth_headers: dict,
    test_user: User,
    test_company,
    db_session: AsyncSession,
    monkeypatch,
):
    docx_buffer = io.BytesIO()
    with zipfile.ZipFile(docx_buffer, "w") as archive:
        archive.writestr(
            "word/document.xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body>"
                "<w:p><w:r><w:t>Jane Candidate</w:t></w:r></w:p>"
                "<w:p><w:r><w:t>Python developer with FastAPI experience.</w:t></w:r></w:p>"
                "</w:body>"
                "</w:document>"
            ),
        )

    async def fake_download(self, file_key: str):
        assert file_key == "resumes/candidate.docx"
        return docx_buffer.getvalue()

    monkeypatch.setattr(ResumeService, "download_file_from_s3", fake_download)

    resume = ResumeModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        view_url="https://example.com/resume.docx",
        storage_file_id="resumes/candidate.docx",
        original_filename="candidate_resume.docx",
        folder_id="test-bucket",
    )
    job_posting = JobPosting(
        id=uuid.uuid4(),
        company_id=test_company.id,
        title="Backend Developer",
        description="Role",
    )
    application = ApplicationModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        company_id=test_company.id,
        job_posting_id=job_posting.id,
        resume_id=resume.id,
        job_title="Backend Developer",
        status=ApplicationStatus.APPLIED,
    )
    db_session.add_all([resume, job_posting, application])
    await db_session.commit()

    response = await client.get(
        f"/api/v1/companies/me/applications/{application.id}/resume/preview",
        headers=company_auth_headers,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Generated preview" in response.text
    assert "Jane Candidate" in response.text
    assert "Python developer with FastAPI experience." in response.text
