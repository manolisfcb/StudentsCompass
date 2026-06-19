import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from app.models.resumeModel import ResumeModel
from app.models.resumeEmbeddingsModel import ResumeEmbedding
from app.models.jobPostingModel import JobPosting
from app.routes.capstoneAnalyticsRoute import _run_capstone_operation
from app.models.skillModel import (
    CourseModel,
    CourseSkillModel,
    OptimizationRunModel,
    ResumeSkillModel,
    SkillAliasModel,
    SkillModel,
)
from app.services.analytics.capstoneAnalyticsService import CapstoneAnalyticsService
from app.services.analytics.capstoneAnalyticsSeedService import seed_capstone_analytics_minimum


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
    assert "Data Analyst" in ready_payload["supported_seed_roles"]


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
    assert payload["recommended_courses"]
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
    assert payload["current_skills"]
    assert payload["missing_skills"]
    assert payload["recommended_courses"]


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
