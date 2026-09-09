"""The text of a job posting, as one string.

A module function rather than a method because two unrelated things need it: the
job-skill extraction, which reads a posting to find skills, and the gap
analysis, which reads recent postings to build the context a role is compared
against. Split out by TASK-023 so neither had to import the other.
"""
from __future__ import annotations

from app.models.jobPostingModel import JobPosting


def job_posting_text(job_posting: JobPosting) -> str:
    fields = [
        job_posting.title,
        job_posting.description,
        job_posting.requirements,
        job_posting.responsibilities,
        job_posting.benefits,
        job_posting.listed_context,
        job_posting.source_context,
    ]
    return "\n".join(field for field in fields if field)
