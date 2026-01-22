from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.JobsScraper.scrapper_propio import fetch_linkedin_jobs
from app.db import get_session
from app.services.userService import current_active_user
from app.models.userModel import User
from app.models.resumeModel import ResumeModel
from sqlalchemy import select
import logging
from app.core.ResumeAnalizer.read_pdf_data import extract_text_from_pdf
from app.core.ResumeAnalizer.llm_model import ask_llm_model
from app.services.resumeService import ResumeService
import io
import tempfile
import os

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


@router.get("/jobs/keywords", response_model=KeywordsResponse)
async def get_job_keywords(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    """Extract keywords from user's CV using LLM analysis"""
    try:
        # Try to get user's latest CV
        result = await session.execute(
            select(ResumeModel)
            .where(ResumeModel.user_id == user.id)
            .order_by(ResumeModel.created_at.desc())
            .limit(1)
        )
        resume = result.scalar_one_or_none()
        
        if not resume:
            # No CV found - fallback to user name
            LOGGER.warning(f"No CV found for user {user.id}")
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
        
        # Download CV from Google Drive using export link
        LOGGER.info(f"Downloading CV for user {user.id}: {resume.storage_file_id}")
        resume_service = ResumeService(session)
        drive_service = await resume_service.get_drive_service()
        
        # Get file metadata and download using direct API call
        request_obj = drive_service.files().get_media(fileId=resume.storage_file_id)
        file_content = request_obj.execute()
        
        # Save to temporary file for PyMuPDF processing
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(file_content)
            temp_path = temp_file.name
        
        try:
            # Extract text from PDF
            LOGGER.info(f"Extracting text from CV: {resume.original_filename}")
            pdf_text = extract_text_from_pdf(temp_path)
            
            if not pdf_text or len(pdf_text.strip()) < 50:
                LOGGER.warning(f"CV text too short for user {user.id}")
                return KeywordsResponse(
                    keywords="developer",
                    has_cv=True,
                    cv_filename=resume.original_filename,
                )
            
            # Generate ResumeFeature using LLM
            LOGGER.info(f"Analyzing CV with LLM for user {user.id}")
            prompt = f"{extract_text_from_pdf.__doc__}\n\nResume text:\n{pdf_text}"
            resume_feature = ask_llm_model(prompt)
            
            # Extract keywords from ResumeFeature - join list of keywords
            if resume_feature.resume_keywords and len(resume_feature.resume_keywords) > 0:
                keywords = ", ".join(resume_feature.resume_keywords[:5])  # Top 5 keywords
            elif resume_feature.resume_key_skills and len(resume_feature.resume_key_skills) > 0:
                keywords = ", ".join(resume_feature.resume_key_skills[:5])  # Fallback to skills
            else:
                keywords = "developer"
            
            LOGGER.info(f"Extracted keywords for user {user.id}: {keywords}")
            return KeywordsResponse(
                keywords=keywords,
                has_cv=True,
                cv_filename=resume.original_filename,
            )
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        
    except Exception as e:
        LOGGER.exception("Failed to extract keywords from CV")
        return KeywordsResponse(keywords="developer", has_cv=False)
