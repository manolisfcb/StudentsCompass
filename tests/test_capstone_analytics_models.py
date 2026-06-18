import pytest

from app.models.resumeModel import ResumeModel
from app.models.skillModel import (
    CourseModel,
    CourseSkillModel,
    OptimizationRunModel,
    ResumeSkillModel,
    SkillAliasModel,
    SkillModel,
)
from app.services.capstoneAnalyticsService import CapstoneAnalyticsService
from app.services.capstoneAnalyticsSeedService import seed_capstone_analytics_minimum


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
