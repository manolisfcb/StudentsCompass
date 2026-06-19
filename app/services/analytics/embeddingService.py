from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import os
import re
from functools import lru_cache
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resumeEmbeddingsModel import ResumeEmbedding

LOGGER = logging.getLogger(__name__)

MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIMS = int(os.getenv("EMBEDDING_DIMS", "384"))
DEFAULT_EMBEDDINGS_PROVIDER = "hash"
LOCAL_PROVIDER_NAMES = {"local", "sentence-transformers", "sentence_transformers"}


def get_embedding_provider() -> str:
    return os.getenv("EMBEDDINGS_PROVIDER", DEFAULT_EMBEDDINGS_PROVIDER).strip().lower()


def is_embedding_generation_enabled() -> bool:
    return get_embedding_provider() not in {"", "0", "false", "off", "disabled", "none"}


def get_embedding_status() -> dict:
    provider = get_embedding_provider()
    return {
        "enabled": is_embedding_generation_enabled(),
        "provider": provider,
        "model_name": MODEL_NAME,
        "dims": EMBEDDING_DIMS,
        "semantic_matching_ready": provider in LOCAL_PROVIDER_NAMES,
    }


async def generate_embedding(text: str) -> list[float] | None:
    clean_text = (text or "").strip()
    if not clean_text or not is_embedding_generation_enabled():
        return None

    provider = get_embedding_provider()
    if provider in LOCAL_PROVIDER_NAMES:
        try:
            return await asyncio.to_thread(_generate_local_embedding, clean_text)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning(
                "Local embedding provider failed; falling back to hash embeddings. error=%s",
                exc,
            )
            return generate_hash_embedding(clean_text)

    if provider == "hash":
        return generate_hash_embedding(clean_text)

    LOGGER.warning("Unknown EMBEDDINGS_PROVIDER=%s. Falling back to hash embeddings.", provider)
    return generate_hash_embedding(clean_text)


class ResumeEmbeddingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_resume_embedding_from_text(
        self,
        *,
        resume_id: UUID,
        text: str | None,
        model_name: str = MODEL_NAME,
    ) -> ResumeEmbedding | None:
        embedding = await generate_embedding(text or "")
        if embedding is None:
            return None
        return await self.upsert_resume_embedding(
            resume_id=resume_id,
            model_name=model_name,
            dims=len(embedding),
            embedding=embedding,
        )

    async def upsert_resume_embedding(
        self,
        *,
        resume_id: UUID,
        model_name: str,
        dims: int,
        embedding: list[float],
    ) -> ResumeEmbedding:
        result = await self.session.execute(
            select(ResumeEmbedding).where(
                ResumeEmbedding.resume_id == resume_id,
                ResumeEmbedding.model_name == model_name,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.dims = dims
            existing.embedding = embedding
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        resume_embedding = ResumeEmbedding(
            resume_id=resume_id,
            model_name=model_name,
            dims=dims,
            embedding=embedding,
        )
        self.session.add(resume_embedding)
        await self.session.commit()
        await self.session.refresh(resume_embedding)
        return resume_embedding

    async def count_resume_embeddings(self) -> int:
        result = await self.session.execute(select(func.count(ResumeEmbedding.id)))
        return int(result.scalar_one() or 0)


def generate_hash_embedding(text: str, dims: int = EMBEDDING_DIMS) -> list[float]:
    tokens = re.findall(r"[a-z0-9+#]+", text.lower())
    vector = [0.0 for _ in range(dims)]

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dims
        sign = 1.0 if digest[4] % 2 else -1.0
        weight = 1.0 + min(len(token), 20) / 20.0
        vector[index] += sign * weight

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [round(value / norm, 8) for value in vector]


@lru_cache(maxsize=1)
def _load_sentence_transformer():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def _generate_local_embedding(text: str) -> list[float]:
    model = _load_sentence_transformer()
    vector = model.encode(text, normalize_embeddings=True)
    return [float(value) for value in vector]
