import pytest
import uuid
import io
import zipfile

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.applicationModel import ApplicationModel, ApplicationStatus
from app.models.applicationAnalyticsModel import ApplicationEventType, ApplicationStatusEventModel
from app.models.jobPostingModel import JobPosting
from app.models.emailNotificationLogModel import EmailNotificationLogModel
from app.models.interviewAvailabilityModel import InterviewAvailabilityModel, InterviewAvailabilityStatus
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
    assert data[0]["application"]["match_strength"] in {"strong_match", "match", "weak_match"}
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


@pytest.mark.asyncio
async def test_company_can_move_applicant_to_in_review_and_student_dashboard_reflects_it(
    client: AsyncClient,
    auth_headers: dict,
    company_auth_headers: dict,
    test_user: User,
    test_company,
    test_company_recruiter,
    db_session: AsyncSession,
):
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
        job_title="Backend Developer",
        status=ApplicationStatus.APPLIED,
    )
    db_session.add_all([job_posting, application])
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/companies/me/applicants/{application.id}",
        headers=company_auth_headers,
        json={
            "status": "in_review",
            "notes": "Moved to in review by recruiter.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["application"]["status"] == "in_review"
    assert payload["application"]["assigned_recruiter_id"] == str(test_company_recruiter.id)
    assert payload["application"]["notes"] == "Moved to in review by recruiter."

    dashboard_response = await client.get("/api/v1/students_dashboard", headers=auth_headers)
    assert dashboard_response.status_code == 200
    dashboard_payload = dashboard_response.json()
    assert dashboard_payload["application_breakdown"]["in_review"] == 1
    assert dashboard_payload["stats"]["interviews_scheduled"] == 0

    event_result = await db_session.execute(
        select(ApplicationStatusEventModel)
        .where(ApplicationStatusEventModel.application_id == application.id)
        .order_by(ApplicationStatusEventModel.occurred_at.desc())
    )
    event = event_result.scalar_one()
    assert event.event_type == ApplicationEventType.STATUS_CHANGED
    assert event.from_status == ApplicationStatus.APPLIED
    assert event.to_status == ApplicationStatus.IN_REVIEW
    assert event.triggered_by_company_recruiter_id == test_company_recruiter.id

    email_result = await db_session.execute(
        select(EmailNotificationLogModel).where(
            EmailNotificationLogModel.application_id == application.id,
            EmailNotificationLogModel.template_key == "candidate_selected_for_review",
        )
    )
    email_log = email_result.scalar_one()
    assert email_log.recipient_email == test_user.email


@pytest.mark.asyncio
async def test_company_can_filter_selected_candidates_from_applicants_endpoint(
    client: AsyncClient,
    company_auth_headers: dict,
    test_user: User,
    test_company,
    db_session: AsyncSession,
):
    job_postings = [
        JobPosting(
            id=uuid.uuid4(),
            company_id=test_company.id,
            title="Backend Developer",
            description="Role",
        ),
        JobPosting(
            id=uuid.uuid4(),
            company_id=test_company.id,
            title="Frontend Developer",
            description="Role",
        ),
        JobPosting(
            id=uuid.uuid4(),
            company_id=test_company.id,
            title="Operations Analyst",
            description="Role",
        ),
    ]
    applications = [
        ApplicationModel(
            id=uuid.uuid4(),
            user_id=test_user.id,
            company_id=test_company.id,
            job_posting_id=job_postings[0].id,
            job_title=job_postings[0].title,
            status=ApplicationStatus.APPLIED,
        ),
        ApplicationModel(
            id=uuid.uuid4(),
            user_id=test_user.id,
            company_id=test_company.id,
            job_posting_id=job_postings[1].id,
            job_title=job_postings[1].title,
            status=ApplicationStatus.IN_REVIEW,
        ),
        ApplicationModel(
            id=uuid.uuid4(),
            user_id=test_user.id,
            company_id=test_company.id,
            job_posting_id=job_postings[2].id,
            job_title=job_postings[2].title,
            status=ApplicationStatus.INTERVIEW,
        ),
    ]
    db_session.add_all(job_postings)
    db_session.add_all(applications)
    await db_session.commit()

    response = await client.get(
        "/api/v1/companies/me/applicants?status=in_review&status=interview",
        headers=company_auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    returned_statuses = {item["application"]["status"] for item in payload}

    assert len(payload) == 2
    assert returned_statuses == {"in_review", "interview"}


@pytest.mark.asyncio
async def test_company_can_publish_interview_availabilities_and_candidate_can_confirm_one(
    client: AsyncClient,
    auth_headers: dict,
    company_auth_headers: dict,
    test_user: User,
    test_company,
    test_company_recruiter,
    db_session: AsyncSession,
):
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
        job_title="Backend Developer",
        status=ApplicationStatus.IN_REVIEW,
        assigned_recruiter_id=test_company_recruiter.id,
    )
    db_session.add_all([job_posting, application])
    await db_session.commit()

    publish_response = await client.post(
        f"/api/v1/companies/me/applicants/{application.id}/interview-availabilities",
        headers=company_auth_headers,
        json={
            "slots": [
                {
                    "starts_at": "2026-03-20T10:00",
                    "ends_at": "2026-03-20T10:30",
                    "timezone": "America/Toronto",
                    "notes": "Google Meet",
                },
                {
                    "starts_at": "2026-03-21T14:00",
                    "ends_at": "2026-03-21T14:30",
                    "timezone": "America/Toronto",
                },
            ],
            "notes": "Choose the slot that works best for you.",
        },
    )

    assert publish_response.status_code == 200
    publish_payload = publish_response.json()
    assert publish_payload["application"]["status"] == "interview"
    assert len(publish_payload["application"]["available_interview_slots"]) == 2
    assert publish_payload["application"]["selected_interview_slot"] is None

    candidate_applications_response = await client.get("/api/v1/applications", headers=auth_headers)
    assert candidate_applications_response.status_code == 200
    candidate_application = candidate_applications_response.json()[0]
    assert candidate_application["status"] == "interview"
    assert len(candidate_application["available_interview_slots"]) == 2

    first_slot_id = candidate_application["available_interview_slots"][0]["id"]
    select_response = await client.post(
        f"/api/v1/applications/{application.id}/interview-selection",
        headers=auth_headers,
        json={"slot_id": first_slot_id},
    )

    assert select_response.status_code == 200
    selection_payload = select_response.json()
    assert selection_payload["selected_interview_slot"]["id"] == first_slot_id
    assert selection_payload["available_interview_slots"] == []

    slot_result = await db_session.execute(
        select(InterviewAvailabilityModel).where(
            InterviewAvailabilityModel.application_id == application.id
        )
    )
    slots = slot_result.scalars().all()
    assert len(slots) == 2
    assert sum(1 for slot in slots if slot.status == InterviewAvailabilityStatus.BOOKED) == 1
    assert sum(1 for slot in slots if slot.status == InterviewAvailabilityStatus.CANCELLED) == 1

    email_result = await db_session.execute(
        select(EmailNotificationLogModel)
        .where(EmailNotificationLogModel.application_id == application.id)
        .order_by(EmailNotificationLogModel.created_at.asc())
    )
    email_logs = email_result.scalars().all()
    template_keys = [log.template_key for log in email_logs]
    assert "candidate_interview_availability_shared" in template_keys
    assert "candidate_interview_confirmed" in template_keys
    assert "recruiter_interview_confirmed" in template_keys
