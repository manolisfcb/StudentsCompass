"""Catalog skill vectors, embedded once and read back from the database.

Plan 11, D3 / TASK-074. A skill's vector depends only on what the catalog says
about it — name and category — so it is the same for every analysis and every
user. It is generated once per (skill, model), stored in ``skill_embeddings``,
and regenerated only when its fingerprint stops matching: the catalog entry was
edited, the model changed, or the fingerprint recipe was bumped.

Per-occurrence evidence text is deliberately **not** part of the vector. It
differs per CV and per posting, so including it would make the vector
uncacheable; and the seed catalog's evidence is templated ("X is part of the
Data Analyst seed profile"), which pulls every seed skill towards the same
point and inflates their mutual similarity.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skillEmbeddingModel import SkillEmbedding
from app.models.skillModel import SkillModel
from app.services.analytics.embeddingService import (
    EMBEDDING_COLUMN_DIMS,
    FINGERPRINT_VERSION,
    HASH_MODEL_NAME,
    compute_text_fingerprint,
    generate_embeddings_batch,
    get_effective_model_name,
)

LOGGER = logging.getLogger(__name__)

#: One provider request carries up to 100 inputs; one batch here is one request.
SYNC_BATCH_SIZE = 100


def catalog_skill_text(skill: Any) -> str:
    """The text a catalog skill is embedded from.

    Accepts a ``SkillModel`` or the skill dicts the analytics services pass
    around. Name and category only — see the module docstring for why evidence
    is left out.
    """

    def field(name: str) -> Any:
        return skill.get(name) if isinstance(skill, dict) else getattr(skill, name, None)

    parts = [field("display_name"), field("normalized_name"), field("category")]
    return " ".join(str(part) for part in parts if part)


def _as_uuid(value: Any) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


@dataclass(frozen=True)
class SkillEmbeddingSyncReport:
    model_name: str
    skills_seen: int
    embedded: int
    already_current: int
    stored: bool
    message: str


class SkillEmbeddingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_vectors(
        self, skills: Iterable[Any], *, embed_missing: bool = True
    ) -> dict[UUID, list[float]]:
        """Vectors of ``skills`` in the configured model's space, by skill id.

        One SELECT for every skill at once. Skills with no current vector are
        embedded in batched provider calls and stored, unless ``embed_missing``
        is off. A skill is absent from the result when no vector of the
        configured model could be had: under hash, or when the provider fell
        back — a fallback vector is never stored or returned.
        """
        model_name = get_effective_model_name()
        if model_name == HASH_MODEL_NAME:
            return {}

        texts: dict[UUID, str] = {}
        for skill in skills:
            skill_id = skill.get("skill_id") if isinstance(skill, dict) else skill.id
            text = catalog_skill_text(skill)
            if skill_id is not None and text:
                texts[_as_uuid(skill_id)] = text
        if not texts:
            return {}

        fingerprints = {
            skill_id: compute_text_fingerprint(text, model_name=model_name)
            for skill_id, text in texts.items()
        }
        result = await self.session.execute(
            select(SkillEmbedding).where(
                SkillEmbedding.skill_id.in_(list(texts)),
                SkillEmbedding.model_name == model_name,
            )
        )
        vectors: dict[UUID, list[float]] = {}
        for row in result.scalars().all():
            if (
                row.text_fingerprint == fingerprints.get(row.skill_id)
                and row.fingerprint_version == FINGERPRINT_VERSION
            ):
                vectors[row.skill_id] = list(row.embedding)

        missing = [skill_id for skill_id in texts if skill_id not in vectors]
        if not missing or not embed_missing:
            return vectors

        for start in range(0, len(missing), SYNC_BATCH_SIZE):
            chunk = missing[start : start + SYNC_BATCH_SIZE]
            generated = await generate_embeddings_batch([texts[skill_id] for skill_id in chunk])
            if generated is None:
                break
            chunk_vectors, produced_by = generated
            if produced_by != model_name:
                # The provider fell back. Storing the result would put a hash
                # vector in the model's space; returning it would compare two.
                LOGGER.warning(
                    "skill embeddings: provider fell back to %s; %d skill(s) left without a vector",
                    produced_by,
                    len(missing) - start,
                )
                break
            await self._upsert(
                [
                    (skill_id, vector, fingerprints[skill_id])
                    for skill_id, vector in zip(chunk, chunk_vectors)
                ],
                model_name=model_name,
            )
            vectors.update(zip(chunk, chunk_vectors))
        return vectors

    async def sync_catalog(self) -> SkillEmbeddingSyncReport:
        """Bring every catalog skill up to date for the configured model.

        Idempotent: a second run finds every fingerprint current and makes no
        provider call.
        """
        model_name = get_effective_model_name()
        result = await self.session.execute(
            select(
                SkillModel.id,
                SkillModel.display_name,
                SkillModel.normalized_name,
                SkillModel.category,
            ).order_by(SkillModel.normalized_name)
        )
        skills = [
            {
                "skill_id": row.id,
                "display_name": row.display_name,
                "normalized_name": row.normalized_name,
                "category": row.category,
            }
            for row in result.all()
        ]
        if model_name == HASH_MODEL_NAME:
            return SkillEmbeddingSyncReport(
                model_name=model_name,
                skills_seen=len(skills),
                embedded=0,
                already_current=0,
                stored=False,
                message="The configured provider produces hash vectors; nothing is stored for them.",
            )

        current = await self.get_vectors(skills, embed_missing=False)
        vectors = await self.get_vectors(skills, embed_missing=True)
        embedded = len(vectors) - len(current)
        left = len(skills) - len(vectors)
        return SkillEmbeddingSyncReport(
            model_name=model_name,
            skills_seen=len(skills),
            embedded=embedded,
            already_current=len(current),
            stored=True,
            message=(
                "Every catalog skill has a current vector."
                if left == 0
                else f"{left} skill(s) still have no vector: the provider was unavailable."
            ),
        )

    async def _upsert(
        self, rows: list[tuple[UUID, list[float], str]], *, model_name: str
    ) -> None:
        """Write ``rows`` atomically on (skill_id, model_name), then commit."""
        now = datetime.now(timezone.utc)
        values = [
            {
                "id": uuid4(),
                "skill_id": skill_id,
                "model_name": model_name,
                "dims": EMBEDDING_COLUMN_DIMS,
                "embedding": vector,
                "text_fingerprint": fingerprint,
                "fingerprint_version": FINGERPRINT_VERSION,
                "created_at": now,
                "updated_at": now,
            }
            for skill_id, vector, fingerprint in rows
        ]
        dialect = self.session.bind.dialect.name if self.session.bind is not None else ""
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as dialect_insert
        else:
            from sqlalchemy.dialects.sqlite import insert as dialect_insert

        statement = dialect_insert(SkillEmbedding).values(values)
        await self.session.execute(
            statement.on_conflict_do_update(
                index_elements=["skill_id", "model_name"],
                set_={
                    "dims": statement.excluded.dims,
                    "embedding": statement.excluded.embedding,
                    "text_fingerprint": statement.excluded.text_fingerprint,
                    "fingerprint_version": statement.excluded.fingerprint_version,
                    "updated_at": now,
                },
            )
        )
        await self.session.commit()
