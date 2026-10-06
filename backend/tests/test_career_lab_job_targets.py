"""Paste a job description, get its deterministic analysis (TASK-078, TASK-079)."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app import config
from app.models.jobTargetModel import JobDescriptionParseModel, JobTargetModel
from app.models.resumeModel import ResumeModel
from app.services.analytics import embeddingService
from app.services.analytics.capstoneAnalyticsSeedService import seed_capstone_analytics_minimum
from app.services.analytics.embeddingService import generate_hash_embedding
from app.services.analytics.skillExtractionService import SkillExtractionService
from app.services.careerLab import jobTargetAnalysisService as analysis
from app.services.careerLab.jobDescriptionRules import (
    PREFERRED,
    REQUIRED,
    detect_min_years,
    detect_title,
    detect_workplace_type,
    parse_job_description,
)

POSTING = """Junior Data Analyst

About the role
You will turn sales data into decisions for regional managers.

Requirements:
- 1+ years writing SQL against a warehouse
- Python for data cleaning
- Tableau dashboards for stakeholders

Nice to have:
- Power BI
- Statistics background

Hybrid role based in Toronto.
"""
SUMMARY = (
    "Business student with 1 year of experience as a data analyst intern. "
    "Built SQL queries and Python scripts, and Tableau dashboards for managers."
)


async def _resume(session, user_id, *, summary: str | None = SUMMARY) -> ResumeModel:
    resume = ResumeModel(
        view_url=f"https://storage.example/{uuid.uuid4().hex}.pdf",
        user_id=user_id,
        storage_file_id=f"resumes/{uuid.uuid4().hex}.pdf",
        original_filename="resume.pdf",
        folder_id="resumes",
        ai_summary=summary,
    )
    session.add(resume)
    await session.commit()
    await session.refresh(resume)
    return resume


@pytest.fixture
def hash_provider(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "hash")


# ---------------------------------------------------------------------------
# The rules parse
# ---------------------------------------------------------------------------


def test_title_years_and_workplace_are_read_from_the_posting():
    lines = POSTING.split("\n")
    assert detect_title(lines) == "Junior Data Analyst"
    assert detect_min_years(POSTING) == 1
    assert detect_workplace_type(POSTING) == "hybrid"


@pytest.mark.asyncio
async def test_requirements_are_split_into_required_and_nice_to_have(db_session, hash_provider):
    await seed_capstone_analytics_minimum(db_session)

    parsed = await parse_job_description(POSTING, extractor=SkillExtractionService(db_session))

    by_name = {item.normalized_name: item.requirement for item in parsed.requirements}
    assert by_name["sql"] == REQUIRED
    assert by_name["python"] == REQUIRED
    assert by_name["tableau"] == REQUIRED
    assert by_name["power_bi"] == PREFERRED
    # Mentioned only in the intro of a posting that has a requirements section.
    assert by_name["sales"] == PREFERRED
    assert parsed.seniority == "junior"


@pytest.mark.asyncio
async def test_a_posting_without_sections_is_all_required(db_session, hash_provider):
    await seed_capstone_analytics_minimum(db_session)
    text = "Data Analyst\n\nWe use SQL and Python every day, and Tableau for reporting.\n"

    parsed = await parse_job_description(text, extractor=SkillExtractionService(db_session))

    assert {item.requirement for item in parsed.requirements} == {REQUIRED}


@pytest.mark.asyncio
async def test_a_skill_required_anywhere_stays_required(db_session, hash_provider):
    await seed_capstone_analytics_minimum(db_session)
    text = "Analyst\n\nRequirements:\nSQL\n\nNice to have:\nSQL and Power BI\n"

    parsed = await parse_job_description(text, extractor=SkillExtractionService(db_session))

    by_name = {item.normalized_name: item.requirement for item in parsed.requirements}
    assert by_name["sql"] == REQUIRED


def test_the_body_wording_does_not_set_the_level():
    from app.services.careerLab.jobDescriptionRules import detect_seniority

    assert detect_seniority("Data Analyst") is None
    assert detect_seniority("Senior Data Analyst") == "senior"


# ---------------------------------------------------------------------------
# The score: components, weights, bands
# ---------------------------------------------------------------------------


def test_an_unavailable_component_spreads_its_weight():
    combined = analysis.combine({"skills": 0.8, "context": None, "title": 1.0, "seniority": 1.0})

    weights = combined["effective_weights"]
    assert weights["context"] == 0.0
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-3)
    # 0.45, 0.20, 0.10 renormalised over 0.75.
    assert combined["score"] == pytest.approx((0.45 * 0.8 + 0.20 + 0.10) / 0.75, abs=1e-3)


def test_no_signal_at_all_is_no_score_rather_than_zero():
    combined = analysis.combine({name: None for name in analysis.COMPONENTS})
    assert combined["score"] is None
    assert analysis.band_for(None) is None


@pytest.mark.parametrize(("score", "band"), [(0.71, "strong_match"), (0.5, "match"), (0.2, "weak_match")])
def test_bands(score, band):
    assert analysis.band_for(score) == band


def test_weights_come_from_configuration(monkeypatch):
    monkeypatch.setattr(config, "JOB_MATCH_WEIGHTS", (1.0, 0.0, 0.0, 0.0))
    combined = analysis.combine({"skills": 0.3, "context": 0.9, "title": 0.9, "seniority": 0.9})
    assert combined["score"] == pytest.approx(0.3)


@pytest.mark.parametrize(
    ("asked", "has", "fit"),
    [("junior", "junior", 1.0), ("junior", "senior", 1.0), ("mid", "junior", 0.5), ("senior", "junior", 0.0), (None, "junior", None)],
)
def test_seniority_fit(asked, has, fit):
    assert analysis.seniority_fit(asked, has) == fit


def test_cv_seniority_reads_years_or_student_status():
    assert analysis.cv_seniority("3 years of experience in analytics") == "mid"
    assert analysis.cv_seniority("Undergraduate student in economics") == "junior"
    assert analysis.cv_seniority("Built dashboards.") is None


def test_title_affinity_ignores_level_words():
    assert analysis.title_affinity("Senior Data Analyst", "worked as a data analyst") == 1.0
    assert analysis.title_affinity("Data Engineer", "worked as a data analyst") == 0.5
    assert analysis.title_affinity("Data Engineer", "") is None


# ---------------------------------------------------------------------------
# The endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pasting_a_posting_returns_its_analysis(client, db_session, test_user, auth_headers, hash_provider):
    await seed_capstone_analytics_minimum(db_session)
    resume = await _resume(db_session, test_user.id)

    response = await client.post(
        "/api/v1/career-lab/job-targets",
        json={"text": POSTING, "resume_id": str(resume.id)},
        headers=auth_headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "ready"
    assert body["title"] == "Junior Data Analyst"
    assert body["workplace_type"] == "hybrid"
    result = body["analysis"]
    # Never a bare number: band and breakdown always come with it.
    assert result["score"] is not None and result["band"] in {"strong_match", "match", "weak_match"}
    assert set(result["components"]) == {"skills", "context", "title", "seniority"}
    # Under hash there is no semantic signal: the context component says so.
    assert result["components"]["context"]["available"] is False
    assert result["context"]["level"] == "unavailable"
    assert result["semantic_matching_ready"] is False
    strengths = {item["display_name"] for item in result["strengths"]}
    assert {"SQL", "Python", "Tableau"} <= strengths
    gaps = {item["display_name"]: item for item in result["gaps"]}
    assert "Power BI" in gaps and gaps["Power BI"]["requirement"] == "preferred"
    # SQL, Python, Tableau and Data Cleaning are asked for; the CV shows three.
    assert result["requirements"]["required"] == 4
    assert result["requirements"]["required_covered"] == 3
    assert gaps["Data Cleaning"]["requirement"] == "required"
    assert gaps["Data Cleaning"]["priority_rank"] == 1
    assert result["seniority"] == {"asked": "junior", "cv": "junior", "min_years": 1}


@pytest.mark.asyncio
async def test_two_users_pasting_the_same_posting_share_one_parse(
    client, db_session, test_user, auth_headers, hash_provider
):
    await seed_capstone_analytics_minimum(db_session)
    resume = await _resume(db_session, test_user.id)
    for _ in range(2):
        response = await client.post(
            "/api/v1/career-lab/job-targets",
            json={"text": POSTING, "resume_id": str(resume.id)},
            headers=auth_headers,
        )
        assert response.status_code == 201

    targets = await db_session.scalar(select(func.count()).select_from(JobTargetModel))
    parses = await db_session.scalar(select(func.count()).select_from(JobDescriptionParseModel))
    assert (targets, parses) == (2, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["too short", "x" * 20_001])
async def test_the_text_is_bounded(client, db_session, test_user, auth_headers, text):
    resume = await _resume(db_session, test_user.id)

    response = await client.post(
        "/api/v1/career-lab/job-targets",
        json={"text": text, "resume_id": str(resume.id)},
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert await db_session.scalar(select(func.count()).select_from(JobTargetModel)) == 0


@pytest.mark.asyncio
async def test_someone_elses_cv_is_not_found(client, db_session, auth_headers):
    from app.models.userModel import User

    stranger = User(
        id=uuid.uuid4(), email="stranger@example.invalid", hashed_password="x",
        is_active=True, is_superuser=False, is_verified=True,
    )
    db_session.add(stranger)
    await db_session.commit()
    resume = await _resume(db_session, stranger.id)

    response = await client.post(
        "/api/v1/career-lab/job-targets",
        json={"text": POSTING, "resume_id": str(resume.id)},
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_a_retried_post_files_the_vacancy_once(client, db_session, test_user, auth_headers, hash_provider):
    await seed_capstone_analytics_minimum(db_session)
    resume = await _resume(db_session, test_user.id)
    headers = {**auth_headers, "Idempotency-Key": f"paste-{uuid.uuid4().hex}"}
    payload = {"text": POSTING, "resume_id": str(resume.id)}

    first = await client.post("/api/v1/career-lab/job-targets", json=payload, headers=headers)
    second = await client.post("/api/v1/career-lab/job-targets", json=payload, headers=headers)

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert await db_session.scalar(select(func.count()).select_from(JobTargetModel)) == 1


@pytest.mark.asyncio
async def test_list_and_reopen_are_owner_scoped(client, db_session, test_user, auth_headers, hash_provider):
    await seed_capstone_analytics_minimum(db_session)
    resume = await _resume(db_session, test_user.id)
    created = await client.post(
        "/api/v1/career-lab/job-targets",
        json={"text": POSTING, "resume_id": str(resume.id)},
        headers=auth_headers,
    )
    target_id = created.json()["id"]

    listing = await client.get("/api/v1/career-lab/job-targets", headers=auth_headers)
    reopened = await client.get(f"/api/v1/career-lab/job-targets/{target_id}", headers=auth_headers)
    missing = await client.get(f"/api/v1/career-lab/job-targets/{uuid.uuid4()}", headers=auth_headers)

    assert listing.status_code == 200
    (row,) = listing.json()["items"]
    assert row["id"] == target_id and row["band"] == created.json()["band"]
    assert "raw_text" not in row
    assert reopened.json()["analysis"] == created.json()["analysis"]
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_a_failed_analysis_keeps_the_vacancy_with_a_reason(
    client, db_session, test_user, auth_headers, hash_provider, monkeypatch
):
    await seed_capstone_analytics_minimum(db_session)
    resume = await _resume(db_session, test_user.id)

    async def broken(self, target, resume):
        raise RuntimeError("boom")

    monkeypatch.setattr(analysis.JobTargetAnalysisService, "analyze", broken)
    response = await client.post(
        "/api/v1/career-lab/job-targets",
        json={"text": POSTING, "resume_id": str(resume.id)},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    assert body["analysis"] is None
    assert "boom" not in (body["error_message"] or "")


@pytest.mark.asyncio
async def test_with_a_real_provider_context_counts_and_the_posting_is_embedded_once(
    client, db_session, test_user, auth_headers, monkeypatch
):
    calls: list[list[str]] = []

    async def embed_content(*, model, contents, config):
        calls.append(list(contents))
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=generate_hash_embedding(t)) for t in contents]
        )

    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "gemini")
    monkeypatch.setenv("GENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "AI_KILL_SWITCH", False)
    monkeypatch.setattr(
        embeddingService,
        "_get_gemini_client",
        lambda: SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(embed_content=embed_content))),
    )
    await seed_capstone_analytics_minimum(db_session)
    resume = await _resume(db_session, test_user.id)

    first = await client.post(
        "/api/v1/career-lab/job-targets",
        json={"text": POSTING, "resume_id": str(resume.id)},
        headers=auth_headers,
    )
    calls_after_first = len(calls)
    second = await client.post(
        "/api/v1/career-lab/job-targets",
        json={"text": POSTING, "resume_id": str(resume.id)},
        headers=auth_headers,
    )

    assert first.status_code == second.status_code == 201
    context = first.json()["analysis"]["components"]["context"]
    assert context["available"] is True
    parse = (await db_session.execute(select(JobDescriptionParseModel))).scalar_one()
    assert parse.embedding_model_name == "gemini-embedding-001@384"
    # Same posting, same CV: posting, CV and skill vectors all come from storage.
    assert len(calls) == calls_after_first


def test_the_embedded_role_text_leaves_the_employer_out():
    from app.services.careerLab.jobDescriptionRules import role_text

    posting = (
        "About Acme\nAcme is the leading platform for widgets.\n"
        "What you'll do\nBuild SQL models for finance.\n"
        "Benefits\nUnlimited PTO and a gym stipend.\n"
        "Requirements\n2+ years of SQL.\n"
        "Acme is an equal opportunity employer.\n"
    )

    text = role_text("Data Analyst", posting)

    assert text.startswith("Data Analyst")
    assert "Build SQL models" in text and "2+ years of SQL" in text
    assert "widgets" not in text and "gym" not in text


def test_a_posting_the_catalogue_barely_reads_cannot_carry_the_score_on_skills():
    one_skill = [{"importance_score": 1.0}]
    evidence = analysis.skill_evidence(one_skill)
    thin = analysis.combine(
        {"skills": 1.0, "context": 0.1, "title": 0.0, "seniority": 0.0},
        confidence={"skills": evidence},
    )
    full = analysis.combine({"skills": 1.0, "context": 0.1, "title": 0.0, "seniority": 0.0})

    assert evidence == pytest.approx(1 / 3, abs=1e-3)
    assert thin["score"] < full["score"]
    assert thin["effective_weights"]["skills"] < full["effective_weights"]["skills"]
    assert analysis.skill_evidence([{"importance_score": 1.0}] * 3) == 1.0
