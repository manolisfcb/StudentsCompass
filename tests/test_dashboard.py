"""
Tests for dashboard endpoints
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
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
        # Create job posting
        job_posting = JobPosting(
            id=uuid.uuid4(),
            company_id=test_company.id,
            title="Software Engineer",
            description="Great job",
            location="Remote"
        )
        db_session.add(job_posting)
        
        # Create applications
        applications = [
            ApplicationModel(
                id=uuid.uuid4(),
                user_id=test_user.id,
                company_id=test_company.id,
                job_posting_id=job_posting.id,
                job_title="Software Engineer",
                status=ApplicationStatus.APPLIED
            ),
            ApplicationModel(
                id=uuid.uuid4(),
                user_id=test_user.id,
                company_id=test_company.id,
                job_posting_id=job_posting.id,
                job_title="Backend Developer",
                status=ApplicationStatus.IN_REVIEW
            ),
            ApplicationModel(
                id=uuid.uuid4(),
                user_id=test_user.id,
                company_id=test_company.id,
                job_posting_id=job_posting.id,
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
            storage_file_id="test/resume.pdf"
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
