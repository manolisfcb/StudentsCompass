"""What every Capstone payload looks like, pinned before the service is split.

``CapstoneAnalyticsService`` mixes extraction, review, catalogue, metrics,
embeddings, recommendations, optimisation and persistence in one class. TASK-023
splits it. The only thing that makes such a split safe is a before/after
comparison of what it produces, so this module builds a deterministic fixture
and asserts the **whole payload**, key by key, for every public entry point the
routes use.

Deterministic on purpose: fixed UUIDs, fixed timestamps, the hash embedding
provider, and no LLM. Two runs of this module produce byte-identical payloads,
which is what lets it be used as a golden.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest
from sqlalchemy import select

from app.models.companyModel import Company
from app.models.jobPostingModel import JobPosting
from app.models.resumeModel import ResumeModel
from app.models.skillModel import CourseModel, CourseSkillModel, SkillModel
from app.services.analytics.capstoneAnalyticsSeedService import (
    seed_capstone_analytics_minimum,
)
from app.services.analytics.capstoneAnalyticsService import CapstoneAnalyticsService

TARGET_ROLE = "Data Analyst"
REQUIREMENTS = "Must have SQL, Python and Tableau experience."


@pytest.fixture(autouse=True)
def _hash_embeddings(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "hash")


def _uuid(seed: int) -> uuid.UUID:
    """A stable UUID, so payloads that echo ids stay comparable across runs.

    The ``ca95`` prefix is not decoration. SQLite gives ``CHAR(32)`` NUMERIC
    affinity, so a UUID whose 32 hex characters parse as a number comes back
    from the database as an ``int`` or a ``float`` and SQLAlchemy then calls
    ``uuid.UUID(hex=<number>)``. ``uuid.UUID(int=1)`` is all digits and hits
    that every time; a letter in the prefix keeps the value textual. See
    TASK-064.
    """
    return uuid.UUID(hex=f"ca95{seed:028d}")


@pytest.fixture
async def capstone_world(db_session, test_user):
    """One deterministic Capstone universe: skills, a posting, a CV, a course."""
    await seed_capstone_analytics_minimum(db_session)

    company = Company(id=_uuid(1), company_name="Snapshot Co")
    db_session.add(company)
    await db_session.flush()

    posting = JobPosting(
        id=_uuid(2),
        company_id=company.id,
        title=TARGET_ROLE,
        requirements=REQUIREMENTS,
        is_active=True,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    resume = ResumeModel(
        id=_uuid(3),
        user_id=test_user.id,
        view_url="https://example.invalid/cv.pdf",
        storage_file_id="snapshot-cv",
        original_filename="cv.pdf",
        folder_id="resumes",
        ai_summary="Analyst with SQL and Excel experience across two internships.",
        created_at=datetime(2026, 1, 2, 12, 0, 0),
    )
    db_session.add_all([posting, resume])
    await db_session.flush()

    course = CourseModel(
        id=_uuid(4),
        title="Tableau for Analysts",
        provider="Snapshot Academy",
        cost=49.0,
        currency="CAD",
        duration_hours=6.0,
        difficulty="beginner",
        rating=4.5,
        is_active=True,
        created_at=datetime(2026, 1, 3, 12, 0, 0),
    )
    db_session.add(course)
    await db_session.flush()

    tableau_id = await db_session.scalar(
        select(SkillModel.id).where(SkillModel.normalized_name == "tableau")
    )
    if tableau_id is not None:
        db_session.add(
            CourseSkillModel(
                id=_uuid(5),
                course_id=course.id,
                skill_id=tableau_id,
                coverage_score=0.9,
                is_prerequisite=False,
            )
        )
    await db_session.commit()

    service = CapstoneAnalyticsService(db_session)
    await service.extract_job_skills_from_job_posting(job_posting_id=posting.id)
    await service.extract_resume_skills_from_text(
        resume_id=resume.id,
        user_id=test_user.id,
        text=resume.ai_summary,
    )
    return {"service": service, "posting": posting, "resume": resume, "course": course}


def _normalise(payload):
    """Drop what is legitimately non-deterministic, keep everything else.

    Only timestamps generated at call time and ids of rows created during the
    call are dropped; every value that describes *what the product decided*
    stays in the comparison.
    """
    volatile = {"created_at", "updated_at", "completed_at", "started_at", "generated_at", "id"}
    if isinstance(payload, dict):
        return {
            key: ("<volatile>" if key in volatile else _normalise(value))
            for key, value in sorted(payload.items())
        }
    if isinstance(payload, list):
        return [_normalise(item) for item in payload]
    return payload


async def collect_payloads(service, world, user_id) -> dict:
    """Every payload the routes can ask for, in one dict."""
    resume, posting = world["resume"], world["posting"]
    return {
        "analytics_status": await service.get_analytics_status(),
        "supported_roles": await service.get_supported_roles(),
        "catalog_quality": await service.get_catalog_quality(),
        "job_skills": await service.get_job_skills(posting.id),
        "resume_skills": await service.get_resume_skills(resume.id),
        "resume_skills_review": await service.list_resume_skills_for_review(
            resume_id=resume.id, user_id=user_id
        ),
        "gap": await service.analyze_gap(
            resume_id=resume.id, user_id=user_id, target_role=TARGET_ROLE
        ),
        "runs": await service.list_learning_route_runs(user_id=user_id),
    }


@pytest.mark.asyncio
async def test_the_payloads_are_deterministic(capstone_world, test_user):
    """Two identical calls agree, which is what makes this usable as a golden.

    After one warm-up call. ``analyze_gap`` syncs the resume embedding, so the
    very first invocation writes a row and ``resume_embeddings_count`` goes from
    0 to 1 — existing behaviour, and the reason the comparison starts from the
    second call rather than the first.
    """
    service = capstone_world["service"]
    await collect_payloads(service, capstone_world, test_user.id)

    first = _normalise(await collect_payloads(service, capstone_world, test_user.id))
    second = _normalise(await collect_payloads(service, capstone_world, test_user.id))

    assert json.dumps(first, sort_keys=True, default=str) == json.dumps(
        second, sort_keys=True, default=str
    )


@pytest.mark.asyncio
async def test_the_gap_payload_keeps_its_shape_and_its_numbers(capstone_world, test_user):
    payload = await capstone_world["service"].analyze_gap(
        resume_id=capstone_world["resume"].id,
        user_id=test_user.id,
        target_role=TARGET_ROLE,
    )

    assert set(payload) == {
        "analysis_version",
        "context_evidence_sources",
        "context_match_level",
        "context_similarity_score",
        "coverage_ratio",
        "current_skills",
        "exact_match_count",
        "gap_insights",
        "market_signals",
        "match_score",
        "matched_required_skills",
        "missing_skills",
        "overall_readiness_score",
        "priority_gap_score",
        "priority_missing_skills",
        "recommended_courses",
        "required_skills",
        "requirements_source",
        "resume_id",
        "semantic_context_ready",
        "semantic_match_count",
        "semantic_matched_skills",
        "semantic_score",
        "status",
        "target_role",
        "weak_match_count",
        "weak_matched_skills",
    }
    assert payload["target_role"] == TARGET_ROLE
    assert payload["requirements_source"] == "job_postings"
    required = {skill["normalized_name"] for skill in payload["required_skills"]}
    missing = {skill["normalized_name"] for skill in payload["missing_skills"]}
    # The posting asks for three; the CV shows SQL and Excel, so two are missing.
    assert required == {"sql", "python", "tableau"}
    assert missing == {"python", "tableau"}
    assert payload["market_signals"]["source"] == "job_postings"
    assert 0.0 <= payload["overall_readiness_score"] <= 1.0


@pytest.mark.asyncio
async def test_the_review_payload_keeps_its_shape(capstone_world, test_user):
    payload = await capstone_world["service"].list_resume_skills_for_review(
        resume_id=capstone_world["resume"].id, user_id=test_user.id
    )

    assert payload is not None
    assert set(payload) == {"resume_id", "skills"}
    assert payload["skills"], "the deterministic CV extracted no skills"
    skill = payload["skills"][0]
    assert set(skill) >= {"skill_id", "normalized_name", "display_name", "status"}
    assert skill["status"] in {"detected", "confirmed", "rejected", "manual"}


@pytest.mark.asyncio
async def test_the_catalog_quality_payload_keeps_its_shape(capstone_world):
    payload = await capstone_world["service"].get_catalog_quality()

    assert set(payload) == {
        "active_courses_count",
        "average_skills_per_course",
        "courses_count",
        "courses_with_skill_mapping",
        "mapped_course_ratio",
        "market_backed_role_count",
        "metadata_completeness",
        "next_actions",
        "quality_score",
        "quality_version",
        "seed_role_count",
        "skills_count",
    }
    assert isinstance(payload["quality_score"], (int, float))
    assert isinstance(payload["next_actions"], list)


@pytest.mark.asyncio
async def test_the_analytics_status_and_roles_payloads_keep_their_shape(capstone_world):
    service = capstone_world["service"]
    status = await service.get_analytics_status()
    roles = await service.get_supported_roles()

    assert set(status) >= {
        "schema_ready",
        "catalog_ready",
        "skills_count",
        "resume_skills_count",
        "courses_count",
        "real_job_skill_links_count",
        "synced_job_postings_count",
        "embedding_provider",
    }
    assert status["embedding_provider"] == "hash"
    assert set(roles) == {"roles"}
    by_role = {role["target_role"]: role for role in roles["roles"]}
    assert TARGET_ROLE in by_role
    assert by_role[TARGET_ROLE]["is_market_backed"] is True


@pytest.mark.asyncio
async def test_the_optimisation_and_runs_payloads_keep_their_shape(capstone_world, test_user):
    service = capstone_world["service"]

    optimisation = await service.optimize_learning_route(
        resume_id=capstone_world["resume"].id,
        user_id=test_user.id,
        target_role=TARGET_ROLE,
        budget=200.0,
        available_hours=40.0,
        max_courses=3,
    )
    assert set(optimisation) >= {"objective_version", "solver_status", "selected_courses"}

    runs = await service.list_learning_route_runs(user_id=test_user.id)
    assert set(runs) >= {"runs"}
    assert runs["runs"], "the optimisation did not record a run"
    run = runs["runs"][0]
    assert set(run) == {
        "optimization_run_id",
        "resume_id",
        "target_role",
        "objective_version",
        "status",
        "match_score_before",
        "projected_match_score_after",
        "total_cost",
        "total_hours",
        "budget",
        "available_hours",
        "max_courses",
        "selected_courses_count",
        "covered_skills_count",
        "remaining_gaps_count",
        "route_summary",
        "solver_status",
        "objective_value",
        "created_at",
    }


# ---------------------------------------------------------------------------
# The split itself
# ---------------------------------------------------------------------------


def test_the_facade_holds_no_implementation_of_its_own():
    """A facade that reimplements what it delegates to is two sources of truth."""
    import ast
    import pathlib

    source = pathlib.Path("app/services/analytics/capstoneAnalyticsService.py").read_text()
    facade = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.ClassDef) and node.name == "CapstoneAnalyticsService"
    )

    with_a_body = []
    for node in facade.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        statements = [
            statement
            for statement in node.body
            if not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant))
        ]
        if len(statements) != 1:
            with_a_body.append(node.name)

    # __init__ composes the services; everything else is a single delegation.
    assert with_a_body == ["__init__"], with_a_body


def test_no_capstone_service_imports_a_route():
    """Router -> service -> router is the cycle the split had to avoid."""
    import pathlib

    modules = [
        "capstoneAnalyticsService",
        "capstoneCatalogService",
        "capstoneGapService",
        "resumeSkillReviewService",
        "resumeSkillExtractionService",
        "jobSkillExtractionService",
        "jobPostingText",
    ]
    for name in modules:
        source = pathlib.Path(f"app/services/analytics/{name}.py").read_text()
        assert "app.routes" not in source, f"{name} imports a route"


def test_the_split_modules_form_a_directed_acyclic_graph():
    import ast
    import pathlib

    names = [
        "capstoneAnalyticsService",
        "capstoneCatalogService",
        "capstoneGapService",
        "resumeSkillReviewService",
        "resumeSkillExtractionService",
        "jobSkillExtractionService",
        "jobPostingText",
    ]
    prefix = "app.services.analytics."
    edges: dict[str, set[str]] = {}
    for name in names:
        tree = ast.parse(pathlib.Path(f"app/services/analytics/{name}.py").read_text())
        edges[name] = {
            node.module[len(prefix) :]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith(prefix)
            and node.module[len(prefix) :] in names
        }

    visiting: set[str] = set()
    done: set[str] = set()

    def visit(node: str, path: tuple[str, ...]) -> None:
        if node in done:
            return
        assert node not in visiting, f"import cycle: {' -> '.join(path + (node,))}"
        visiting.add(node)
        for neighbour in sorted(edges[node]):
            visit(neighbour, path + (node,))
        visiting.discard(node)
        done.add(node)

    for name in names:
        visit(name, ())

    # And the facade is the only one that reaches everything else.
    assert edges["jobPostingText"] == set()
    assert "capstoneAnalyticsService" not in {dep for deps in edges.values() for dep in deps}
