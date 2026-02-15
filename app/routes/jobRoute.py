from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.JobsScraper.scrapper_propio import fetch_linkedin_jobs
from app.db import get_session
import asyncio
from app.services.userService import current_active_user
from app.models.userModel import User
from app.models.resumeModel import ResumeModel
from app.models.jobAnalysisModel import JobAnalysisModel, JobStatus
from sqlalchemy import select
import logging
from app.core.ResumeAnalizer.read_pdf_data import extract_text_from_pdf
from app.core.ResumeAnalizer.llm_model import ask_llm_model
from app.services.resumeService import ResumeService
import io
import tempfile
import os
from datetime import datetime
from uuid import UUID

LOGGER = logging.getLogger(__name__)

router = APIRouter()


class JobSearchRequest(BaseModel):
    keywords: str
    location: str
    limit: int = 25
    remote: bool = False


class JobResponse(BaseModel):
    title: str
    company: str
    location: str
    url: str
    listed_at: Optional[str] = None


@router.post("/jobs/search", response_model=List[JobResponse])
async def search_jobs(
    request: JobSearchRequest,
    user: User = Depends(current_active_user),
):
    """Search LinkedIn jobs using custom scraper"""
    try:
        LOGGER.debug(
            f"Searching LinkedIn jobs: keywords={request.keywords}, "
            f"location={request.location}, limit={request.limit}, remote={request.remote}"
        )
        
        jobs = fetch_linkedin_jobs(
            keywords=request.keywords,
            location=request.location,
            limit=request.limit,
            remote=request.remote,
            throttle_seconds=0.5,
        )
        
        return [
            JobResponse(
                title=j.title,
                company=j.company,
                location=j.location,
                url=j.url,
                listed_at=j.listed_at,
            )
            for j in jobs
        ]
    except Exception as e:
        LOGGER.exception("Job search failed")
        raise HTTPException(status_code=500, detail=f"Job search failed: {str(e)}")


class KeywordsResponse(BaseModel):
    keywords: str
    has_cv: bool
    cv_filename: Optional[str] = None


class JobInitResponse(BaseModel):
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    keywords: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


async def process_cv_analysis(job_id: UUID, user_id: UUID, resume_id: UUID, session_factory):
    """Background task to process CV and extract keywords"""
    # Create new session for background task
    async for session in session_factory():
        try:
            # Update job status to processing
            result = await session.execute(
                select(JobAnalysisModel).where(JobAnalysisModel.id == job_id)
            )
            job = result.scalar_one_or_none()
            if not job:
                LOGGER.error(f"Job {job_id} not found")
                return
            
            job.status = JobStatus.PROCESSING
            await session.commit()
            
            # Check if this resume has already been analyzed before (cache hit)
            result = await session.execute(
                select(JobAnalysisModel)
                .where(JobAnalysisModel.user_id == user_id)
                .where(JobAnalysisModel.resume_id == resume_id)
                .where(JobAnalysisModel.status == JobStatus.COMPLETED)
                .where(JobAnalysisModel.keywords.is_not(None))
                .where(JobAnalysisModel.id != job_id)
                .order_by(JobAnalysisModel.completed_at.desc())
                .limit(1)
            )
            cached_job = result.scalar_one_or_none()

            if cached_job and cached_job.keywords:
                job.status = JobStatus.COMPLETED
                job.keywords = cached_job.keywords
                job.completed_at = datetime.utcnow()
                await session.commit()
                LOGGER.info(f"Job {job_id} completed from cache (resume_id={resume_id})")
                return

            # Get specific CV for this job
            result = await session.execute(
                select(ResumeModel)
                .where(ResumeModel.user_id == user_id)
                .where(ResumeModel.id == resume_id)
                .limit(1)
            )
            resume = result.scalar_one_or_none()
            
            if not resume:
                job.status = JobStatus.FAILED
                job.error_message = "No CV found"
                job.completed_at = datetime.utcnow()
                await session.commit()
                LOGGER.warning(f"No CV found for user {user_id} with resume_id {resume_id}")
                return
            
            # Download CV from S3
            LOGGER.info(f"Downloading CV for job {job_id}: {resume.storage_file_id}")
            resume_service = ResumeService(session)
            
            # Download file from S3
            file_content = await resume_service.download_file_from_s3(resume.storage_file_id)
            
            # Save to temporary file
            loop = asyncio.get_event_loop()
            def write_temp_file():
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                    temp_file.write(file_content)
                    return temp_file.name
            
            temp_path = await loop.run_in_executor(None, write_temp_file)
            
            try:
                # Extract text from PDF
                LOGGER.info(f"Extracting text from CV for job {job_id}")
                pdf_text = await extract_text_from_pdf(temp_path)
                
                if not pdf_text or len(pdf_text.strip()) < 50:
                    job.status = JobStatus.COMPLETED
                    job.keywords = "developer"
                    job.completed_at = datetime.utcnow()
                    await session.commit()
                    LOGGER.warning(f"CV text too short for job {job_id}")
                    return
                
                # Generate keywords using LLM
                LOGGER.info(f"Analyzing CV with LLM for job {job_id}")
                prompt = f"{extract_text_from_pdf.__doc__}\n\nResume text:\n{pdf_text}"
                resume_feature = await ask_llm_model(prompt)
                
                # Extract keywords
                if resume_feature.resume_keywords and len(resume_feature.resume_keywords) > 0:
                    keywords = ", ".join(resume_feature.resume_keywords[:5])
                elif resume_feature.resume_key_skills and len(resume_feature.resume_key_skills) > 0:
                    keywords = ", ".join(resume_feature.resume_key_skills[:5])
                else:
                    keywords = "developer"
                
                # Update job with results
                job.status = JobStatus.COMPLETED
                job.keywords = keywords
                job.completed_at = datetime.utcnow()
                await session.commit()
                
                LOGGER.info(f"Job {job_id} completed successfully with keywords: {keywords}")
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    await loop.run_in_executor(None, os.unlink, temp_path)
        
        except Exception as e:
            LOGGER.exception(f"Error processing job {job_id}")
            try:
                result = await session.execute(
                    select(JobAnalysisModel).where(JobAnalysisModel.id == job_id)
                )
                job = result.scalar_one_or_none()
                if job:
                    job.status = JobStatus.FAILED
                    job.error_message = str(e)
                    job.completed_at = datetime.utcnow()
                    await session.commit()
            except Exception as commit_error:
                LOGGER.exception(f"Failed to update job {job_id} status after error")
        
        break  # Exit after first iteration


@router.post("/jobs/keywords/analyze", response_model=JobInitResponse)
async def start_cv_analysis(
    background_tasks: BackgroundTasks,
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
    except Exception as e:
        LOGGER.exception("Failed to start CV analysis")
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {str(e)}")


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
            error_message=job.error_message,
            created_at=job.created_at.isoformat(),
            completed_at=job.completed_at.isoformat() if job.completed_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.exception("Failed to get job status")
        raise HTTPException(status_code=500, detail=str(e))


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
            )
        
        # Has CV but no analysis yet
        return KeywordsResponse(
            keywords="",
            has_cv=True,
            cv_filename=resume.original_filename,
        )
        
    except Exception as e:
        LOGGER.exception("Failed to check CV status")
        return KeywordsResponse(keywords="developer", has_cv=False)
