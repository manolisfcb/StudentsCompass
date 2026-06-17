"""Backward-compatible import path for the LinkedIn jobs scraper."""

from app.core.JobsScraper.linkedin_scraper import JobPosting, fetch_linkedin_jobs

__all__ = ["JobPosting", "fetch_linkedin_jobs"]
