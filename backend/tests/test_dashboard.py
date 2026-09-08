"""
Tests for dashboard endpoints
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from app.models.userModel import User
from app.models.applicationModel import ApplicationModel, ApplicationStatus
from app.models.resumeModel import ResumeModel
from app.models.companyModel import Company
from app.models.jobPostingModel import JobPosting
import uuid


class TestDashboard:
    """Test dashboard endpoints"""
    
    @pytest.mark.asyncio
    async def test_get_students_dashboard_no_data(
        self, 
        client: AsyncClient, 
        auth_headers: dict,
        test_user: User
    ):
        """Test dashboard with no applications"""
        response = await client.get(
            "/api/v1/students_dashboard",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check stats
        assert data["stats"]["total_applications"] == 0
        assert data["stats"]["in_review"] == 0
        assert data["stats"]["interviews_scheduled"] == 0
        assert data["stats"]["offers_received"] == 0
        assert "overall_progress" in data["stats"]
        
        # Check progress
        assert "resume" in data["progress"]
        assert "linkedin" in data["progress"]
        assert "interview_prep" in data["progress"]
        
        # Check application breakdown
        assert data["application_breakdown"]["applied"] == 0
        
        # Check resources exist
        assert len(data["resources"]) > 0
    
    @pytest.mark.asyncio
    async def test_get_students_dashboard_with_applications(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_company: Company,
        db_session: AsyncSession
    ):
        """Test dashboard with applications"""
        job_postings = [
            JobPosting(
                id=uuid.uuid4(),
                company_id=test_company.id,
                title="Software Engineer",
                description="Great job",
                location="Remote",
            ),
            JobPosting(
                id=uuid.uuid4(),
                company_id=test_company.id,
                title="Backend Developer",
                description="Backend role",
                location="Remote",
            ),
            JobPosting(
                id=uuid.uuid4(),
                company_id=test_company.id,
                title="Frontend Developer",
                description="Frontend role",
                location="Remote",
            ),
        ]
        for job_posting in job_postings:
            db_session.add(job_posting)

        applications = [
            ApplicationModel(
                id=uuid.uuid4(),
                user_id=test_user.id,
                company_id=test_company.id,
                job_posting_id=job_postings[0].id,
                job_title="Software Engineer",
                status=ApplicationStatus.APPLIED
            ),
            ApplicationModel(
                id=uuid.uuid4(),
                user_id=test_user.id,
                company_id=test_company.id,
                job_posting_id=job_postings[1].id,
                job_title="Backend Developer",
                status=ApplicationStatus.IN_REVIEW
            ),
            ApplicationModel(
                id=uuid.uuid4(),
                user_id=test_user.id,
                company_id=test_company.id,
                job_posting_id=job_postings[2].id,
                job_title="Frontend Developer",
                status=ApplicationStatus.INTERVIEW
            )
        ]
        
        for app in applications:
            db_session.add(app)
        
        await db_session.commit()
        
        # Get dashboard
        response = await client.get(
            "/api/v1/students_dashboard",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check stats
        assert data["stats"]["total_applications"] == 3
        assert data["stats"]["in_review"] == 1
        assert data["stats"]["interviews_scheduled"] == 1
        assert data["application_breakdown"]["applied"] == 1
    
    @pytest.mark.asyncio
    async def test_get_students_dashboard_unauthorized(self, client: AsyncClient):
        """Test dashboard without authentication fails"""
        response = await client.get("/api/v1/students_dashboard")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_students_dashboard_with_resume(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession
    ):
        """Test dashboard progress calculation with resume"""
        # Create resume
        resume = ResumeModel(
            id=uuid.uuid4(),
            user_id=test_user.id,
            view_url="https://example.com/resume.pdf",
            original_filename="resume.pdf",
            storage_file_id="test/resume.pdf",
            folder_id="test/"
        )
        db_session.add(resume)
        await db_session.commit()
        
        response = await client.get(
            "/api/v1/students_dashboard",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Resume progress should be > 0
        assert data["progress"]["resume"] > 0


class TestCompanyDashboard:
    """Test company dashboard endpoint."""

    @pytest.mark.asyncio
    async def test_get_company_dashboard_no_data(
        self,
        client: AsyncClient,
        company_auth_headers: dict,
        test_company: Company,
    ):
        response = await client.get(
            "/api/v1/company_dashboard",
            headers=company_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["company"]["company_name"] == test_company.company_name
        assert data["stats"]["active_job_postings"] == 0
        assert data["stats"]["total_applications"] == 0
        assert data["stats"]["scheduled_interviews"] == 0
        assert data["stats"]["shortlisted"] == 0
        assert data["recent_job_postings"] == []

    @pytest.mark.asyncio
    async def test_get_company_dashboard_with_data(
        self,
        client: AsyncClient,
        company_auth_headers: dict,
        test_company: Company,
        test_user: User,
        db_session: AsyncSession,
    ):
        older_job = JobPosting(
            id=uuid.uuid4(),
            company_id=test_company.id,
            title="Junior Backend Engineer",
            description="Backend role",
            location="Remote",
            is_active=True,
            created_at=datetime.utcnow() - timedelta(days=2),
        )
        latest_job = JobPosting(
            id=uuid.uuid4(),
            company_id=test_company.id,
            title="Frontend Engineer",
            description="Frontend role",
            location="Toronto",
            is_active=False,
            created_at=datetime.utcnow() - timedelta(hours=1),
        )
        db_session.add(older_job)
        db_session.add(latest_job)

        applications = [
            ApplicationModel(
                id=uuid.uuid4(),
                user_id=test_user.id,
                company_id=test_company.id,
                job_posting_id=older_job.id,
                job_title=older_job.title,
                status=ApplicationStatus.APPLIED,
            ),
            ApplicationModel(
                id=uuid.uuid4(),
                user_id=test_user.id,
                company_id=test_company.id,
                job_posting_id=latest_job.id,
                job_title=latest_job.title,
                status=ApplicationStatus.IN_REVIEW,
            ),
            ApplicationModel(
                id=uuid.uuid4(),
                user_id=test_user.id,
                company_id=test_company.id,
                job_posting_id=None,
                job_title="Operations Analyst",
                status=ApplicationStatus.INTERVIEW,
            ),
            ApplicationModel(
                id=uuid.uuid4(),
                user_id=test_user.id,
                company_id=test_company.id,
                job_posting_id=None,
                job_title="Community Coordinator",
                status=ApplicationStatus.OFFER,
            ),
        ]
        for application in applications:
            db_session.add(application)

        await db_session.commit()

        response = await client.get(
            "/api/v1/company_dashboard",
            headers=company_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["stats"]["active_job_postings"] == 1
        assert data["stats"]["total_applications"] == 4
        assert data["stats"]["scheduled_interviews"] == 1
        assert data["stats"]["shortlisted"] == 1
        assert len(data["recent_job_postings"]) == 2
        assert data["recent_job_postings"][0]["title"] == "Frontend Engineer"
        assert data["recent_job_postings"][0]["status"] == "closed"
        assert data["recent_job_postings"][1]["title"] == "Junior Backend Engineer"
        assert data["recent_job_postings"][1]["status"] == "active"
        assert data["recent_job_postings"][0]["application_count"] == 1
        assert data["recent_job_postings"][1]["application_count"] == 1

    @pytest.mark.asyncio
    async def test_get_company_dashboard_unauthorized(self, client: AsyncClient):
        response = await client.get("/api/v1/company_dashboard")
        assert response.status_code == 401
