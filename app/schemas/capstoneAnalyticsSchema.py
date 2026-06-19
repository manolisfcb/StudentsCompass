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
    source_type: str | None = None


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
    requirements_source: str
    coverage_ratio: float
    current_skills: list[CapstoneSkillRead]
    required_skills: list[CapstoneRequiredSkillRead]
    matched_required_skills: list[CapstoneRequiredSkillRead]
    missing_skills: list[CapstoneRequiredSkillRead]
    recommended_courses: list[CapstoneRecommendedCourseRead]


class CapstoneSkillExtractionRead(BaseModel):
    resume_id: str
    extracted_skills: list[CapstoneSkillRead]


class CapstoneJobSkillExtractionRead(BaseModel):
    job_posting_id: str
    extracted_skills: list[CapstoneRequiredSkillRead]


class CapstoneJobSkillBatchExtractionRead(BaseModel):
    jobs_scanned: int
    jobs_with_matches: int
    job_skill_links: int


class CapstoneAnalyticsSeedSummaryRead(BaseModel):
    skills: int
    aliases: int
    courses: int
    course_skills: int
    role_skills: int


class CapstoneAnalyticsStatusRead(BaseModel):
    schema_ready: bool
    catalog_ready: bool
    skills_count: int
    aliases_count: int
    courses_count: int
    course_skills_count: int
    role_seed_requirements_count: int
    real_job_skill_links_count: int
    synced_job_postings_count: int
    supported_seed_roles: list[str]
    resume_embeddings_count: int
    embedding_provider: str
    embedding_model_name: str
    semantic_matching_ready: bool
    next_action: str | None = None


class CapstoneAnalyticsRoleRead(BaseModel):
    target_role: str
    requirement_source: str
    required_skills_count: int
    synced_job_postings_count: int
    is_market_backed: bool


class CapstoneAnalyticsRolesRead(BaseModel):
    roles: list[CapstoneAnalyticsRoleRead]
