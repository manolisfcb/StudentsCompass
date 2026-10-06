"""Career Lab job targets: what the API accepts and answers (plan 11, C1).

The analysis is typed down to its leaves rather than published as a free-form
object: the React client generates its types from the OpenAPI contract, and
the score must always reach it together with its band and breakdown (plan 11
§4.1), which a loose ``dict`` would not guarantee.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app import config
from app.schemas.paginationSchema import CursorPage

JobTargetStatus = Literal["pending", "parsing", "ready", "failed"]
WorkplaceType = Literal["onsite", "hybrid", "remote"]
MatchBand = Literal["strong_match", "match", "weak_match"]
Requirement = Literal["required", "preferred"]
SeniorityLevel = Literal["intern", "junior", "mid", "senior", "lead"]


class JobTargetCreate(BaseModel):
    """A job description the user pasted, and the CV to read it against."""

    text: str
    resume_id: UUID

    @field_validator("text")
    @classmethod
    def _bounded(cls, value: str) -> str:
        length = len(value.strip())
        if length < config.JOB_TEXT_MIN_CHARS:
            raise ValueError(
                f"Paste the full job description (at least {config.JOB_TEXT_MIN_CHARS} characters)."
            )
        if length > config.JOB_TEXT_MAX_CHARS:
            raise ValueError(
                f"The job description is too long (at most {config.JOB_TEXT_MAX_CHARS} characters)."
            )
        return value


class MatchComponentRead(BaseModel):
    #: 0–1, or null when the component had no signal (see ``available``).
    value: float | None
    available: bool
    #: The configured weight.
    weight: float
    #: The weight it actually carried once unavailable components were spread.
    effective_weight: float


class MatchComponentsRead(BaseModel):
    skills: MatchComponentRead
    context: MatchComponentRead
    title: MatchComponentRead
    seniority: MatchComponentRead


class MatchGateRead(BaseModel):
    value: float
    reason: str


class MatchContextRead(BaseModel):
    value: float | None
    level: Literal["strong", "moderate", "weak", "unavailable"]
    message: str | None = None


class MatchSeniorityRead(BaseModel):
    asked: SeniorityLevel | None = None
    cv: SeniorityLevel | None = None
    min_years: int | None = None


class MatchRequirementsRead(BaseModel):
    #: 0–1: how much of its weight the skills component carried, given how
    #: many catalogue requirements the posting yielded.
    evidence: float
    required: int
    preferred: int
    required_covered: int


class MatchStrengthRead(BaseModel):
    skill_id: str
    display_name: str
    requirement: Requirement | None = None
    match_type: Literal["exact", "semantic"]
    #: For a semantic match, the CV skill that stands in for the requirement.
    matched_with: str | None = None
    similarity: float | None = None


class MatchGapRead(BaseModel):
    skill_id: str
    display_name: str
    requirement: Requirement | None = None
    #: ``gap``: nothing in the CV covers it. ``reinforce``: a related skill
    #: does, partially — ``closest_skill`` names it.
    kind: Literal["gap", "reinforce"]
    closest_skill: str | None = None
    similarity: float | None = None
    priority_rank: int
    skill_gap_score: float
    reason: str


class JobMatchAnalysisRead(BaseModel):
    analysis_version: str
    computed_at: datetime
    resume_id: UUID
    #: Never shown without ``band`` and ``components``. Null when no component
    #: had a signal to score on.
    score: float | None
    band: MatchBand | None
    gate: MatchGateRead
    components: MatchComponentsRead
    context: MatchContextRead
    seniority: MatchSeniorityRead
    title: str | None = None
    workplace_type: WorkplaceType | None = None
    requirements: MatchRequirementsRead
    strengths: list[MatchStrengthRead]
    gaps: list[MatchGapRead]
    semantic_matching_ready: bool
    parse_version: str


class JobTargetSummaryRead(BaseModel):
    """A row of the user's list: no pasted text, the headline numbers only."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    resume_id: UUID | None
    status: JobTargetStatus
    source: str
    title: str | None
    company: str | None
    location: str | None
    workplace_type: WorkplaceType | None
    score: float | None = None
    band: MatchBand | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, target) -> "JobTargetSummaryRead":
        snapshot = target.match_snapshot or {}
        summary = cls.model_validate(target)
        summary.score = snapshot.get("score")
        summary.band = snapshot.get("band")
        return summary


class JobTargetRead(JobTargetSummaryRead):
    raw_text: str
    error_message: str | None
    analysis: JobMatchAnalysisRead | None = None

    @classmethod
    def from_model(cls, target) -> "JobTargetRead":
        read = cls.model_validate(target)
        snapshot = target.match_snapshot
        if snapshot:
            read.score = snapshot.get("score")
            read.band = snapshot.get("band")
            read.analysis = JobMatchAnalysisRead.model_validate(snapshot)
        return read


class JobTargetPageRead(CursorPage[JobTargetSummaryRead]):
    """One bounded page of the user's job targets, newest first."""
