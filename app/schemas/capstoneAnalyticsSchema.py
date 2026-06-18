from pydantic import BaseModel, Field


class CapstoneSkillExtractionRequest(BaseModel):
    text: str = Field(..., min_length=1)
    source_section: str | None = None


class CapstoneSkillRead(BaseModel):
    skill_id: str
    normalized_name: str
    display_name: str
    category: str | None = None
    confidence_score: float | None = None
    evidence_text: str | None = None
    extraction_method: str | None = None


class CapstoneRequiredSkillRead(BaseModel):
    skill_id: str
    normalized_name: str
    display_name: str
    category: str | None = None
    importance_score: float | None = None
    evidence_text: str | None = None
    extraction_method: str | None = None


class CapstoneCourseSkillCoverageRead(BaseModel):
    skill_id: str
    normalized_name: str
    display_name: str
    coverage_score: float


class CapstoneRecommendedCourseRead(BaseModel):
    course_id: str
    title: str
    provider: str
    url: str | None = None
    cost: float | None = None
    currency: str | None = None
    duration_hours: float | None = None
    difficulty: str | None = None
    rating: float | None = None
    recommendation_score: float
    skills_covered: list[CapstoneCourseSkillCoverageRead]


class CapstoneGapAnalysisRead(BaseModel):
    status: str
    resume_id: str
    target_role: str
    coverage_ratio: float
    current_skills: list[CapstoneSkillRead]
    required_skills: list[CapstoneRequiredSkillRead]
    matched_required_skills: list[CapstoneRequiredSkillRead]
    missing_skills: list[CapstoneRequiredSkillRead]
    recommended_courses: list[CapstoneRecommendedCourseRead]


class CapstoneSkillExtractionRead(BaseModel):
    resume_id: str
    extracted_skills: list[CapstoneSkillRead]
