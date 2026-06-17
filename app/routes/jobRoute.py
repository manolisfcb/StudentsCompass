from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request, status
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_session
from app.services.userService import current_active_user
from app.models.userModel import User
from app.models.resumeModel import ResumeModel
from app.models.jobAnalysisModel import JobAnalysisModel, JobStatus
from sqlalchemy import select
import logging
from uuid import UUID
from collections import deque
from time import monotonic
from app.models.companyModel import Company
from app.models.jobPostingModel import JobPosting
from app.schemas.jobPostingSchema import (
    CompanyJobPostingCreate,
    JobBoardPostingRead,
    JobPostingRead,
    JobPostingUpdate,
)
from app.services.companyService import current_active_company
from app.services.companyService import current_company_job_manager_recruiter
from app.services.jobPostingService import JobPostingService
from app.services.cvAnalysisService import CVAnalysisService, LLM_GENERAL_FAILURE_MESSAGE
from app.services.jobSearchService import JobSearchQuery, JobSearchService
from app.models.companyRecruiterModel import CompanyRecruiter

LOGGER = logging.getLogger(__name__)

router = APIRouter()

# Rate limit LLM analysis: 5 requests per IP per minute
LLM_RATE_LIMIT_PER_MINUTE = 5
LLM_RATE_LIMIT_WINDOW_SECONDS = 60
_llm_rate_limit_store: dict[str, deque[float]] = {}

def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_llm_rate_limit(request: Request) -> None:
    ip = _get_client_ip(request)
    now = monotonic()
    timestamps = _llm_rate_limit_store.get(ip)
    if timestamps is None:
        timestamps = deque()
        _llm_rate_limit_store[ip] = timestamps

    while timestamps and now - timestamps[0] > LLM_RATE_LIMIT_WINDOW_SECONDS:
        timestamps.popleft()

    if len(timestamps) >= LLM_RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail="Too many analysis requests right now. Please wait a minute and try again.",
        )

    timestamps.append(now)


class JobSearchRequest(BaseModel):
    keywords: str
    location: str
    limit: int = 25
    remote: bool = False


class JobResponse(BaseModel):
    id: Optional[str] = None
    company_id: Optional[str] = None
    title: str
    company: str
    location: str
    url: Optional[str] = None
    listed_at: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    responsibilities: Optional[str] = None
    job_type: Optional[str] = None
    workplace_type: Optional[str] = None
    seniority_level: Optional[str] = None
    salary_range: Optional[str] = None
    benefits: Optional[str] = None
    listed_context: Optional[str] = None
    source_context: Optional[str] = None
    company_description: Optional[str] = None
    company_website: Optional[str] = None
    company_location: Optional[str] = None
    source: str = "students_compass"
    source_label: str = "Students Compass"


class JobSearchResultsResponse(BaseModel):
    students_compass: List[JobResponse]
    linkedin: List[JobResponse]


@router.get("/jobs/board", response_model=List[JobBoardPostingRead])
async def list_job_board_postings(
    keywords: Optional[str] = None,
    location: Optional[str] = None,
    limit: int = 50,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    del user
    service = JobPostingService(session)
    jobs = await service.list_public_job_postings(
        keywords=keywords,
        location=location,
        limit=max(1, min(limit, 100)),
    )
    return [
        JobBoardPostingRead(
            id=job.id,
            company_id=job.company_id,
            title=job.title,
            description=job.description,
            requirements=job.requirements,
            responsibilities=job.responsibilities,
            location=job.location,
            job_type=job.job_type,
            salary_range=job.salary_range,
            workplace_type=job.workplace_type,
            seniority_level=job.seniority_level,
            benefits=job.benefits,
            listed_context=job.listed_context,
            source_context=job.source_context,
            application_url=job.application_url,
            is_active=job.is_active,
            expires_at=job.expires_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
            company_name=job.company.company_name if job.company else None,
            company_location=job.company.location if job.company else None,
            company_description=job.company.description if job.company else None,
            company_website=job.company.website if job.company else None,
        )
        for job in jobs
    ]


@router.post("/jobs/search", response_model=JobSearchResultsResponse)
async def search_jobs(
    request: JobSearchRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Search Students Compass first, then append LinkedIn results after internal matches."""
    try:
        del user
        return await JobSearchService(session).search(
            JobSearchQuery(
                keywords=request.keywords,
                location=request.location,
                limit=request.limit,
                remote=request.remote,
            )
        )
    except Exception as e:
        LOGGER.exception("Job search failed")
        raise HTTPException(status_code=500, detail=f"Job search failed: {str(e)}")


@router.get("/companies/me/job-postings", response_model=List[JobBoardPostingRead])
async def list_current_company_job_postings(
    company: Company = Depends(current_active_company),
    recruiter: CompanyRecruiter = Depends(current_company_job_manager_recruiter),
    session: AsyncSession = Depends(get_session),
):
    del recruiter
    service = JobPostingService(session)
    jobs = await service.list_company_job_postings(company.id, include_closed=True, limit=100)
    return [
        JobBoardPostingRead(
            id=job.id,
            company_id=job.company_id,
            title=job.title,
            description=job.description,
            requirements=job.requirements,
            responsibilities=job.responsibilities,
            location=job.location,
            job_type=job.job_type,
            salary_range=job.salary_range,
            workplace_type=job.workplace_type,
            seniority_level=job.seniority_level,
            benefits=job.benefits,
            listed_context=job.listed_context,
            source_context=job.source_context,
            application_url=job.application_url,
            is_active=job.is_active,
            expires_at=job.expires_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
            company_name=job.company.company_name if job.company else None,
            company_location=job.company.location if job.company else None,
            company_description=job.company.description if job.company else None,
            company_website=job.company.website if job.company else None,
        )
        for job in jobs
    ]


@router.post(
    "/companies/me/job-postings",
    response_model=JobPostingRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_current_company_job_posting(
    payload: CompanyJobPostingCreate,
    company: Company = Depends(current_active_company),
    recruiter: CompanyRecruiter = Depends(current_company_job_manager_recruiter),
    session: AsyncSession = Depends(get_session),
):
    del recruiter
    service = JobPostingService(session)
    job = await service.create_for_company(company.id, payload)
    return JobPostingRead.model_validate(job)


@router.patch("/companies/me/job-postings/{job_posting_id}", response_model=JobPostingRead)
async def update_current_company_job_posting(
    job_posting_id: UUID,
    payload: JobPostingUpdate,
    company: Company = Depends(current_active_company),
    recruiter: CompanyRecruiter = Depends(current_company_job_manager_recruiter),
    session: AsyncSession = Depends(get_session),
):
    del recruiter
    service = JobPostingService(session)
    job = await service.update_company_job_posting(company.id, job_posting_id, payload)
    if job is None:
        raise HTTPException(status_code=404, detail="Job posting not found")
    return JobPostingRead.model_validate(job)


@router.delete("/companies/me/job-postings/{job_posting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_company_job_posting(
    job_posting_id: UUID,
    company: Company = Depends(current_active_company),
    recruiter: CompanyRecruiter = Depends(current_company_job_manager_recruiter),
    session: AsyncSession = Depends(get_session),
):
    del recruiter
    service = JobPostingService(session)
    deleted = await service.delete_company_job_posting(company.id, job_posting_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job posting not found")


class KeywordsResponse(BaseModel):
    keywords: str
    has_cv: bool
    cv_filename: Optional[str] = None
    summary: Optional[str] = None


class JobInitResponse(BaseModel):
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    keywords: Optional[str] = None
    summary: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


async def process_cv_analysis(job_id: UUID, user_id: UUID, resume_id: UUID, session_factory):
    """Background task to process CV and extract keywords plus a recruiter-facing summary."""
    async for session in session_factory():
        await CVAnalysisService(session).process_job(
            job_id=job_id,
            user_id=user_id,
            resume_id=resume_id,
        )
        break


@router.post("/jobs/keywords/analyze", response_model=JobInitResponse)
async def start_cv_analysis(
    background_tasks: BackgroundTasks,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),

):
    """Start CV analysis job - returns immediately with job_id"""
    try:
        # Check if user has a CV
        result = await session.execute(
            select(ResumeModel)
            .where(ResumeModel.user_id == user.id)
            .order_by(ResumeModel.created_at.desc())
            .limit(1)
        )
        resume = result.scalar_one_or_none()
        
        if not resume:
            raise HTTPException(status_code=404, detail="No CV found. Please upload your CV first.")
        
        # If this resume has already been analyzed, return cached job directly
        result = await session.execute(
            select(JobAnalysisModel)
            .where(JobAnalysisModel.user_id == user.id)
            .where(JobAnalysisModel.resume_id == resume.id)
            .where(JobAnalysisModel.status == JobStatus.COMPLETED)
            .where(JobAnalysisModel.keywords.is_not(None))
            .order_by(JobAnalysisModel.completed_at.desc())
            .limit(1)
        )
        cached_job = result.scalar_one_or_none()
        if cached_job and cached_job.keywords:
            return JobInitResponse(
                job_id=str(cached_job.id),
                status=cached_job.status.value,
                message="CV already analyzed. Using cached keywords."
            )

        # If there's already a running job for this same resume, reuse it
        result = await session.execute(
            select(JobAnalysisModel)
            .where(JobAnalysisModel.user_id == user.id)
            .where(JobAnalysisModel.resume_id == resume.id)
            .where(JobAnalysisModel.status.in_([JobStatus.PENDING, JobStatus.PROCESSING]))
            .order_by(JobAnalysisModel.created_at.desc())
            .limit(1)
        )
        running_job = result.scalar_one_or_none()
        if running_job:
            return JobInitResponse(
                job_id=str(running_job.id),
                status=running_job.status.value,
                message="CV analysis already in progress for this resume."
            )

        await CVAnalysisService(session).ensure_daily_limit(user.id)
        _check_llm_rate_limit(request)

        # Create new job
        job = JobAnalysisModel(
            user_id=user.id,
            resume_id=resume.id,
            status=JobStatus.PENDING
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        
        LOGGER.info(f"Created job {job.id} for user {user.id}")
        
        # Schedule background processing
        from app.db import get_session as get_session_factory
        background_tasks.add_task(process_cv_analysis, job.id, user.id, resume.id, get_session_factory)
        
        return JobInitResponse(
            job_id=str(job.id),
            status=job.status.value,
            message="CV analysis started. Use the job_id to check status."
        )
        
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception("Failed to start CV analysis")
        raise HTTPException(status_code=500, detail=LLM_GENERAL_FAILURE_MESSAGE)


@router.get("/jobs/keywords/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    """Get status of CV analysis job (for polling)"""
    try:
        result = await session.execute(
            select(JobAnalysisModel)
            .where(JobAnalysisModel.id == job_id)
            .where(JobAnalysisModel.user_id == user.id)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return JobStatusResponse(
            job_id=str(job.id),
            status=job.status.value,
            keywords=job.keywords,
            summary=job.summary,
            error_message=job.error_message,
            created_at=job.created_at.isoformat(),
            completed_at=job.completed_at.isoformat() if job.completed_at else None
        )
        
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception("Failed to get job status")
        raise HTTPException(status_code=500, detail="Could not fetch analysis status right now. Please retry.")


@router.get("/jobs/keywords", response_model=KeywordsResponse)
async def get_job_keywords(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    """Check if user has CV (for initial check)"""
    try:
        # Check if user has a CV
        result = await session.execute(
            select(ResumeModel)
            .where(ResumeModel.user_id == user.id)
            .order_by(ResumeModel.created_at.desc())
            .limit(1)
        )
        resume = result.scalar_one_or_none()
        
        if not resume:
            # No CV - return user name as fallback
            keywords = ""
            if user.first_name:
                keywords += user.first_name
            if user.last_name:
                if keywords:
                    keywords += " "
                keywords += user.last_name
            return KeywordsResponse(
                keywords=keywords or "developer",
                has_cv=False,
            )
        
        # Check if there's a completed job for this exact resume
        result = await session.execute(
            select(JobAnalysisModel)
            .where(JobAnalysisModel.user_id == user.id)
            .where(JobAnalysisModel.resume_id == resume.id)
            .where(JobAnalysisModel.status == JobStatus.COMPLETED)
            .order_by(JobAnalysisModel.completed_at.desc())
            .limit(1)
        )
        last_job = result.scalar_one_or_none()

        # Backward compatibility: if old rows didn't store resume_id, fallback to latest completed
        if not last_job:
            result = await session.execute(
                select(JobAnalysisModel)
                .where(JobAnalysisModel.user_id == user.id)
                .where(JobAnalysisModel.status == JobStatus.COMPLETED)
                .order_by(JobAnalysisModel.completed_at.desc())
                .limit(1)
            )
            last_job = result.scalar_one_or_none()
        
        if last_job and last_job.keywords:
            # Return cached keywords from last successful job
            return KeywordsResponse(
                keywords=last_job.keywords,
                has_cv=True,
                cv_filename=resume.original_filename,
                summary=resume.ai_summary or last_job.summary,
            )
        
        # Has CV but no analysis yet
        return KeywordsResponse(
            keywords="",
            has_cv=True,
            cv_filename=resume.original_filename,
            summary=resume.ai_summary,
        )
        
    except Exception as e:
        LOGGER.exception("Failed to check CV status")
        return KeywordsResponse(keywords="developer", has_cv=False)
