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
from app.services.analytics.capstoneAnalyticsSeedService import seed_capstone_analytics_minimum
from app.services.analytics.semanticMatchingService import SemanticMatchingService


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

    assert summary["skills"] == 25
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
    assert ready_payload["skills_count"] == 25
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
    assert payload["skills_count"] == 25
    assert payload["courses_count"] == 12
    assert payload["mapped_course_ratio"] == 1
    assert payload["metadata_completeness"]["overall"] == 1
    assert payload["next_actions"]
    assert any("Expand the skill catalog" in action for action in payload["next_actions"])


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
    assert payload["skills"] == 25
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
    assert payload["objective_version"] == "heuristic_route_v1"
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
    assert optimization_run.objective_version == "heuristic_route_v1"
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
