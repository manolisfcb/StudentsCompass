"""Catalog skill vectors are embedded once and read back (TASK-074).

The point of ``skill_embeddings`` is that the provider is called once per skill
in its life, not once per analysis. These tests pin that a second sync costs no
call, that an edited skill is the only one re-embedded, and that a provider
fallback stores nothing in the model's space.
"""
from __future__ import annotations

import math
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app import config
from app.models.skillEmbeddingModel import SkillEmbedding
from app.models.skillModel import SkillModel
from app.services.analytics import embeddingService
from app.services.analytics.embeddingService import (
    FINGERPRINT_VERSION,
    compute_text_fingerprint,
    gemini_model_name,
    generate_hash_embedding,
)
from app.services.analytics.skillEmbeddingService import (
    SkillEmbeddingService,
    catalog_skill_text,
)


class FakeGeminiModels:
    def __init__(self):
        self.error: Exception | None = None
        self.inputs: list[str] = []
        self.calls = 0

    async def embed_content(self, *, model, contents, config):
        self.calls += 1
        if self.error is not None:
            raise self.error
        self.inputs.extend(contents)
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=generate_hash_embedding(text)) for text in contents]
        )


@pytest.fixture
def gemini(monkeypatch):
    models = FakeGeminiModels()
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "gemini")
    monkeypatch.setenv("GENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "AI_KILL_SWITCH", False)
    monkeypatch.setattr(
        embeddingService,
        "_get_gemini_client",
        lambda: SimpleNamespace(aio=SimpleNamespace(models=models)),
    )
    return models


async def _skills(session, *names: str) -> list[SkillModel]:
    skills = [
        SkillModel(
            id=uuid.uuid4(),
            normalized_name=name.lower().replace(" ", "_"),
            display_name=name,
            category="tools",
            source="manual",
        )
        for name in names
    ]
    session.add_all(skills)
    await session.commit()
    return skills


async def _row_count(session) -> int:
    return int((await session.execute(select(func.count(SkillEmbedding.id)))).scalar_one())


def test_the_catalog_text_leaves_evidence_out():
    skill = {
        "display_name": "Python",
        "normalized_name": "python",
        "category": "programming",
        "evidence_text": "Python is part of the Data Analyst seed profile.",
    }
    assert catalog_skill_text(skill) == "Python python programming"


@pytest.mark.asyncio
async def test_a_second_sync_makes_no_provider_call(db_session, gemini):
    await _skills(db_session, "Python", "SQL", "Tableau")
    service = SkillEmbeddingService(db_session)

    first = await service.sync_catalog()
    calls_after_first = gemini.calls
    second = await service.sync_catalog()

    assert (first.embedded, first.already_current) == (3, 0)
    assert (second.embedded, second.already_current) == (0, 3)
    assert gemini.calls == calls_after_first == 1
    assert await _row_count(db_session) == 3


@pytest.mark.asyncio
async def test_stored_rows_carry_model_fingerprint_and_unit_vectors(db_session, gemini):
    (skill,) = await _skills(db_session, "Power BI")

    await SkillEmbeddingService(db_session).sync_catalog()

    row = (await db_session.execute(select(SkillEmbedding))).scalar_one()
    assert row.skill_id == skill.id
    assert row.model_name == gemini_model_name()
    assert row.fingerprint_version == FINGERPRINT_VERSION
    assert row.text_fingerprint == compute_text_fingerprint(
        catalog_skill_text(skill), model_name=gemini_model_name()
    )
    assert math.sqrt(sum(value * value for value in row.embedding)) == pytest.approx(1.0, abs=1e-6)


@pytest.mark.asyncio
async def test_only_an_edited_skill_is_embedded_again(db_session, gemini):
    python, sql = await _skills(db_session, "Python", "SQL")
    service = SkillEmbeddingService(db_session)
    await service.sync_catalog()
    gemini.inputs.clear()

    sql.display_name = "Structured Query Language"
    await db_session.commit()
    report = await service.sync_catalog()

    assert report.embedded == 1
    assert gemini.inputs == [catalog_skill_text(sql)]
    assert await _row_count(db_session) == 2


@pytest.mark.asyncio
async def test_get_vectors_reads_stored_vectors_and_embeds_only_the_missing(db_session, gemini):
    python, sql, tableau = await _skills(db_session, "Python", "SQL", "Tableau")
    service = SkillEmbeddingService(db_session)
    await service.get_vectors([python, sql])
    gemini.inputs.clear()

    # String ids, as some callers carry them, resolve to the same rows.
    vectors = await service.get_vectors(
        [
            {"skill_id": str(python.id), "display_name": "Python", "normalized_name": "python", "category": "tools"},
            sql,
            tableau,
        ]
    )

    assert set(vectors) == {python.id, sql.id, tableau.id}
    assert gemini.inputs == [catalog_skill_text(tableau)]


@pytest.mark.asyncio
async def test_a_fallback_stores_and_returns_nothing(db_session, gemini):
    await _skills(db_session, "Python", "SQL")
    gemini.error = RuntimeError("503 UNAVAILABLE")

    report = await SkillEmbeddingService(db_session).sync_catalog()

    assert report.embedded == 0
    assert "unavailable" in report.message
    assert await _row_count(db_session) == 0


@pytest.mark.asyncio
async def test_under_hash_nothing_is_stored(db_session, monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "hash")
    skills = await _skills(db_session, "Python")
    service = SkillEmbeddingService(db_session)

    report = await service.sync_catalog()

    assert report.stored is False
    assert await service.get_vectors(skills) == {}
    assert await _row_count(db_session) == 0


@pytest.mark.asyncio
async def test_a_new_model_gets_its_own_rows(db_session, gemini, monkeypatch):
    await _skills(db_session, "Python")
    service = SkillEmbeddingService(db_session)
    await service.sync_catalog()

    monkeypatch.setattr(embeddingService, "GEMINI_EMBEDDING_MODEL", "gemini-embedding-002")
    await service.sync_catalog()

    names = set((await db_session.execute(select(SkillEmbedding.model_name))).scalars())
    assert names == {"gemini-embedding-001@384", "gemini-embedding-002@384"}


# ---------------------------------------------------------------------------
# The matcher reads stored vectors (TASK-075)
# ---------------------------------------------------------------------------


def _as_dicts(skills: list[SkillModel]) -> list[dict]:
    return [
        {
            "skill_id": skill.id,
            "display_name": skill.display_name,
            "normalized_name": skill.normalized_name,
            "category": skill.category,
            "importance_score": 1.0,
        }
        for skill in skills
    ]


@pytest.mark.asyncio
async def test_an_analysis_over_an_embedded_catalog_calls_no_provider(db_session, gemini):
    from app.services.analytics.semanticMatchingService import SemanticMatchingService

    skills = await _skills(db_session, "Tableau", "Python", "Power BI", "Kubernetes")
    await SkillEmbeddingService(db_session).sync_catalog()
    calls_before = gemini.calls
    current, required = _as_dicts(skills[:2]), _as_dicts(skills[2:])

    await SemanticMatchingService(session=db_session).analyze_required_skill_matches(
        current_skills=current, required_skills=required
    )

    assert gemini.calls == calls_before


@pytest.mark.asyncio
async def test_a_never_embedded_skill_costs_one_batched_call_then_none(db_session, gemini):
    from app.services.analytics.semanticMatchingService import SemanticMatchingService

    skills = await _skills(db_session, "Tableau", "Python", "Power BI", "Kubernetes")
    current, required = _as_dicts(skills[:2]), _as_dicts(skills[2:])
    service = SemanticMatchingService(session=db_session)

    await service.analyze_required_skill_matches(current_skills=current, required_skills=required)
    assert gemini.calls == 1  # four skills, one request
    await service.analyze_required_skill_matches(current_skills=current, required_skills=required)
    assert gemini.calls == 1


@pytest.mark.asyncio
async def test_stored_vectors_give_the_same_result_as_embedding_in_the_request(db_session, gemini):
    from app.services.analytics.semanticMatchingService import SemanticMatchingService

    skills = await _skills(db_session, "Tableau", "Python", "Power BI", "Kubernetes", "Excel")
    current, required = _as_dicts(skills[:3]), _as_dicts(skills[3:])

    stored = await SemanticMatchingService(session=db_session).analyze_required_skill_matches(
        current_skills=current, required_skills=required
    )
    in_request = await SemanticMatchingService().analyze_required_skill_matches(
        current_skills=current, required_skills=required
    )

    assert stored == in_request
