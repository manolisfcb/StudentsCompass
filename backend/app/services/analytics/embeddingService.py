from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import logging
import os
import re
from functools import lru_cache
from uuid import UUID

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resumeEmbeddingsModel import ResumeEmbedding

LOGGER = logging.getLogger(__name__)

MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIMS = int(os.getenv("EMBEDDING_DIMS", "384"))
# Stored as the model_name for hash-fallback vectors so they never share a
# (resume_id, model_name) key with real sentence-transformer embeddings.
HASH_MODEL_NAME = "hash-v1"
DEFAULT_EMBEDDINGS_PROVIDER = "hash"
LOCAL_PROVIDER_NAMES = {"local", "sentence-transformers", "sentence_transformers"}
_EMBEDDING_METRICS = {
    "local_failure_count": 0,
    "fallback_to_hash_count": 0,
    "unknown_provider_fallback_count": 0,
}


def get_embedding_provider() -> str:
    return os.getenv("EMBEDDINGS_PROVIDER", DEFAULT_EMBEDDINGS_PROVIDER).strip().lower()


def is_embedding_generation_enabled() -> bool:
    return get_embedding_provider() not in {"", "0", "false", "off", "disabled", "none"}


def get_effective_model_name() -> str:
    """Model name under which embeddings are stored for the configured provider.

    Mirrors the model name reported by ``generate_embedding_with_model`` so that
    corpus searches query the matching vector space (hash vectors never share a
    space with sentence-transformer vectors).
    """
    return MODEL_NAME if get_embedding_provider() in LOCAL_PROVIDER_NAMES else HASH_MODEL_NAME


def get_embedding_status() -> dict:
    provider = get_embedding_provider()
    local_package_available = importlib.util.find_spec("sentence_transformers") is not None
    local_configured = provider in LOCAL_PROVIDER_NAMES
    return {
        "enabled": is_embedding_generation_enabled(),
        "provider": provider,
        "model_name": MODEL_NAME,
        "dims": EMBEDDING_DIMS,
        "semantic_matching_ready": local_configured and local_package_available,
        "local_provider_configured": local_configured,
        "local_package_available": local_package_available,
        "fallback_provider": "hash",
        "model_cache_strategy": "lru_cache_process_memory",
        "local_model_cache_dir": os.getenv("SENTENCE_TRANSFORMERS_HOME") or os.getenv("HF_HOME"),
        "local_failure_count": _EMBEDDING_METRICS["local_failure_count"],
        "fallback_to_hash_count": _EMBEDDING_METRICS["fallback_to_hash_count"],
        "unknown_provider_fallback_count": _EMBEDDING_METRICS["unknown_provider_fallback_count"],
        "production_recommendation": (
            "Use EMBEDDINGS_PROVIDER=local with sentence-transformers installed and model cache warmed."
            if provider == "hash"
            else "Monitor fallback_to_hash_count and local_failure_count before relying on semantic scoring."
        ),
    }


async def generate_embedding_with_model(text: str) -> tuple[list[float], str] | None:
    """Generate an embedding and report the model name actually used.

    The returned model name distinguishes a real sentence-transformer vector
    from a hash-fallback vector (including the local -> hash fallback path), so
    callers can persist them under separate keys.
    """
    clean_text = (text or "").strip()
    if not clean_text or not is_embedding_generation_enabled():
        return None

    provider = get_embedding_provider()
    if provider in LOCAL_PROVIDER_NAMES:
        try:
            vector = await asyncio.to_thread(_generate_local_embedding, clean_text)
            return vector, MODEL_NAME
        except Exception as exc:  # noqa: BLE001
            _EMBEDDING_METRICS["local_failure_count"] += 1
            _EMBEDDING_METRICS["fallback_to_hash_count"] += 1
            LOGGER.warning(
                "Local embedding provider failed; falling back to hash embeddings. error=%s",
                exc,
            )
            return generate_hash_embedding(clean_text), HASH_MODEL_NAME

    if provider == "hash":
        return generate_hash_embedding(clean_text), HASH_MODEL_NAME

    LOGGER.warning("Unknown EMBEDDINGS_PROVIDER=%s. Falling back to hash embeddings.", provider)
    _EMBEDDING_METRICS["unknown_provider_fallback_count"] += 1
    _EMBEDDING_METRICS["fallback_to_hash_count"] += 1
    return generate_hash_embedding(clean_text), HASH_MODEL_NAME


async def generate_embedding(text: str) -> list[float] | None:
    result = await generate_embedding_with_model(text)
    return result[0] if result else None


class ResumeEmbeddingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_resume_embedding_from_text(
        self,
        *,
        resume_id: UUID,
        text: str | None,
        model_name: str | None = None,
    ) -> ResumeEmbedding | None:
        result = await generate_embedding_with_model(text or "")
        if result is None:
            return None
        embedding, effective_model_name = result
        return await self.upsert_resume_embedding(
            resume_id=resume_id,
            model_name=model_name or effective_model_name,
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

    async def find_similar_resumes(
        self,
        *,
        resume_id: UUID,
        k: int = 10,
        model_name: str | None = None,
    ) -> list[dict]:
        """Return the ``k`` nearest stored resume embeddings by cosine distance.

        Uses pgvector's native ``<=>`` operator (via ``cosine_distance``) so the
        ranking runs in the database against the HNSW index instead of pulling
        every vector into Python. Always filters by ``model_name`` to compare
        within a single vector space. Requires a PostgreSQL backend with the
        ``vector`` extension; not supported on SQLite.
        """
        effective_model = model_name or get_effective_model_name()
        source = await self.session.execute(
            select(ResumeEmbedding.embedding).where(
                ResumeEmbedding.resume_id == resume_id,
                ResumeEmbedding.model_name == effective_model,
            )
        )
        query_vector = source.scalar_one_or_none()
        if query_vector is None:
            return []

        distance = ResumeEmbedding.embedding.cosine_distance(query_vector)
        result = await self.session.execute(
            select(ResumeEmbedding.resume_id, distance.label("distance"))
            .where(
                ResumeEmbedding.model_name == effective_model,
                ResumeEmbedding.resume_id != resume_id,
            )
            .order_by(distance.asc())
            .limit(k)
        )
        return [
            {"resume_id": row.resume_id, "similarity": round(1.0 - float(row.distance), 6)}
            for row in result.all()
        ]


def generate_hash_embedding(text: str, dims: int = EMBEDDING_DIMS) -> list[float]:
    tokens = re.findall(r"[a-z0-9+#]+", text.lower())
    if not tokens:
        return [0.0 for _ in range(dims)]

    # Hashing each token still needs a Python loop (the SHA256 cost dominates),
    # but the accumulation/normalization is vectorized with numpy. np.bincount
    # adds weights in token order, matching the original sequential accumulation.
    indices = np.empty(len(tokens), dtype=np.int64)
    weights = np.empty(len(tokens), dtype=np.float64)
    for i, token in enumerate(tokens):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        indices[i] = int.from_bytes(digest[:4], "big") % dims
        sign = 1.0 if digest[4] % 2 else -1.0
        weights[i] = sign * (1.0 + min(len(token), 20) / 20.0)

    vector = np.bincount(indices, weights=weights, minlength=dims)
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return vector.tolist()
    return np.round(vector / norm, 8).tolist()


@lru_cache(maxsize=1)
def _load_sentence_transformer():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def _generate_local_embedding(text: str) -> list[float]:
    model = _load_sentence_transformer()
    vector = model.encode(text, normalize_embeddings=True)
    return [float(value) for value in vector]
