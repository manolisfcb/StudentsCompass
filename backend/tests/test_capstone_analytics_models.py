import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from app.models.resumeModel import ResumeModel
from app.models.resumeEmbeddingsModel import ResumeEmbedding
from app.models.jobPostingModel import JobPosting
from app.models.userModel import User
from app.routes.capstoneAnalyticsRoute import _run_capstone_operation
from app.models.skillModel import (
    CourseModel,
    CourseSkillModel,
    JobSkillModel,
    OptimizationRunModel,
    ResumeSkillModel,
    SkillAliasModel,
    SkillModel,
)
from app.services.analytics.capstoneAnalyticsService import CapstoneAnalyticsService
from app.services.analytics.capstoneAnalyticsSeedService import (
    CAPSTONE_SKILL_SEED_DATA,
    seed_capstone_analytics_minimum,
)
from app.services.analytics.learningRouteOptimizerService import (
    OBJECTIVE_VERSION_CP_SAT,
    OBJECTIVE_VERSION_HEURISTIC,
    LearningRouteConstraints,
    ORToolsLearningRouteOptimizer,
)
from app.services.analytics.learningRouteBaselineEvaluationService import (
    LearningRouteBaselineEvaluationService,
    PHASE_7_EVALUATION_VERSION,
)
from app.services.analytics.resumeSkillDatasetEvaluator import summarize_resume_skill_dataset
from app.services.analytics.semanticMatchingService import SemanticMatchingService
from app.services.analytics.skillGapScoringService import SkillGapScoringService
from app.services.analytics.skillExtractionService import SkillExtractionService
from app.services.analytics.skillNormalizer import SkillNormalizer


@pytest.mark.asyncio
async def test_capstone_operation_translates_missing_analytics_schema_error():
    async def operation():
        raise ProgrammingError(
            statement="select * from skills",
            params={},
            orig=Exception('relation "skills" does not exist'),
        )

    with pytest.raises(HTTPException) as exc_info:
        await _run_capstone_operation(operation)

    assert exc_info.value.status_code == 503
    assert "Career analytics schema is not ready" in exc_info.value.detail


@pytest.mark.asyncio
async def test_capstone_seed_creates_minimum_skill_course_catalog(db_session):
    summary = await seed_capstone_analytics_minimum(db_session)

    assert summary["skills"] == len(CAPSTONE_SKILL_SEED_DATA)
    assert summary["courses"] == 12
    assert summary["course_skills"] > 0
    assert summary["role_skills"] == 28

    second_summary = await seed_capstone_analytics_minimum(db_session)

    assert second_summary == {
        "skills": 0,
        "aliases": 0,
        "courses": 0,
        "course_skills": 0,
        "role_skills": 0,
    }


@pytest.mark.asyncio
async def test_capstone_analytics_status_reports_catalog_readiness(client, db_session, auth_headers):
    empty_response = await client.get("/api/v1/capstone/analytics/status", headers=auth_headers)

    assert empty_response.status_code == 200
    empty_payload = empty_response.json()
    assert empty_payload["schema_ready"] is True
    assert empty_payload["catalog_ready"] is False
    assert empty_payload["next_action"]

    await seed_capstone_analytics_minimum(db_session)

    ready_response = await client.get("/api/v1/capstone/analytics/status", headers=auth_headers)

    assert ready_response.status_code == 200
    ready_payload = ready_response.json()
    assert ready_payload["catalog_ready"] is True
    assert ready_payload["skills_count"] == len(CAPSTONE_SKILL_SEED_DATA)
    assert ready_payload["resume_skills_count"] == 0
    assert ready_payload["confirmed_resume_skills_count"] == 0
    assert ready_payload["courses_count"] == 12
    assert ready_payload["resume_embeddings_count"] == 0
    assert ready_payload["embedding_provider"] == "hash"
    assert ready_payload["embedding_model_name"]
    assert ready_payload["semantic_matching_ready"] is False
    assert ready_payload["local_embedding_provider_configured"] is False
    assert ready_payload["embedding_fallback_provider"] == "hash"
    assert ready_payload["embedding_model_cache_strategy"]
    assert ready_payload["embedding_production_recommendation"]
    assert "Data Analyst" in ready_payload["supported_seed_roles"]


@pytest.mark.asyncio
async def test_capstone_catalog_quality_reports_product_readiness_gaps(client, db_session, auth_headers):
    await seed_capstone_analytics_minimum(db_session)

    response = await client.get("/api/v1/capstone/catalog/quality", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["quality_version"] == "catalog_quality_v1"
    assert 0 < payload["quality_score"] < 1
    assert payload["skills_count"] == len(CAPSTONE_SKILL_SEED_DATA)
    assert payload["courses_count"] == 12
    assert payload["mapped_course_ratio"] == 1
    assert payload["metadata_completeness"]["overall"] == 1
    assert payload["next_actions"]
    assert any("Curate at least 40 active learning resources" in action for action in payload["next_actions"])


@pytest.mark.asyncio
async def test_capstone_roles_endpoint_reports_seed_and_market_backed_roles(
    client,
    db_session,
    test_company,
    auth_headers,
):
    await seed_capstone_analytics_minimum(db_session)

    seed_response = await client.get("/api/v1/capstone/analytics/roles", headers=auth_headers)

    assert seed_response.status_code == 200
    seed_roles = {role["target_role"]: role for role in seed_response.json()["roles"]}
    assert seed_roles["Data Analyst"]["requirement_source"] == "role_seed"
    assert seed_roles["Data Analyst"]["is_market_backed"] is False
    assert seed_roles["Data Analyst"]["required_skills_count"] > 0

    job = JobPosting(
        company_id=test_company.id,
        title="Data Analyst",
        requirements="Must have SQL and Tableau experience.",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    service = CapstoneAnalyticsService(db_session)
    await service.extract_job_skills_from_job_posting(job_posting_id=job.id)

    market_response = await client.get("/api/v1/capstone/analytics/roles", headers=auth_headers)

    assert market_response.status_code == 200
    market_roles = {role["target_role"]: role for role in market_response.json()["roles"]}
    assert market_roles["Data Analyst"]["requirement_source"] == "job_postings"
    assert market_roles["Data Analyst"]["is_market_backed"] is True
    assert market_roles["Data Analyst"]["required_skills_count"] == 2
    assert market_roles["Data Analyst"]["synced_job_postings_count"] == 1


@pytest.mark.asyncio
async def test_capstone_seed_endpoint_is_admin_only(client, db_session, test_user, auth_headers):
    forbidden_response = await client.post("/api/v1/capstone/analytics/seed", headers=auth_headers)

    assert forbidden_response.status_code == 403

    test_user.is_superuser = True
    db_session.add(test_user)
    await db_session.commit()

    seed_response = await client.post("/api/v1/capstone/analytics/seed", headers=auth_headers)

    assert seed_response.status_code == 200
    payload = seed_response.json()
    assert payload["skills"] == len(CAPSTONE_SKILL_SEED_DATA)
    assert payload["courses"] == 12
    assert payload["role_skills"] == 28


@pytest.mark.asyncio
async def test_capstone_open_job_skill_sync_is_admin_only(
    client,
    db_session,
    test_user,
    test_company,
    auth_headers,
):
    await seed_capstone_analytics_minimum(db_session)
    job = JobPosting(
        company_id=test_company.id,
        title="Data Analyst",
        requirements="Strong SQL, Python, Excel, and communication skills.",
    )
    db_session.add(job)
    await db_session.commit()

    forbidden_response = await client.post(
        "/api/v1/capstone/job-postings/skills/sync-open",
        headers=auth_headers,
    )

    assert forbidden_response.status_code == 403

    test_user.is_superuser = True
    db_session.add(test_user)
    await db_session.commit()

    sync_response = await client.post(
        "/api/v1/capstone/job-postings/skills/sync-open",
        headers=auth_headers,
        params={"limit": 10},
    )

    assert sync_response.status_code == 200
    payload = sync_response.json()
    assert payload["jobs_scanned"] == 1
    assert payload["jobs_with_matches"] == 1
    assert payload["job_skill_links"] >= 4


@pytest.mark.asyncio
async def test_capstone_analytics_models_link_resume_skills_courses_and_runs(db_session, test_user):
    skill = SkillModel(
        normalized_name="python",
        display_name="Python",
        category="programming",
        source="test",
    )
    alias = SkillAliasModel(skill=skill, alias="python programming", source="test")
    course = CourseModel(
        title="Python for Data Analysis",
        provider="StudentsCompass",
        cost=0,
        duration_hours=8,
        difficulty="beginner",
    )
    course_skill = CourseSkillModel(course=course, skill=skill, coverage_score=0.9)
    resume = ResumeModel(
        view_url="https://storage.example/resume.pdf",
        user_id=test_user.id,
        storage_file_id="resumes/test.pdf",
        original_filename="resume.pdf",
        folder_id="resumes",
    )
    db_session.add_all([skill, alias, course, course_skill, resume])
    await db_session.flush()

    resume_skill = ResumeSkillModel(
        resume_id=resume.id,
        user_id=test_user.id,
        skill_id=skill.id,
        confidence_score=0.88,
        extraction_method="test",
        evidence_text="Built Python dashboards.",
    )
    optimization_run = OptimizationRunModel(
        user_id=test_user.id,
        resume_id=resume.id,
        target_role="Data Analyst",
        budget=100,
        available_hours=20,
        max_courses=3,
        skill_coverage={"python": 1.0},
        constraints={"currency": "CAD"},
    )
    db_session.add_all([resume_skill, optimization_run])
    await db_session.commit()

    assert skill.aliases[0].alias == "python programming"
    assert course.skills[0].skill.display_name == "Python"
    assert resume_skill.skill.normalized_name == "python"
    assert optimization_run.target_role == "Data Analyst"


@pytest.mark.asyncio
async def test_skill_normalizer_builds_alias_lookup_and_preserves_symbol_skills(db_session):
    await seed_capstone_analytics_minimum(db_session)
    csharp = SkillModel(
        normalized_name="c#",
        display_name="C#",
        category="programming",
        source="test",
    )
    cpp = SkillModel(
        normalized_name="c++",
        display_name="C++",
        category="programming",
        source="test",
    )
    db_session.add_all([csharp, cpp])
    await db_session.commit()

    lookup = await SkillNormalizer.build_lookup(db_session)

    assert SkillNormalizer.normalize_text("Python, SQL & Tableau") == "python sql tableau"
    assert SkillNormalizer.normalize_canonical_name("Scikit Learn") == "scikit_learn"
    assert lookup["powerbi"].display_name == "Power BI"
    assert lookup["c#"].display_name == "C#"
    assert lookup["c++"].display_name == "C++"


@pytest.mark.asyncio
async def test_skill_extraction_service_deduplicates_prefers_long_aliases_and_avoids_substrings(db_session):
    await seed_capstone_analytics_minimum(db_session)
    service = SkillExtractionService(db_session)

    matches = await service.extract_known_skills_from_text(
        "Built PowerBI dashboards with python programming. NoSQL migration only.",
        extraction_method="unit_rules_v1",
        source_section="summary",
    )
    by_name = {match.skill.normalized_name: match for match in matches}

    assert {"power_bi", "python"}.issubset(by_name)
    assert "sql" not in by_name
    assert by_name["power_bi"].matched_text == "powerbi"
    assert by_name["python"].matched_text == "python programming"
    assert by_name["python"].confidence_score == 0.75
    assert by_name["python"].evidence_text == "python programming"
    assert by_name["python"].source_section == "summary"
    assert by_name["python"].extraction_method == "unit_rules_v1"


@pytest.mark.asyncio
async def test_skill_extraction_service_returns_empty_list_for_empty_catalog(db_session):
    service = SkillExtractionService(db_session)

    matches = await service.extract_known_skills_from_text("Python and SQL")

    assert matches == []


@pytest.mark.asyncio
async def test_phase_4_manual_skill_extraction_sample_meets_baseline_quality(db_session):
    await seed_capstone_analytics_minimum(db_session)
    service = SkillExtractionService(db_session)
    samples = [
        {
            "text": "Resume: Python, SQL, pandas, and Tableau dashboards for stakeholder reporting.",
            "expected": {"python", "sql", "pandas", "tableau", "stakeholder_management"},
        },
        {
            "text": "Job: PowerBI, Excel, KPI design, data wrangling, and presentation skills required.",
            "expected": {"power_bi", "excel", "kpi_design", "data_cleaning", "communication"},
        },
        {
            "text": "Resume: Agile business analyst with requirements elicitation and noSQL migration exposure.",
            "expected": {"agile", "business_analysis", "requirements_gathering", "nosql"},
        },
    ]

    true_positive = 0
    false_positive = 0
    false_negative = 0
    for sample in samples:
        matches = await service.extract_known_skills_from_text(sample["text"])
        extracted = {match.skill.normalized_name for match in matches}
        expected = sample["expected"]
        true_positive += len(extracted & expected)
        false_positive += len(extracted - expected)
        false_negative += len(expected - extracted)

    precision = true_positive / (true_positive + false_positive)
    recall = true_positive / (true_positive + false_negative)

    assert precision >= 0.9
    assert recall >= 0.75
    assert false_positive == 0


@pytest.mark.asyncio
async def test_resume_skill_dataset_evaluator_returns_aggregate_counts_without_text(db_session, tmp_path):
    await seed_capstone_analytics_minimum(db_session)
    csv_path = tmp_path / "resume_sample.csv"
    csv_path.write_text(
        "ID,Resume_str,Category\n"
        '1,"Built Python dashboards with SQL and Tableau.",INFORMATION-TECHNOLOGY\n'
        '2,"Managed recruiting, onboarding, and employee relations.",HR\n',
        encoding="utf-8",
    )

    summary = await summarize_resume_skill_dataset(
        csv_path=csv_path,
        extraction_service=SkillExtractionService(db_session),
    )

    assert summary["resumes_scanned"] == 2
    assert summary["resumes_with_skills"] == 2
    assert summary["coverage_ratio"] == 1
    assert "Resume_str" not in str(summary)
    top_names = {row["normalized_name"] for row in summary["top_skills"]}
    assert {"python", "sql", "tableau", "recruiting", "onboarding", "employee_relations"}.issubset(top_names)


@pytest.mark.asyncio
async def test_capstone_gap_analysis_returns_missing_skills_and_recommended_courses(db_session, test_user):
    await seed_capstone_analytics_minimum(db_session)
    resume = ResumeModel(
        view_url="https://storage.example/resume.pdf",
        user_id=test_user.id,
        storage_file_id="resumes/test.pdf",
        original_filename="resume.pdf",
        folder_id="resumes",
        ai_summary="Built Python dashboards with SQL queries and clear stakeholder communication.",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    service = CapstoneAnalyticsService(db_session)
    payload = await service.analyze_gap(
        resume_id=resume.id,
        user_id=test_user.id,
        target_role="Data Analyst",
    )

    current_skill_names = {skill["normalized_name"] for skill in payload["current_skills"]}
    missing_skill_names = {skill["normalized_name"] for skill in payload["missing_skills"]}

    assert payload["status"] == "ok"
    assert {"python", "sql", "communication"}.issubset(current_skill_names)
    assert "excel" in missing_skill_names
    assert payload["coverage_ratio"] > 0
    assert payload["overall_readiness_score"] == payload["match_score"]
    assert payload["context_similarity_score"] == 0
    assert payload["context_match_level"] == "fallback_disabled"
    assert payload["semantic_context_ready"] is False
    assert "role_required_skills" in payload["context_evidence_sources"]
    assert payload["recommended_courses"]
    assert payload["priority_missing_skills"]
    assert payload["priority_missing_skills"][0]["priority_rank"] == 1
    assert payload["priority_missing_skills"][0]["required_skill_weight"] > 0
    assert payload["priority_missing_skills"][0]["student_skill_evidence"] >= 0
    assert payload["priority_missing_skills"][0]["skill_gap_score"] == payload["priority_missing_skills"][0]["priority_score"]
    assert payload["gap_insights"]
    assert payload["market_signals"]["source"] == "role_seed"
    assert any(
        covered_skill["normalized_name"] == "excel"
        for course in payload["recommended_courses"]
        for covered_skill in course["skills_covered"]
    )

    embedding = await db_session.scalar(
        select(ResumeEmbedding).where(ResumeEmbedding.resume_id == resume.id)
    )
    assert embedding is not None
    assert embedding.dims == 384
    assert len(embedding.embedding) == 384


@pytest.mark.asyncio
async def test_semantic_matching_separates_exact_and_semantic_matches(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "local")

    vectors = {
        "python python programming": [1.0, 0.0],
        "data visualization data_visualization analytics": [0.0, 1.0],
        "tableau tableau analytics": [0.0, 0.96],
    }

    async def fake_embedding(text: str):
        return vectors[text.lower()]

    service = SemanticMatchingService(embedding_fn=fake_embedding, semantic_ready_override=True)
    summary = await service.analyze_required_skill_matches(
        current_skills=[
            {
                "skill_id": "python-id",
                "normalized_name": "python",
                "display_name": "Python",
                "category": "programming",
                "confidence_score": 0.9,
            },
            {
                "skill_id": "tableau-id",
                "normalized_name": "tableau",
                "display_name": "Tableau",
                "category": "analytics",
                "confidence_score": 0.85,
            },
        ],
        required_skills=[
            {
                "skill_id": "python-id",
                "normalized_name": "python",
                "display_name": "Python",
                "category": "programming",
                "importance_score": 0.9,
            },
            {
                "skill_id": "data-viz-id",
                "normalized_name": "data_visualization",
                "display_name": "Data Visualization",
                "category": "analytics",
                "importance_score": 0.8,
            },
        ],
    )

    assert summary.analysis_version == "semantic_gap_v1"
    assert summary.exact_match_count == 1
    assert summary.semantic_match_count == 1
    assert summary.missing_skills == []
    assert summary.semantic_matched_skills[0]["matched_skill_display_name"] == "Tableau"
    assert summary.match_score > 0.8


def test_skill_gap_scoring_prioritizes_required_weight_minus_student_evidence():
    prioritized = SkillGapScoringService.prioritize_missing_skills(
        [
            {
                "skill_id": "sql-id",
                "normalized_name": "sql",
                "display_name": "SQL",
                "importance_score": 0.8,
                "market_demand_score": 1.0,
                "market_demand_count": 4,
                "match_type": "weak",
                "similarity_score": 0.5,
            },
            {
                "skill_id": "excel-id",
                "normalized_name": "excel",
                "display_name": "Excel",
                "importance_score": 0.95,
                "market_demand_score": 0.0,
                "market_demand_count": 0,
            },
        ]
    )

    by_name = {skill["normalized_name"]: skill for skill in prioritized}

    assert by_name["sql"]["required_skill_weight"] == 1.08
    assert by_name["sql"]["student_skill_evidence"] == 0.175
    assert by_name["sql"]["skill_gap_score"] == 0.891
    assert by_name["sql"]["priority_score"] == by_name["sql"]["skill_gap_score"]
    assert prioritized[0]["normalized_name"] == "excel"
    assert prioritized[0]["priority_rank"] == 1


@pytest.mark.asyncio
async def test_semantic_context_similarity_uses_full_resume_and_role_text(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "local")

    async def fake_embedding(text: str):
        if "dashboards" in text.lower():
            return [1.0, 0.0]
        return [0.94, 0.1]

    service = SemanticMatchingService(embedding_fn=fake_embedding, semantic_ready_override=True)
    summary = await service.analyze_context_similarity(
        resume_text="Built dashboards, SQL reporting, and stakeholder summaries.",
        role_text="Data Analyst role requiring dashboards, SQL, and business reporting.",
        evidence_sources=["resume_summary", "job_postings"],
    )

    assert summary.semantic_context_ready is True
    assert summary.context_similarity_score > 0.95
    assert summary.context_match_level == "strong"
    assert "job_postings" in summary.evidence_sources


@pytest.mark.asyncio
async def test_capstone_gap_analysis_falls_back_when_local_embedding_model_fails(
    db_session,
    test_user,
    monkeypatch,
):
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "local")

    def fail_local_embedding(text: str):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(
        "app.services.analytics.embeddingService._generate_local_embedding",
        fail_local_embedding,
    )
    await seed_capstone_analytics_minimum(db_session)
    resume = ResumeModel(
        view_url="https://storage.example/resume.pdf",
        user_id=test_user.id,
        storage_file_id="resumes/test.pdf",
        original_filename="resume.pdf",
        folder_id="resumes",
        ai_summary="Experienced with Python and SQL.",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    payload = await CapstoneAnalyticsService(db_session).analyze_gap(
        resume_id=resume.id,
        user_id=test_user.id,
        target_role="Data Analyst",
    )

    assert payload["status"] == "ok"
    assert payload["analysis_version"] == "semantic_gap_v1"
    assert payload["exact_match_count"] >= 1
    assert payload["match_score"] > 0
    assert 0 <= payload["overall_readiness_score"] <= 1


@pytest.mark.asyncio
async def test_capstone_gap_analysis_endpoint_returns_gap_payload(client, db_session, test_user, auth_headers):
    await seed_capstone_analytics_minimum(db_session)
    resume = ResumeModel(
        view_url="https://storage.example/resume.pdf",
        user_id=test_user.id,
        storage_file_id="resumes/test.pdf",
        original_filename="resume.pdf",
        folder_id="resumes",
        ai_summary="Experienced with Python and SQL.",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    response = await client.get(
        "/api/v1/capstone/gap-analysis",
        params={"resume_id": str(resume.id), "target_role": "Data Analyst"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["target_role"] == "Data Analyst"
    assert payload["analysis_version"] == "semantic_gap_v1"
    assert "match_score" in payload
    assert "overall_readiness_score" in payload
    assert "context_similarity_score" in payload
    assert "semantic_matched_skills" in payload
    assert payload["priority_missing_skills"]
    assert "skill_gap_score" in payload["priority_missing_skills"][0]
    assert payload["gap_insights"]
    assert payload["market_signals"]["target_role"] == "Data Analyst"
    assert payload["current_skills"]
    assert payload["missing_skills"]
    assert payload["recommended_courses"]


@pytest.mark.asyncio
async def test_capstone_learning_route_optimization_respects_constraints_and_persists_run(
    client,
    db_session,
    test_user,
    auth_headers,
):
    await seed_capstone_analytics_minimum(db_session)
    resume = ResumeModel(
        view_url="https://storage.example/resume.pdf",
        user_id=test_user.id,
        storage_file_id="resumes/test.pdf",
        original_filename="resume.pdf",
        folder_id="resumes",
        ai_summary="Experienced with Python and SQL.",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    response = await client.post(
        "/api/v1/capstone/learning-route/optimize",
        headers=auth_headers,
        json={
            "resume_id": str(resume.id),
            "target_role": "Data Analyst",
            "budget": 100,
            "available_hours": 30,
            "max_courses": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["objective_version"] in {OBJECTIVE_VERSION_HEURISTIC, OBJECTIVE_VERSION_CP_SAT}
    if ORToolsLearningRouteOptimizer.is_available():
        assert payload["objective_version"] == OBJECTIVE_VERSION_CP_SAT
        assert payload["solver_status"] in {"OPTIMAL", "FEASIBLE", "NO_CANDIDATES"}
        assert payload["model_explanation"]
    else:
        assert payload["objective_version"] == OBJECTIVE_VERSION_HEURISTIC
    assert payload["match_score_before"] >= 0
    assert payload["total_cost"] <= 100
    assert payload["total_hours"] <= 30
    assert len(payload["selected_courses"]) <= 2
    assert payload["projected_match_score_after"] >= payload["match_score_before"]
    assert payload["route_summary"]
    if payload["selected_courses"]:
        assert payload["selected_courses"][0]["sequence_order"] == 1
        assert payload["selected_courses"][0]["selection_reason"]
        assert payload["selected_courses"][0]["covered_priority_skills"]

    optimization_run = await db_session.get(
        OptimizationRunModel,
        uuid.UUID(payload["optimization_run_id"]),
    )
    assert optimization_run is not None
    assert optimization_run.status == "completed"
    assert optimization_run.objective_version == payload["objective_version"]
    assert optimization_run.total_cost == payload["total_cost"]
    assert optimization_run.skill_coverage["route_summary"] == payload["route_summary"]

    runs_response = await client.get(
        "/api/v1/capstone/learning-route/runs",
        headers=auth_headers,
    )

    assert runs_response.status_code == 200
    runs_payload = runs_response.json()
    assert runs_payload["runs"][0]["optimization_run_id"] == payload["optimization_run_id"]
    assert runs_payload["runs"][0]["selected_courses_count"] == len(payload["selected_courses"])


@pytest.mark.asyncio
async def test_phase_7_baseline_evaluation_endpoint_compares_all_methods(
    client,
    db_session,
    test_user,
    auth_headers,
):
    await seed_capstone_analytics_minimum(db_session)
    resume = ResumeModel(
        view_url="https://storage.example/resume.pdf",
        user_id=test_user.id,
        storage_file_id="resumes/phase-7.pdf",
        original_filename="phase-7.pdf",
        folder_id="resumes",
        ai_summary="Experienced with Python and SQL.",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    response = await client.post(
        "/api/v1/capstone/learning-route/evaluate-baselines",
        headers=auth_headers,
        json={
            "resume_id": str(resume.id),
            "target_role": "Data Analyst",
            "budget": 100,
            "available_hours": 30,
            "max_courses": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["evaluation_version"] == PHASE_7_EVALUATION_VERSION
    assert payload["baseline_seed"] == 42
    assert payload["winner_summary"]["best_method"]
    methods = {method["method"]: method for method in payload["methods"]}
    assert {
        "cheapest_feasible",
        "highest_rated_feasible",
        "similarity_only",
        "heuristic_route_v1",
        "random_feasible_seeded",
        "cp_sat_route_v1",
    } == set(methods)
    for method in methods.values():
        assert method["metrics"]["constraint_satisfaction"] == 1
        assert method["metrics"]["explanation_completeness"] == 1
        assert method["metrics"]["selected_courses_count"] <= 2
        assert method["metrics"]["total_cost"] <= 100
        assert method["metrics"]["total_hours"] <= 30
        assert method["explanation"]
    if ORToolsLearningRouteOptimizer.is_available():
        assert methods["cp_sat_route_v1"]["solver_status"] in {"OPTIMAL", "FEASIBLE", "NO_CANDIDATES"}


@pytest.mark.skipif(
    not ORToolsLearningRouteOptimizer.is_available(),
    reason="OR-Tools is not installed in this environment.",
)
def test_phase_7_cp_sat_beats_cheapest_on_weighted_critical_coverage(db_session):
    evaluator = LearningRouteBaselineEvaluationService(db_session)
    missing_skills = [
        {
            "skill_id": "skill-critical",
            "normalized_name": "python",
            "display_name": "Python",
            "importance_score": 0.95,
            "market_demand_score": 1.0,
            "skill_gap_score": 1.2,
            "priority_rank": 1,
        },
        {
            "skill_id": "skill-support",
            "normalized_name": "excel",
            "display_name": "Excel",
            "importance_score": 0.4,
            "market_demand_score": 0.2,
            "skill_gap_score": 0.3,
            "priority_rank": 5,
        },
    ]
    candidates = [
        {
            "course_id": "cheap-support",
            "title": "Cheap Excel",
            "provider": "Test",
            "url": None,
            "cost": 1,
            "currency": "CAD",
            "duration_hours": 2,
            "difficulty": "beginner",
            "rating": 4.9,
            "optimization_score": 1.0,
            "skills_covered": [
                {
                    "skill_id": "skill-support",
                    "normalized_name": "excel",
                    "display_name": "Excel",
                    "coverage_score": 0.9,
                    "is_prerequisite": False,
                }
            ],
        },
        {
            "course_id": "critical-route",
            "title": "Critical Python",
            "provider": "Test",
            "url": None,
            "cost": 20,
            "currency": "CAD",
            "duration_hours": 8,
            "difficulty": "beginner",
            "rating": 4.0,
            "optimization_score": 1.0,
            "skills_covered": [
                {
                    "skill_id": "skill-critical",
                    "normalized_name": "python",
                    "display_name": "Python",
                    "coverage_score": 0.9,
                    "is_prerequisite": True,
                }
            ],
        },
    ]

    payload = evaluator.evaluate_candidates(
        candidates=candidates,
        missing_skills=missing_skills,
        match_score_before=0.2,
        constraints=LearningRouteConstraints(budget=25, available_hours=10, max_courses=1),
    )

    methods = {method["method"]: method for method in payload["methods"]}
    cheapest = methods["cheapest_feasible"]["metrics"]
    cp_sat = methods["cp_sat_route_v1"]["metrics"]

    assert cp_sat["critical_skill_coverage"] > cheapest["critical_skill_coverage"]
    assert cp_sat["weighted_skill_coverage"] > cheapest["weighted_skill_coverage"]
    assert methods["cp_sat_route_v1"]["selected_courses"][0]["course_id"] == "critical-route"


@pytest.mark.skipif(
    not ORToolsLearningRouteOptimizer.is_available(),
    reason="OR-Tools is not installed in this environment.",
)
def test_phase_7_cp_sat_reduces_similarity_only_redundancy_and_cost(db_session):
    evaluator = LearningRouteBaselineEvaluationService(db_session)
    missing_skills = [
        {
            "skill_id": "skill-a",
            "normalized_name": "python",
            "display_name": "Python",
            "importance_score": 0.95,
            "market_demand_score": 1.0,
            "skill_gap_score": 1.2,
            "priority_rank": 1,
        },
        {
            "skill_id": "skill-b",
            "normalized_name": "sql",
            "display_name": "SQL",
            "importance_score": 0.9,
            "market_demand_score": 0.9,
            "skill_gap_score": 1.0,
            "priority_rank": 2,
        },
        {
            "skill_id": "skill-c",
            "normalized_name": "tableau",
            "display_name": "Tableau",
            "importance_score": 0.7,
            "market_demand_score": 0.5,
            "skill_gap_score": 0.8,
            "priority_rank": 5,
        },
    ]
    candidates = [
        {
            "course_id": "expensive-overlap",
            "title": "Expensive Python SQL Bundle",
            "provider": "Test",
            "url": None,
            "cost": 80,
            "currency": "CAD",
            "duration_hours": 8,
            "difficulty": "intermediate",
            "rating": 4.8,
            "optimization_score": 1.0,
            "skills_covered": [
                {
                    "skill_id": "skill-a",
                    "normalized_name": "python",
                    "display_name": "Python",
                    "coverage_score": 0.9,
                    "is_prerequisite": False,
                },
                {
                    "skill_id": "skill-b",
                    "normalized_name": "sql",
                    "display_name": "SQL",
                    "coverage_score": 0.9,
                    "is_prerequisite": False,
                },
            ],
        },
        {
            "course_id": "bc-extra",
            "title": "Efficient SQL Tableau",
            "provider": "Test",
            "url": None,
            "cost": 5,
            "currency": "CAD",
            "duration_hours": 3,
            "difficulty": "beginner",
            "rating": 4.5,
            "optimization_score": 1.0,
            "skills_covered": [
                {
                    "skill_id": "skill-b",
                    "normalized_name": "sql",
                    "display_name": "SQL",
                    "coverage_score": 0.9,
                    "is_prerequisite": False,
                },
                {
                    "skill_id": "skill-c",
                    "normalized_name": "tableau",
                    "display_name": "Tableau",
                    "coverage_score": 0.9,
                    "is_prerequisite": False,
                },
            ],
        },
        {
            "course_id": "a-only",
            "title": "Focused Python",
            "provider": "Test",
            "url": None,
            "cost": 5,
            "currency": "CAD",
            "duration_hours": 3,
            "difficulty": "beginner",
            "rating": 4.2,
            "optimization_score": 1.0,
            "skills_covered": [
                {
                    "skill_id": "skill-a",
                    "normalized_name": "python",
                    "display_name": "Python",
                    "coverage_score": 0.9,
                    "is_prerequisite": True,
                }
            ],
        },
    ]

    payload = evaluator.evaluate_candidates(
        candidates=candidates,
        missing_skills=missing_skills,
        match_score_before=0.1,
        constraints=LearningRouteConstraints(budget=100, available_hours=15, max_courses=2),
    )

    methods = {method["method"]: method for method in payload["methods"]}
    similarity = methods["similarity_only"]["metrics"]
    cp_sat = methods["cp_sat_route_v1"]["metrics"]

    assert cp_sat["weighted_skill_coverage"] == similarity["weighted_skill_coverage"]
    assert cp_sat["critical_skill_coverage"] == similarity["critical_skill_coverage"]
    assert cp_sat["redundancy_rate"] < similarity["redundancy_rate"]
    assert cp_sat["total_cost"] < similarity["total_cost"]
    assert {course["course_id"] for course in methods["cp_sat_route_v1"]["selected_courses"]} == {
        "a-only",
        "bc-extra",
    }


def test_phase_7_random_baseline_is_reproducible(db_session):
    evaluator = LearningRouteBaselineEvaluationService(db_session)
    missing_skills = [
        {
            "skill_id": "skill-a",
            "normalized_name": "python",
            "display_name": "Python",
            "importance_score": 0.8,
            "skill_gap_score": 0.8,
            "priority_rank": 1,
        },
        {
            "skill_id": "skill-b",
            "normalized_name": "excel",
            "display_name": "Excel",
            "importance_score": 0.7,
            "skill_gap_score": 0.7,
            "priority_rank": 2,
        },
    ]
    candidates = [
        {
            "course_id": f"course-{index}",
            "title": f"Course {index}",
            "provider": "Test",
            "url": None,
            "cost": index,
            "currency": "CAD",
            "duration_hours": 1,
            "difficulty": "beginner",
            "rating": 4.0,
            "optimization_score": 1.0,
            "skills_covered": [
                {
                    "skill_id": "skill-a" if index % 2 else "skill-b",
                    "normalized_name": "python" if index % 2 else "excel",
                    "display_name": "Python" if index % 2 else "Excel",
                    "coverage_score": 0.9,
                    "is_prerequisite": False,
                }
            ],
        }
        for index in range(1, 6)
    ]

    first_payload = evaluator.evaluate_candidates(
        candidates=candidates,
        missing_skills=missing_skills,
        match_score_before=0.3,
        constraints=LearningRouteConstraints(budget=10, available_hours=5, max_courses=2),
    )
    second_payload = evaluator.evaluate_candidates(
        candidates=candidates,
        missing_skills=missing_skills,
        match_score_before=0.3,
        constraints=LearningRouteConstraints(budget=10, available_hours=5, max_courses=2),
    )

    first_random = next(method for method in first_payload["methods"] if method["method"] == "random_feasible_seeded")
    second_random = next(method for method in second_payload["methods"] if method["method"] == "random_feasible_seeded")

    assert first_payload["baseline_seed"] == second_payload["baseline_seed"] == 42
    assert [course["course_id"] for course in first_random["selected_courses"]] == [
        course["course_id"] for course in second_random["selected_courses"]
    ]
    assert first_random["metrics"]["weighted_skill_coverage"] == second_random["metrics"]["weighted_skill_coverage"]


@pytest.mark.skipif(
    not ORToolsLearningRouteOptimizer.is_available(),
    reason="OR-Tools is not installed in this environment.",
)
def test_cp_sat_optimizer_prefers_high_value_gap_under_constraints(db_session):
    optimizer = ORToolsLearningRouteOptimizer(db_session)
    missing_by_id = {
        "skill-high": {
            "skill_id": "skill-high",
            "normalized_name": "python",
            "display_name": "Python",
            "importance_score": 0.95,
            "market_demand_score": 1.0,
            "skill_gap_score": 1.2,
            "priority_rank": 1,
        },
        "skill-low": {
            "skill_id": "skill-low",
            "normalized_name": "excel",
            "display_name": "Excel",
            "importance_score": 0.4,
            "market_demand_score": 0.2,
            "skill_gap_score": 0.3,
            "priority_rank": 2,
        },
    }
    candidates = [
        {
            "course_id": "course-high",
            "title": "Applied Python",
            "provider": "Test",
            "url": None,
            "cost": 50,
            "currency": "CAD",
            "duration_hours": 8,
            "difficulty": "intermediate",
            "rating": 4.8,
            "optimization_score": 1.0,
            "skills_covered": [
                {
                    "skill_id": "skill-high",
                    "normalized_name": "python",
                    "display_name": "Python",
                    "coverage_score": 0.9,
                    "is_prerequisite": False,
                }
            ],
        },
        {
            "course_id": "course-low",
            "title": "Excel Basics",
            "provider": "Test",
            "url": None,
            "cost": 10,
            "currency": "CAD",
            "duration_hours": 2,
            "difficulty": "beginner",
            "rating": 5.0,
            "optimization_score": 1.0,
            "skills_covered": [
                {
                    "skill_id": "skill-low",
                    "normalized_name": "excel",
                    "display_name": "Excel",
                    "coverage_score": 0.9,
                    "is_prerequisite": False,
                }
            ],
        },
    ]

    solution = optimizer._solve_cp_sat(
        candidates=candidates,
        missing_by_id=missing_by_id,
        constraints=LearningRouteConstraints(budget=60, available_hours=10, max_courses=1),
    )

    assert solution["solver_status"] == "OPTIMAL"
    assert solution["selected_course_indexes"] == [0]
    assert solution["covered_skill_ids"] == {"skill-high"}


@pytest.mark.skipif(
    not ORToolsLearningRouteOptimizer.is_available(),
    reason="OR-Tools is not installed in this environment.",
)
def test_cp_sat_optimizer_respects_budget_hours_and_course_count(db_session):
    optimizer = ORToolsLearningRouteOptimizer(db_session)
    missing_by_id = {
        "skill-high": {
            "skill_id": "skill-high",
            "normalized_name": "python",
            "display_name": "Python",
            "importance_score": 0.95,
            "market_demand_score": 1.0,
            "skill_gap_score": 1.2,
            "priority_rank": 1,
        }
    }
    candidates = [
        {
            "course_id": "too-expensive",
            "title": "Premium Python",
            "provider": "Test",
            "url": None,
            "cost": 500,
            "currency": "CAD",
            "duration_hours": 4,
            "difficulty": "beginner",
            "rating": 5.0,
            "optimization_score": 1.0,
            "skills_covered": [
                {
                    "skill_id": "skill-high",
                    "normalized_name": "python",
                    "display_name": "Python",
                    "coverage_score": 0.95,
                    "is_prerequisite": False,
                }
            ],
        },
        {
            "course_id": "too-long",
            "title": "Python Marathon",
            "provider": "Test",
            "url": None,
            "cost": 20,
            "currency": "CAD",
            "duration_hours": 100,
            "difficulty": "beginner",
            "rating": 5.0,
            "optimization_score": 1.0,
            "skills_covered": [
                {
                    "skill_id": "skill-high",
                    "normalized_name": "python",
                    "display_name": "Python",
                    "coverage_score": 0.95,
                    "is_prerequisite": False,
                }
            ],
        },
        {
            "course_id": "feasible",
            "title": "Practical Python",
            "provider": "Test",
            "url": None,
            "cost": 40,
            "currency": "CAD",
            "duration_hours": 6,
            "difficulty": "beginner",
            "rating": 4.5,
            "optimization_score": 1.0,
            "skills_covered": [
                {
                    "skill_id": "skill-high",
                    "normalized_name": "python",
                    "display_name": "Python",
                    "coverage_score": 0.9,
                    "is_prerequisite": False,
                }
            ],
        },
    ]

    solution = optimizer._solve_cp_sat(
        candidates=candidates,
        missing_by_id=missing_by_id,
        constraints=LearningRouteConstraints(budget=50, available_hours=10, max_courses=1),
    )

    assert solution["solver_status"] == "OPTIMAL"
    assert solution["selected_course_indexes"] == [2]
    assert solution["covered_skill_ids"] == {"skill-high"}


@pytest.mark.skipif(
    not ORToolsLearningRouteOptimizer.is_available(),
    reason="OR-Tools is not installed in this environment.",
)
def test_cp_sat_optimizer_avoids_redundancy_when_distinct_gap_can_be_covered(db_session):
    optimizer = ORToolsLearningRouteOptimizer(db_session)
    missing_by_id = {
        "skill-high": {
            "skill_id": "skill-high",
            "normalized_name": "python",
            "display_name": "Python",
            "importance_score": 0.95,
            "market_demand_score": 1.0,
            "skill_gap_score": 1.2,
            "priority_rank": 1,
        },
        "skill-low": {
            "skill_id": "skill-low",
            "normalized_name": "excel",
            "display_name": "Excel",
            "importance_score": 0.5,
            "market_demand_score": 0.2,
            "skill_gap_score": 0.5,
            "priority_rank": 4,
        },
    }
    candidates = [
        {
            "course_id": "python-a",
            "title": "Python A",
            "provider": "Test",
            "url": None,
            "cost": 10,
            "currency": "CAD",
            "duration_hours": 2,
            "difficulty": "beginner",
            "rating": 4.5,
            "optimization_score": 1.0,
            "skills_covered": [
                {
                    "skill_id": "skill-high",
                    "normalized_name": "python",
                    "display_name": "Python",
                    "coverage_score": 0.9,
                    "is_prerequisite": False,
                }
            ],
        },
        {
            "course_id": "python-b",
            "title": "Python B",
            "provider": "Test",
            "url": None,
            "cost": 10,
            "currency": "CAD",
            "duration_hours": 2,
            "difficulty": "beginner",
            "rating": 4.5,
            "optimization_score": 1.0,
            "skills_covered": [
                {
                    "skill_id": "skill-high",
                    "normalized_name": "python",
                    "display_name": "Python",
                    "coverage_score": 0.9,
                    "is_prerequisite": False,
                }
            ],
        },
        {
            "course_id": "excel",
            "title": "Excel",
            "provider": "Test",
            "url": None,
            "cost": 10,
            "currency": "CAD",
            "duration_hours": 2,
            "difficulty": "beginner",
            "rating": 4.5,
            "optimization_score": 1.0,
            "skills_covered": [
                {
                    "skill_id": "skill-low",
                    "normalized_name": "excel",
                    "display_name": "Excel",
                    "coverage_score": 0.9,
                    "is_prerequisite": False,
                }
            ],
        },
    ]

    solution = optimizer._solve_cp_sat(
        candidates=candidates,
        missing_by_id=missing_by_id,
        constraints=LearningRouteConstraints(budget=30, available_hours=10, max_courses=2),
    )

    assert solution["solver_status"] == "OPTIMAL"
    assert set(solution["selected_course_indexes"]) in ({0, 2}, {1, 2})
    assert solution["covered_skill_ids"] == {"skill-high", "skill-low"}


@pytest.mark.skipif(
    not ORToolsLearningRouteOptimizer.is_available(),
    reason="OR-Tools is not installed in this environment.",
)
def test_cp_sat_optimizer_sequences_beginner_before_advanced_inside_solver(db_session):
    optimizer = ORToolsLearningRouteOptimizer(db_session)
    missing_by_id = {
        "skill-advanced": {
            "skill_id": "skill-advanced",
            "normalized_name": "machine_learning",
            "display_name": "Machine Learning",
            "importance_score": 0.95,
            "market_demand_score": 1.0,
            "skill_gap_score": 1.2,
            "priority_rank": 1,
        },
        "skill-foundation": {
            "skill_id": "skill-foundation",
            "normalized_name": "python",
            "display_name": "Python",
            "importance_score": 0.8,
            "market_demand_score": 0.8,
            "skill_gap_score": 0.9,
            "priority_rank": 2,
        },
    }
    candidates = [
        {
            "course_id": "advanced",
            "title": "Advanced ML",
            "provider": "Test",
            "url": None,
            "cost": 10,
            "currency": "CAD",
            "duration_hours": 2,
            "difficulty": "advanced",
            "rating": 5.0,
            "optimization_score": 1.0,
            "skills_covered": [
                {
                    "skill_id": "skill-advanced",
                    "normalized_name": "machine_learning",
                    "display_name": "Machine Learning",
                    "coverage_score": 0.9,
                    "is_prerequisite": False,
                }
            ],
        },
        {
            "course_id": "beginner",
            "title": "Python Foundation",
            "provider": "Test",
            "url": None,
            "cost": 10,
            "currency": "CAD",
            "duration_hours": 2,
            "difficulty": "beginner",
            "rating": 4.0,
            "optimization_score": 1.0,
            "skills_covered": [
                {
                    "skill_id": "skill-foundation",
                    "normalized_name": "python",
                    "display_name": "Python",
                    "coverage_score": 0.9,
                    "is_prerequisite": True,
                }
            ],
        },
    ]

    solution = optimizer._solve_cp_sat(
        candidates=candidates,
        missing_by_id=missing_by_id,
        constraints=LearningRouteConstraints(budget=30, available_hours=10, max_courses=2),
    )

    assert solution["solver_status"] == "OPTIMAL"
    assert set(solution["selected_course_indexes"]) == {0, 1}
    assert solution["sequence_positions"][1] < solution["sequence_positions"][0]


@pytest.mark.skipif(
    not ORToolsLearningRouteOptimizer.is_available(),
    reason="OR-Tools is not installed in this environment.",
)
def test_cp_sat_optimizer_sequences_prerequisite_signal_before_same_difficulty_course(db_session):
    optimizer = ORToolsLearningRouteOptimizer(db_session)
    missing_by_id = {
        "skill-core": {
            "skill_id": "skill-core",
            "normalized_name": "sql",
            "display_name": "SQL",
            "importance_score": 0.9,
            "market_demand_score": 0.9,
            "skill_gap_score": 1.0,
            "priority_rank": 1,
        },
        "skill-reporting": {
            "skill_id": "skill-reporting",
            "normalized_name": "tableau",
            "display_name": "Tableau",
            "importance_score": 0.8,
            "market_demand_score": 0.7,
            "skill_gap_score": 0.9,
            "priority_rank": 2,
        },
    }
    candidates = [
        {
            "course_id": "reporting",
            "title": "Intermediate Reporting",
            "provider": "Test",
            "url": None,
            "cost": 10,
            "currency": "CAD",
            "duration_hours": 2,
            "difficulty": "intermediate",
            "rating": 5.0,
            "optimization_score": 1.0,
            "skills_covered": [
                {
                    "skill_id": "skill-reporting",
                    "normalized_name": "tableau",
                    "display_name": "Tableau",
                    "coverage_score": 0.9,
                    "is_prerequisite": False,
                }
            ],
        },
        {
            "course_id": "core",
            "title": "Intermediate SQL Core",
            "provider": "Test",
            "url": None,
            "cost": 10,
            "currency": "CAD",
            "duration_hours": 2,
            "difficulty": "intermediate",
            "rating": 4.5,
            "optimization_score": 1.0,
            "skills_covered": [
                {
                    "skill_id": "skill-core",
                    "normalized_name": "sql",
                    "display_name": "SQL",
                    "coverage_score": 0.9,
                    "is_prerequisite": True,
                }
            ],
        },
    ]

    solution = optimizer._solve_cp_sat(
        candidates=candidates,
        missing_by_id=missing_by_id,
        constraints=LearningRouteConstraints(budget=30, available_hours=10, max_courses=2),
    )

    assert solution["solver_status"] == "OPTIMAL"
    assert set(solution["selected_course_indexes"]) == {0, 1}
    assert solution["sequence_positions"][1] < solution["sequence_positions"][0]


@pytest.mark.asyncio
async def test_capstone_learning_route_optimization_returns_404_for_other_user_resume(
    client,
    db_session,
    auth_headers,
):
    other_user = User(
        id=uuid.uuid4(),
        email="other-capstone@example.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(other_user)
    await db_session.commit()

    other_resume = ResumeModel(
        view_url="https://storage.example/resume.pdf",
        user_id=other_user.id,
        storage_file_id="resumes/other.pdf",
        original_filename="other.pdf",
        folder_id="resumes",
        ai_summary="Experienced with Python.",
    )
    db_session.add(other_resume)
    await db_session.commit()
    await db_session.refresh(other_resume)

    response = await client.post(
        "/api/v1/capstone/learning-route/optimize",
        headers=auth_headers,
        json={
            "resume_id": str(other_resume.id),
            "target_role": "Data Analyst",
        },
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_capstone_learning_route_optimization_returns_empty_route_when_no_courses_cover_gaps(
    client,
    db_session,
    test_user,
    auth_headers,
):
    await seed_capstone_analytics_minimum(db_session)
    skill = SkillModel(
        normalized_name="rust",
        display_name="Rust",
        category="programming",
        source="test",
    )
    db_session.add(skill)
    await db_session.flush()
    db_session.add(
        JobSkillModel(
            skill_id=skill.id,
            target_role="Rust Analyst",
            importance_score=0.9,
            extraction_method="role_seed",
            evidence_text="Required by a custom test role.",
        )
    )
    resume = ResumeModel(
        view_url="https://storage.example/resume.pdf",
        user_id=test_user.id,
        storage_file_id="resumes/test.pdf",
        original_filename="resume.pdf",
        folder_id="resumes",
        ai_summary="Experienced with SQL.",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    response = await client.post(
        "/api/v1/capstone/learning-route/optimize",
        headers=auth_headers,
        json={
            "resume_id": str(resume.id),
            "target_role": "Rust Analyst",
            "budget": 50,
            "available_hours": 5,
            "max_courses": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_courses"] == []
    assert payload["covered_skills"] == []
    assert [gap["normalized_name"] for gap in payload["remaining_gaps"]] == ["rust"]
    assert payload["route_summary"]


@pytest.mark.asyncio
async def test_capstone_extracts_job_skills_from_existing_job_posting(db_session, test_company):
    await seed_capstone_analytics_minimum(db_session)
    job = JobPosting(
        company_id=test_company.id,
        title="Data Analyst",
        description="Analyze dashboards and business metrics.",
        requirements="Strong SQL, Python, Excel, Power BI, and communication skills.",
        responsibilities="Clean data and build KPI dashboards.",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    service = CapstoneAnalyticsService(db_session)
    links = await service.extract_job_skills_from_job_posting(job_posting_id=job.id)
    extracted = await service.get_job_skills(job.id)

    extracted_names = {skill["normalized_name"] for skill in extracted}

    assert links
    assert {"sql", "python", "excel", "power_bi", "communication"}.issubset(extracted_names)
    assert all(skill["extraction_method"] == "job_posting_rules_v1" for skill in extracted)


@pytest.mark.asyncio
async def test_capstone_resume_skill_sync_endpoint_uses_existing_ai_summary(client, db_session, test_user, auth_headers):
    await seed_capstone_analytics_minimum(db_session)
    resume = ResumeModel(
        view_url="https://storage.example/resume.pdf",
        user_id=test_user.id,
        storage_file_id="resumes/test.pdf",
        original_filename="resume.pdf",
        folder_id="resumes",
        ai_summary="Candidate has SQL, Tableau, and statistics experience.",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    response = await client.post(
        f"/api/v1/capstone/resumes/{resume.id}/skills/sync",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    extracted_names = {skill["normalized_name"] for skill in payload["extracted_skills"]}
    assert {"sql", "tableau", "statistics"}.issubset(extracted_names)


@pytest.mark.asyncio
async def test_student_can_review_reject_and_add_manual_resume_skills(
    client,
    db_session,
    test_user,
    auth_headers,
):
    await seed_capstone_analytics_minimum(db_session)
    resume = ResumeModel(
        view_url="https://storage.example/resume.pdf",
        user_id=test_user.id,
        storage_file_id="resumes/test.pdf",
        original_filename="resume.pdf",
        folder_id="resumes",
        ai_summary="Candidate has SQL and Tableau experience.",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    sync_response = await client.post(
        f"/api/v1/capstone/resumes/{resume.id}/skills/sync",
        headers=auth_headers,
    )

    assert sync_response.status_code == 200
    skills_response = await client.get(
        f"/api/v1/capstone/resumes/{resume.id}/skills",
        headers=auth_headers,
    )
    skills_payload = skills_response.json()
    sql_skill = next(skill for skill in skills_payload["skills"] if skill["normalized_name"] == "sql")
    tableau_skill = next(skill for skill in skills_payload["skills"] if skill["normalized_name"] == "tableau")

    confirm_response = await client.patch(
        f"/api/v1/capstone/resumes/{resume.id}/skills/{sql_skill['resume_skill_id']}",
        headers=auth_headers,
        json={"status": "confirmed"},
    )
    reject_response = await client.patch(
        f"/api/v1/capstone/resumes/{resume.id}/skills/{tableau_skill['resume_skill_id']}",
        headers=auth_headers,
        json={"status": "rejected"},
    )
    manual_response = await client.post(
        f"/api/v1/capstone/resumes/{resume.id}/skills/manual",
        headers=auth_headers,
        json={"normalized_name": "python", "evidence_text": "Portfolio project", "source_section": "student_review"},
    )

    assert confirm_response.status_code == 200
    assert reject_response.status_code == 200
    assert manual_response.status_code == 200
    reviewed = {skill["normalized_name"]: skill for skill in manual_response.json()["skills"]}
    assert reviewed["sql"]["status"] == "confirmed"
    assert reviewed["tableau"]["status"] == "rejected"
    assert reviewed["python"]["status"] == "manual"

    gap_payload = await CapstoneAnalyticsService(db_session).analyze_gap(
        resume_id=resume.id,
        user_id=test_user.id,
        target_role="Data Analyst",
    )
    current_names = {skill["normalized_name"] for skill in gap_payload["current_skills"]}

    assert "sql" in current_names
    assert "python" in current_names
    assert "tableau" not in current_names


@pytest.mark.asyncio
async def test_student_cannot_review_another_users_resume_skill(
    client,
    db_session,
    auth_headers,
):
    await seed_capstone_analytics_minimum(db_session)
    other_user = User(
        id=uuid.uuid4(),
        email="other-review@example.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(other_user)
    await db_session.commit()

    other_resume = ResumeModel(
        view_url="https://storage.example/resume.pdf",
        user_id=other_user.id,
        storage_file_id="resumes/other-review.pdf",
        original_filename="other-review.pdf",
        folder_id="resumes",
        ai_summary="Experienced with SQL.",
    )
    db_session.add(other_resume)
    await db_session.commit()
    await db_session.refresh(other_resume)
    await CapstoneAnalyticsService(db_session).extract_resume_skills_from_existing_resume(
        resume_id=other_resume.id,
        user_id=other_user.id,
    )
    skills = await CapstoneAnalyticsService(db_session).get_resume_skills(other_resume.id)

    response = await client.patch(
        f"/api/v1/capstone/resumes/{other_resume.id}/skills/{skills[0]['resume_skill_id']}",
        headers=auth_headers,
        json={"status": "confirmed"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_capstone_gap_analysis_prefers_real_job_skills_over_role_seed(
    db_session,
    test_user,
    test_company,
):
    await seed_capstone_analytics_minimum(db_session)
    resume = ResumeModel(
        view_url="https://storage.example/resume.pdf",
        user_id=test_user.id,
        storage_file_id="resumes/test.pdf",
        original_filename="resume.pdf",
        folder_id="resumes",
        ai_summary="Candidate has strong SQL experience.",
    )
    job = JobPosting(
        company_id=test_company.id,
        title="Data Analyst",
        requirements="Must have SQL and Tableau experience.",
    )
    db_session.add_all([resume, job])
    await db_session.commit()
    await db_session.refresh(resume)
    await db_session.refresh(job)

    service = CapstoneAnalyticsService(db_session)
    await service.extract_job_skills_from_job_posting(job_posting_id=job.id)
    payload = await service.analyze_gap(
        resume_id=resume.id,
        user_id=test_user.id,
        target_role="Data Analyst",
    )

    required_names = {skill["normalized_name"] for skill in payload["required_skills"]}
    missing_names = {skill["normalized_name"] for skill in payload["missing_skills"]}

    assert payload["requirements_source"] == "job_postings"
    assert required_names == {"sql", "tableau"}
    assert missing_names == {"tableau"}
    assert "excel" not in required_names
    assert payload["market_signals"]["source"] == "job_postings"
    assert payload["market_signals"]["synced_job_postings_count"] == 1
    assert all(skill["market_demand_count"] == 1 for skill in payload["required_skills"])
    assert payload["priority_missing_skills"][0]["normalized_name"] == "tableau"
