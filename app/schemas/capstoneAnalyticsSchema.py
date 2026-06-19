from datetime import datetime
from uuid import UUID

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
    match_type: str | None = None
    matched_skill_id: str | None = None
    matched_skill_display_name: str | None = None
    similarity_score: float | None = None
    market_demand_count: int | None = None
    market_demand_score: float | None = None
    priority_score: float | None = None
    priority_rank: int | None = None
    reason: str | None = None


class CapstoneCourseSkillCoverageRead(BaseModel):
    skill_id: str
    normalized_name: str
    display_name: str
    coverage_score: float
    is_prerequisite: bool | None = None


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


class CapstoneGapInsightRead(BaseModel):
    insight_type: str
    severity: str
    message: str
    skill_id: str | None = None
    skill_name: str | None = None


class CapstoneMarketSkillSignalRead(BaseModel):
    skill_id: str
    normalized_name: str
    display_name: str
    job_posting_count: int
    demand_score: float


class CapstoneMarketSignalsRead(BaseModel):
    target_role: str
    source: str
    synced_job_postings_count: int
    skills: list[CapstoneMarketSkillSignalRead]


class CapstoneGapAnalysisRead(BaseModel):
    status: str
    resume_id: str
    target_role: str
    requirements_source: str
    coverage_ratio: float
    analysis_version: str
    match_score: float
    overall_readiness_score: float
    semantic_score: float
    context_similarity_score: float
    context_match_level: str
    semantic_context_ready: bool
    context_evidence_sources: list[str]
    exact_match_count: int
    semantic_match_count: int
    weak_match_count: int
    priority_gap_score: float
    current_skills: list[CapstoneSkillRead]
    required_skills: list[CapstoneRequiredSkillRead]
    matched_required_skills: list[CapstoneRequiredSkillRead]
    semantic_matched_skills: list[CapstoneRequiredSkillRead]
    weak_matched_skills: list[CapstoneRequiredSkillRead]
    missing_skills: list[CapstoneRequiredSkillRead]
    priority_missing_skills: list[CapstoneRequiredSkillRead]
    recommended_courses: list[CapstoneRecommendedCourseRead]
    gap_insights: list[CapstoneGapInsightRead]
    market_signals: CapstoneMarketSignalsRead


class CapstoneLearningRouteOptimizeRequest(BaseModel):
    resume_id: UUID
    target_role: str = Field(..., min_length=2, max_length=120)
    budget: float | None = Field(None, ge=0)
    available_hours: float | None = Field(None, ge=0)
    max_courses: int | None = Field(None, ge=1, le=20)


class CapstoneSelectedCourseRead(BaseModel):
    course_id: str
    title: str
    provider: str
    url: str | None = None
    cost: float | None = None
    currency: str | None = None
    duration_hours: float | None = None
    difficulty: str | None = None
    rating: float | None = None
    optimization_score: float
    sequence_order: int | None = None
    selection_reason: str | None = None
    covered_priority_skills: list[str] = Field(default_factory=list)
    skills_covered: list[CapstoneCourseSkillCoverageRead]


class CapstoneLearningRouteOptimizationRead(BaseModel):
    status: str
    optimization_run_id: str
    objective_version: str
    target_role: str
    match_score_before: float
    projected_match_score_after: float
    total_cost: float
    total_hours: float
    selected_courses: list[CapstoneSelectedCourseRead]
    covered_skills: list[CapstoneRequiredSkillRead]
    remaining_gaps: list[CapstoneRequiredSkillRead]
    route_summary: str


class CapstoneLearningRouteRunRead(BaseModel):
    optimization_run_id: str
    resume_id: str | None = None
    target_role: str
    objective_version: str
    status: str
    match_score_before: float | None = None
    projected_match_score_after: float | None = None
    total_cost: float | None = None
    total_hours: float | None = None
    budget: float | None = None
    available_hours: float | None = None
    max_courses: int | None = None
    selected_courses_count: int
    covered_skills_count: int
    remaining_gaps_count: int
    route_summary: str | None = None
    created_at: datetime


class CapstoneLearningRouteRunsRead(BaseModel):
    runs: list[CapstoneLearningRouteRunRead]


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
    local_embedding_provider_configured: bool
    local_embedding_package_available: bool
    embedding_fallback_provider: str
    embedding_model_cache_strategy: str
    embedding_local_failure_count: int
    embedding_fallback_to_hash_count: int
    embedding_production_recommendation: str
    next_action: str | None = None


class CapstoneAnalyticsRoleRead(BaseModel):
    target_role: str
    requirement_source: str
    required_skills_count: int
    synced_job_postings_count: int
    is_market_backed: bool


class CapstoneAnalyticsRolesRead(BaseModel):
    roles: list[CapstoneAnalyticsRoleRead]


class CapstoneCatalogMetadataCompletenessRead(BaseModel):
    overall: float
    url: float
    cost: float
    duration_hours: float
    difficulty: float
    rating: float


class CapstoneCatalogQualityRead(BaseModel):
    quality_version: str
    quality_score: float
    skills_count: int
    courses_count: int
    active_courses_count: int
    seed_role_count: int
    market_backed_role_count: int
    courses_with_skill_mapping: int
    mapped_course_ratio: float
    average_skills_per_course: float
    metadata_completeness: CapstoneCatalogMetadataCompletenessRead
    next_actions: list[str]
