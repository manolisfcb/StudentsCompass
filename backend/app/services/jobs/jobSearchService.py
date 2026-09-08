from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.JobsScraper.linkedin_scraper import fetch_linkedin_jobs
from app.models.jobPostingModel import JobPosting
from app.services.jobs.jobPostingService import JobPostingService

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobSearchQuery:
    keywords: str
    location: str
    limit: int
    remote: bool = False


def serialize_internal_job(job: JobPosting) -> dict:
    company = job.company
    return {
        "id": str(job.id),
        "company_id": str(job.company_id),
        "title": job.title,
        "company": company.company_name if company else "Students Compass Company",
        "location": job.location or (company.location if company else "") or "Location not specified",
        "url": job.application_url,
        "listed_at": job.created_at.isoformat() if job.created_at else None,
        "description": job.description,
        "requirements": job.requirements,
        "responsibilities": job.responsibilities,
        "job_type": job.job_type,
        "workplace_type": job.workplace_type,
        "seniority_level": job.seniority_level,
        "salary_range": job.salary_range,
        "benefits": job.benefits,
        "listed_context": job.listed_context,
        "source_context": job.source_context,
        "company_description": company.description if company else None,
        "company_website": company.website if company else None,
        "company_location": company.location if company else None,
        "source": "students_compass",
        "source_label": "Students Compass",
    }


def serialize_linkedin_job(job) -> dict:
    return {
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "url": job.url,
        "listed_at": job.listed_at,
        "company_location": job.location,
        "source": "linkedin",
        "source_label": "LinkedIn",
    }


class JobSearchService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.job_posting_service = JobPostingService(session)

    async def search(self, query: JobSearchQuery) -> dict:
        limit = max(1, min(query.limit, 100))
        internal_jobs = await self.job_posting_service.list_public_job_postings(
            keywords=query.keywords,
            location=query.location,
            limit=limit,
        )

        LOGGER.debug(
            "Searching LinkedIn after Students Compass lookup: keywords=%s, location=%s, limit=%s, remote=%s",
            query.keywords,
            query.location,
            query.limit,
            query.remote,
        )
        linkedin_jobs = fetch_linkedin_jobs(
            keywords=query.keywords,
            location=query.location,
            limit=query.limit,
            remote=query.remote,
            throttle_seconds=0.5,
        )

        return {
            "students_compass": [serialize_internal_job(job) for job in internal_jobs],
            "linkedin": [serialize_linkedin_job(job) for job in linkedin_jobs],
        }
