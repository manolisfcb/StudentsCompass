from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ResumeAuditCategoryScores(BaseModel):
    ats: float = Field(ge=0, le=10)
    canadian_format: float = Field(ge=0, le=10)
    keywords: float = Field(ge=0, le=10)
    achievements: float = Field(ge=0, le=10)
    readability: float = Field(ge=0, le=10)
    ai_risk: float = Field(ge=0, le=10)
    differentiation: float = Field(ge=0, le=10)
    formatting: float = Field(ge=0, le=10)


class ResumeAuditResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    overall_score: float = Field(ge=0, le=10)
    pass_status: bool = Field(alias="pass")
    llm_confidence: float = Field(ge=0, le=1)
    scores: ResumeAuditCategoryScores
    reason_for_score: str = ""
    main_weaknesses: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    prompt_injection_signals_detected: list[str] = Field(default_factory=list)


def format_resume_audit_report(result: ResumeAuditResult) -> str:
    status_line = "PASS (>=8)" if result.pass_status else "FAIL (<8)"
    categories = result.scores

    lines = [
        f"OVERALL ATS SCORE: {result.overall_score:.1f}/10",
        "",
        "PASS STATUS:",
        status_line,
        "",
        "LLM CONFIDENCE:",
        f"{result.llm_confidence:.2f}",
        "",
        "CATEGORY SCORES",
        "",
        f"ATS Compatibility: {categories.ats:.1f}/10",
        f"Canadian Resume Format: {categories.canadian_format:.1f}/10",
        f"Keyword Optimization: {categories.keywords:.1f}/10",
        f"Achievement Quality: {categories.achievements:.1f}/10",
        f"Recruiter Readability: {categories.readability:.1f}/10",
        f"AI Detection Risk: {categories.ai_risk:.1f}/10",
        f"Impact & Differentiation: {categories.differentiation:.1f}/10",
        f"Structure & Formatting: {categories.formatting:.1f}/10",
        "",
        "WHY THIS SCORE",
        result.reason_for_score.strip() or "No detailed explanation provided.",
        "",
        "MAIN WEAKNESSES",
        *([f"- {item}" for item in result.main_weaknesses] or ["- None listed"]),
        "",
        "IMPROVEMENT ACTIONS",
        *([f"- {item}" for item in result.improvements] or ["- None listed"]),
    ]
    return "\n".join(lines)
