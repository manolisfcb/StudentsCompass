from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.JobsScraper.linkedin_scraper import fetch_linkedin_jobs
from app.core.observability import external_call
from app.core.offload import BoundedOffload, OffloadRejected
from app.models.jobPostingModel import JobPosting
from app.services.jobs.jobPostingService import JobPostingService

LOGGER = logging.getLogger(__name__)

#: Threads that may be scraping at once. The provider is a third-party site
#: being paged politely; more parallelism there is not a win worth the memory.
SCRAPER_MAX_WORKERS = 4
#: Searches that may be *waiting* for one of those threads. Past this the
#: provider is shed rather than queued: a request that waits behind fifty others
#: has already failed the user, and an unbounded queue is how a slow provider
#: turns into an out-of-memory.
SCRAPER_MAX_QUEUED = 16
#: What the caller waits for the provider. The internal results are already in
#: hand by then, so timing out costs the LinkedIn half, not the response.
SCRAPER_TIMEOUT_SECONDS = 12.0
#: What the scraper itself may spend walking pages. Below the caller's timeout
#: so a worker is normally released by its own budget rather than abandoned
#: mid-walk with the caller already gone.
SCRAPER_BUDGET_SECONDS = 10.0


#: One pool for the process. Module level so the threads are reused across
#: requests instead of a new pool per search.
LINKEDIN_OFFLOAD = BoundedOffload(
    max_workers=SCRAPER_MAX_WORKERS,
    max_queued=SCRAPER_MAX_QUEUED,
    thread_name_prefix="linkedin-scraper",
)


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
            limit,
            query.remote,
        )
        linkedin_jobs = await self._fetch_provider_jobs(query, limit)

        return {
            "students_compass": [serialize_internal_job(job) for job in internal_jobs],
            "linkedin": [serialize_linkedin_job(job) for job in linkedin_jobs],
        }

    async def _fetch_provider_jobs(self, query: JobSearchQuery, limit: int) -> list:
        """The LinkedIn half of the search, off the event loop and degradable.

        The scraper is ``requests.get`` and ``time.sleep`` in a paging loop, so
        awaiting it directly parked the whole worker: one search against a slow
        provider stalled every other request sharing that process. It now runs
        in a bounded pool, and every way it can fail — full queue, timeout, or
        the provider itself erroring — returns an empty LinkedIn list rather
        than failing the search. The Students Compass results are already in
        hand and are what the user actually came for.
        """

        def work():
            # Looked up here, not captured at import, so the module-level name
            # stays the patch point the tests use.
            return fetch_linkedin_jobs(
                keywords=query.keywords,
                location=query.location,
                # The normalised limit, not the raw one: the provider used to
                # receive whatever the caller asked for while the internal
                # search was capped at 100.
                limit=limit,
                remote=query.remote,
                throttle_seconds=0.5,
                budget_seconds=SCRAPER_BUDGET_SECONDS,
            )

        try:
            # The provider boundary is the whole offloaded call, including the
            # time spent waiting for a worker: that wait is part of what the
            # user experiences.
            with external_call("linkedin"):
                return await LINKEDIN_OFFLOAD.run(work, timeout=SCRAPER_TIMEOUT_SECONDS)
        except OffloadRejected as exc:
            LOGGER.warning("LinkedIn search shed, provider queue full: %s", exc)
            return []
        except asyncio.TimeoutError:
            LOGGER.warning(
                "LinkedIn search timed out after %ss; returning internal results only",
                SCRAPER_TIMEOUT_SECONDS,
            )
            return []
        except Exception:  # noqa: BLE001 — a third-party site must not fail the search
            LOGGER.exception("LinkedIn search failed; returning internal results only")
            return []
