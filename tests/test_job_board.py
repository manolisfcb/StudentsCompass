import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi_users.password import PasswordHelper

from app.models.companyModel import Company
from app.models.companyRecruiterModel import CompanyRecruiter
from app.models.jobPostingModel import JobPosting


class DummyLinkedInJob:
    def __init__(self, title: str, company: str, location: str, url: str, listed_at: str | None = None):
        self.title = title
        self.company = company
        self.location = location
        self.url = url
        self.listed_at = listed_at


@pytest.mark.asyncio
async def test_company_can_create_job_posting(
    client: AsyncClient,
    company_auth_headers: dict,
    test_company: Company,
    db_session: AsyncSession,
):
    response = await client.post(
        "/api/v1/companies/me/job-postings",
        headers=company_auth_headers,
        json={
            "title": "Python Developer Intern",
            "description": "Build backend features for students.",
            "location": "Remote",
            "job_type": "Internship",
            "workplace_type": "Remote",
            "seniority_level": "Entry level",
            "benefits": "Mentorship and flexible schedule",
            "application_url": "https://example.com/jobs/python-intern",
            "is_active": True,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["company_id"] == str(test_company.id)
    assert data["title"] == "Python Developer Intern"
    assert data["workplace_type"] == "Remote"
    assert data["seniority_level"] == "Entry level"
    assert data["application_url"] == "https://example.com/jobs/python-intern"

    created_job = await db_session.get(JobPosting, uuid.UUID(data["id"]))
    assert created_job is not None
    assert created_job.company_id == test_company.id


@pytest.mark.asyncio
async def test_student_job_board_lists_internal_jobs(
    client: AsyncClient,
    auth_headers: dict,
    test_company: Company,
    db_session: AsyncSession,
):
    job_posting = JobPosting(
        id=uuid.uuid4(),
        company_id=test_company.id,
        title="Frontend Engineer",
        description="Build the student-facing job board.",
        location="Toronto",
        application_url="https://example.com/jobs/frontend",
        is_active=True,
    )
    db_session.add(job_posting)
    await db_session.commit()

    response = await client.get("/api/v1/jobs/board", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Frontend Engineer"
    assert data[0]["company_name"] == test_company.company_name
    assert data[0]["source"] == "students_compass"


@pytest.mark.asyncio
async def test_job_search_returns_students_compass_first_and_then_linkedin(
    client: AsyncClient,
    auth_headers: dict,
    test_company: Company,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    job_posting = JobPosting(
        id=uuid.uuid4(),
        company_id=test_company.id,
        title="Python Developer",
        description="Work on FastAPI services.",
        location="Remote",
        application_url="https://example.com/jobs/python-dev",
        is_active=True,
    )
    db_session.add(job_posting)
    await db_session.commit()

    def fake_linkedin_jobs(**kwargs):
        return [
            DummyLinkedInJob(
                title="Python Developer External",
                company="LinkedIn Co",
                location="Remote",
                url="https://linkedin.example/jobs/python-developer",
                listed_at="2026-03-10",
            )
        ]

    monkeypatch.setattr("app.routes.jobRoute.fetch_linkedin_jobs", fake_linkedin_jobs)

    response = await client.post(
        "/api/v1/jobs/search",
        headers=auth_headers,
        json={
            "keywords": "python",
            "location": "Remote",
            "limit": 10,
            "remote": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["students_compass"]) == 1
    assert data["students_compass"][0]["title"] == "Python Developer"
    assert data["students_compass"][0]["source"] == "students_compass"
    assert data["students_compass"][0]["url"] == "https://example.com/jobs/python-dev"
    assert len(data["linkedin"]) == 1
    assert data["linkedin"][0]["title"] == "Python Developer External"
    assert data["linkedin"][0]["source"] == "linkedin"


@pytest.mark.asyncio
async def test_job_search_falls_back_to_linkedin_when_no_internal_matches(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_linkedin_jobs(**kwargs):
        return [
            DummyLinkedInJob(
                title="Data Analyst",
                company="LinkedIn Co",
                location="Remote",
                url="https://linkedin.example/jobs/data-analyst",
                listed_at="2026-03-10",
            )
        ]

    monkeypatch.setattr("app.routes.jobRoute.fetch_linkedin_jobs", fake_linkedin_jobs)

    response = await client.post(
        "/api/v1/jobs/search",
        headers=auth_headers,
        json={
            "keywords": "data analyst",
            "location": "Remote",
            "limit": 10,
            "remote": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["students_compass"] == []
    assert len(data["linkedin"]) == 1
    assert data["linkedin"][0]["title"] == "Data Analyst"
    assert data["linkedin"][0]["source"] == "linkedin"
    assert data["linkedin"][0]["source_label"] == "LinkedIn"


@pytest.mark.asyncio
async def test_company_can_delete_its_own_job_posting(
    client: AsyncClient,
    company_auth_headers: dict,
    test_company: Company,
    db_session: AsyncSession,
):
    job_posting = JobPosting(
        id=uuid.uuid4(),
        company_id=test_company.id,
        title="Delete Me",
        description="Temporary role.",
        is_active=True,
    )
    db_session.add(job_posting)
    await db_session.commit()
    job_id = job_posting.id

    response = await client.delete(
        f"/api/v1/companies/me/job-postings/{job_id}",
        headers=company_auth_headers,
    )

    assert response.status_code == 204
    db_session.expire_all()
    deleted_job = await db_session.execute(select(JobPosting).where(JobPosting.id == job_id))
    assert deleted_job.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_student_cannot_delete_company_job_posting(
    client: AsyncClient,
    auth_headers: dict,
    test_company: Company,
    db_session: AsyncSession,
):
    job_posting = JobPosting(
        id=uuid.uuid4(),
        company_id=test_company.id,
        title="Protected Job",
        description="Students cannot delete this.",
        is_active=True,
    )
    db_session.add(job_posting)
    await db_session.commit()

    response = await client.delete(
        f"/api/v1/companies/me/job-postings/{job_posting.id}",
        headers=auth_headers,
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_company_viewer_cannot_manage_job_postings(
    client: AsyncClient,
    test_company_recruiter: CompanyRecruiter,
    db_session: AsyncSession,
):
    password_helper = PasswordHelper()
    viewer = CompanyRecruiter(
        id=uuid.uuid4(),
        company_id=test_company_recruiter.company_id,
        email="job-viewer@example.com",
        hashed_password=password_helper.hash("password123"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        role="viewer",
    )
    db_session.add(viewer)
    await db_session.commit()

    login_response = await client.post(
        "/api/v1/auth/company/login",
        data={
            "username": viewer.email,
            "password": "password123",
        },
    )
    assert login_response.status_code in (200, 204)

    create_response = await client.post(
        "/api/v1/companies/me/job-postings",
        json={
            "title": "Viewer Cannot Post",
            "description": "Should be forbidden",
            "is_active": True,
        },
    )
    assert create_response.status_code == 403
    assert create_response.json()["detail"] == "Only company recruiters can manage job postings"

    protected_job = JobPosting(
        id=uuid.uuid4(),
        company_id=test_company_recruiter.company_id,
        title="Protected Job",
        description="Cannot be deleted by viewer",
        is_active=True,
    )
    db_session.add(protected_job)
    await db_session.commit()

    delete_response = await client.delete(f"/api/v1/companies/me/job-postings/{protected_job.id}")
    assert delete_response.status_code == 403
    assert delete_response.json()["detail"] == "Only company recruiters can manage job postings"
