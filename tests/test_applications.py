"""
Tests for application endpoints
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.userModel import User
from app.models.companyModel import Company
from app.models.applicationModel import ApplicationModel, ApplicationStatus
from app.models.jobPostingModel import JobPosting
import uuid


class TestApplications:
    """Test application endpoints"""
    
    @pytest.mark.asyncio
    async def test_create_application(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_company: Company,
        db_session: AsyncSession
    ):
        """Test creating a new application"""
        # Create job posting first
        job_posting = JobPosting(
            id=uuid.uuid4(),
            company_id=test_company.id,
            title="Software Engineer",
            description="Great opportunity"
        )
        db_session.add(job_posting)
        await db_session.commit()
        await db_session.refresh(job_posting)
        
        response = await client.post(
            "/api/v1/applications",
            headers=auth_headers,
            json={
                "company_id": str(test_company.id),
                "job_posting_id": str(job_posting.id),
                "job_title": "Software Engineer",
                "status": "applied",
                "notes": "Excited about this opportunity"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_title"] == "Software Engineer"
        assert data["status"] == "applied"
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_create_application_unauthorized(
        self,
        client: AsyncClient,
        test_company: Company
    ):
        """Test creating application without auth fails"""
        response = await client.post(
            "/api/v1/applications",
            json={
                "company_id": str(test_company.id),
                "job_title": "Software Engineer",
                "status": "applied"
            }
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_user_applications(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_company: Company,
        db_session: AsyncSession
    ):
        """Test getting user's applications"""
        # Create applications
        app1 = ApplicationModel(
            user_id=test_user.id,
            company_id=test_company.id,
            job_title="Software Engineer",
            status=ApplicationStatus.APPLIED
        )
        app2 = ApplicationModel(
            user_id=test_user.id,
            company_id=test_company.id,
            job_title="Backend Developer",
            status=ApplicationStatus.IN_REVIEW
        )
        db_session.add_all([app1, app2])
        await db_session.commit()
        
        response = await client.get(
            "/api/v1/applications",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all("job_title" in app for app in data)
    
    @pytest.mark.asyncio
    async def test_get_applications_empty(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test getting applications when user has none"""
        response = await client.get(
            "/api/v1/applications",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json() == []
    
    @pytest.mark.asyncio
    async def test_update_application_status(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_company: Company,
        db_session: AsyncSession
    ):
        """Test updating application status"""
        # Create application
        app = ApplicationModel(
            user_id=test_user.id,
            company_id=test_company.id,
            job_title="Software Engineer",
            status=ApplicationStatus.APPLIED
        )
        db_session.add(app)
        await db_session.commit()
        await db_session.refresh(app)
        
        response = await client.patch(
            f"/api/v1/applications/{app.id}",
            headers=auth_headers,
            json={
                "status": "interview",
                "notes": "Interview scheduled for next week"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "interview"
        assert data["notes"] == "Interview scheduled for next week"
    
    @pytest.mark.asyncio
    async def test_update_nonexistent_application(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test updating non-existent application fails"""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await client.patch(
            f"/api/v1/applications/{fake_uuid}",
            headers=auth_headers,
            json={"status": "interview"}
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_delete_application(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_company: Company,
        db_session: AsyncSession
    ):
        """Test deleting an application"""
        # Create application
        app = ApplicationModel(
            user_id=test_user.id,
            company_id=test_company.id,
            job_title="Software Engineer",
            status=ApplicationStatus.APPLIED
        )
        db_session.add(app)
        await db_session.commit()
        await db_session.refresh(app)
        
        response = await client.delete(
            f"/api/v1/applications/{app.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert "message" in response.json()
        
        # Verify application is deleted
        response = await client.get(
            "/api/v1/applications",
            headers=auth_headers
        )
        assert len(response.json()) == 0
    
    @pytest.mark.asyncio
    async def test_delete_other_user_application(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_company: Company,
        db_session: AsyncSession
    ):
        """Test users can't delete other users' applications"""
        # Create another user
        from app.models.userModel import User
        
        other_user = User(
            id=uuid.uuid4(),
            email="other@example.com",
            hashed_password="hashed",
            is_active=True
        )
        db_session.add(other_user)
        
        # Create application for other user
        app = ApplicationModel(
            user_id=other_user.id,
            company_id=test_company.id,
            job_title="Software Engineer",
            status=ApplicationStatus.APPLIED
        )
        db_session.add(app)
        await db_session.commit()
        await db_session.refresh(app)
        
        # Try to delete as test_user
        response = await client.delete(
            f"/api/v1/applications/{app.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 404
