"""
Tests for application endpoints
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.userModel import User
from app.models.companyModel import Company
from app.models.applicationModel import ApplicationModel, ApplicationStatus
from app.models.applicationAnalyticsModel import (
    ApplicationDailyAggregateModel,
    ApplicationEventType,
    ApplicationStatusEventModel,
)
from app.models.jobPostingModel import JobPosting
from app.models.resumeCourseEvaluationModel import (
    ResumeCourseEvaluationModel,
    ResumeCourseEvaluationStatus,
)
from app.models.resumeModel import ResumeModel
import uuid


async def create_approved_resume(*, db_session: AsyncSession, test_user: User, filename: str = "resume.pdf") -> ResumeModel:
    resume = ResumeModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        view_url=f"https://example.com/{filename}",
        storage_file_id=f"resumes/{filename}",
        original_filename=filename,
        folder_id="test-bucket",
        ai_summary="Approved resume summary",
        contact_phone="+1 555 0100",
    )
    evaluation = ResumeCourseEvaluationModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        resume_id=resume.id,
        status=ResumeCourseEvaluationStatus.COMPLETED,
        overall_score=8.7,
        pass_status=True,
    )
    db_session.add_all([resume, evaluation])
    await db_session.commit()
    return resume


class TestApplications:
    """Test application endpoints"""
    
    @pytest.mark.asyncio
    async def test_create_application(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_company: Company,
        test_company_recruiter,
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
        resume = await create_approved_resume(db_session=db_session, test_user=test_user)
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
        assert data["match_strength"] in {"strong_match", "match", "weak_match"}
        assert "id" in data
        assert data["assigned_recruiter_id"] == str(test_company_recruiter.id)
        assert data["resume_id"] == str(resume.id)

        event_result = await db_session.execute(
            select(ApplicationStatusEventModel).where(
                ApplicationStatusEventModel.application_id == uuid.UUID(data["id"])
            )
        )
        events = event_result.scalars().all()
        assert len(events) == 1
        assert events[0].event_type == ApplicationEventType.CREATED
        assert events[0].from_status is None
        assert events[0].to_status == ApplicationStatus.APPLIED

        aggregate_result = await db_session.execute(
            select(ApplicationDailyAggregateModel).where(
                ApplicationDailyAggregateModel.company_id == test_company.id
            )
        )
        aggregate = aggregate_result.scalar_one()
        assert aggregate.applications_created_count == 1
        assert aggregate.entered_applied_count == 1

    @pytest.mark.asyncio
    async def test_create_application_is_idempotent_for_same_job_posting(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_company: Company,
        test_company_recruiter,
        db_session: AsyncSession,
    ):
        job_posting = JobPosting(
            id=uuid.uuid4(),
            company_id=test_company.id,
            title="Platform Engineer",
            description="Great opportunity",
        )
        resume = await create_approved_resume(db_session=db_session, test_user=test_user)
        db_session.add(job_posting)
        await db_session.commit()

        payload = {
            "company_id": str(test_company.id),
            "job_posting_id": str(job_posting.id),
            "job_title": "Platform Engineer",
            "status": "applied",
        }

        first_response = await client.post("/api/v1/applications", headers=auth_headers, json=payload)
        second_response = await client.post("/api/v1/applications", headers=auth_headers, json=payload)

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert first_response.json()["id"] == second_response.json()["id"]
        assert first_response.json()["match_strength"] == second_response.json()["match_strength"]
        assert second_response.json()["assigned_recruiter_id"] == str(test_company_recruiter.id)
        assert second_response.json()["resume_id"] == str(resume.id)

    @pytest.mark.asyncio
    async def test_create_application_requires_students_compass_approved_resume(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_company: Company,
        db_session: AsyncSession,
    ):
        job_posting = JobPosting(
            id=uuid.uuid4(),
            company_id=test_company.id,
            title="Backend Engineer",
            description="Role",
        )
        resume = ResumeModel(
            id=uuid.uuid4(),
            user_id=test_user.id,
            view_url="https://example.com/unapproved.pdf",
            storage_file_id="resumes/unapproved.pdf",
            original_filename="unapproved.pdf",
            folder_id="test-bucket",
        )
        db_session.add_all([job_posting, resume])
        await db_session.commit()

        response = await client.post(
            "/api/v1/applications",
            headers=auth_headers,
            json={
                "company_id": str(test_company.id),
                "job_posting_id": str(job_posting.id),
                "resume_id": str(resume.id),
                "job_title": "Backend Engineer",
                "status": "applied",
            },
        )

        assert response.status_code == 400
        assert "approved resume" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_eligible_resumes_returns_only_approved_resumes(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        approved_resume = await create_approved_resume(db_session=db_session, test_user=test_user, filename="approved_resume.pdf")
        rejected_resume = ResumeModel(
            id=uuid.uuid4(),
            user_id=test_user.id,
            view_url="https://example.com/rejected.pdf",
            storage_file_id="resumes/rejected.pdf",
            original_filename="rejected.pdf",
            folder_id="test-bucket",
        )
        rejected_evaluation = ResumeCourseEvaluationModel(
            id=uuid.uuid4(),
            user_id=test_user.id,
            resume_id=rejected_resume.id,
            status=ResumeCourseEvaluationStatus.COMPLETED,
            overall_score=6.5,
            pass_status=False,
        )
        db_session.add_all([rejected_resume, rejected_evaluation])
        await db_session.commit()

        response = await client.get("/api/v1/applications/eligible-resumes", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(approved_resume.id)
        assert data[0]["is_latest"] is True
        assert data[0]["overall_score"] == 8.7
    
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

        event_result = await db_session.execute(
            select(ApplicationStatusEventModel)
            .where(ApplicationStatusEventModel.company_id == test_company.id)
            .order_by(ApplicationStatusEventModel.occurred_at.desc())
        )
        events = event_result.scalars().all()
        assert len(events) == 1
        assert events[0].event_type == ApplicationEventType.STATUS_CHANGED
        assert events[0].from_status == ApplicationStatus.APPLIED
        assert events[0].to_status == ApplicationStatus.INTERVIEW

        aggregate_result = await db_session.execute(
            select(ApplicationDailyAggregateModel).where(
                ApplicationDailyAggregateModel.company_id == test_company.id
            )
        )
        aggregate = aggregate_result.scalar_one()
        assert aggregate.status_change_events_count == 1
        assert aggregate.entered_interview_count == 1
    
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

        event_result = await db_session.execute(
            select(ApplicationStatusEventModel)
            .where(ApplicationStatusEventModel.company_id == test_company.id)
            .order_by(ApplicationStatusEventModel.occurred_at.desc())
        )
        events = event_result.scalars().all()
        assert len(events) == 1
        assert events[0].event_type == ApplicationEventType.DELETED
        assert events[0].from_status == ApplicationStatus.APPLIED
        assert events[0].to_status is None

        aggregate_result = await db_session.execute(
            select(ApplicationDailyAggregateModel).where(
                ApplicationDailyAggregateModel.company_id == test_company.id
            )
        )
        aggregate = aggregate_result.scalar_one()
        assert aggregate.applications_deleted_count == 1
        
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
