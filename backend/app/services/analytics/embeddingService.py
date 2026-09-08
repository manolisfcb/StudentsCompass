from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import logging
import os
import re
from datetime import datetime, timezone
from functools import lru_cache
from uuid import UUID, uuid4

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resumeEmbeddingsModel import ResumeEmbedding

LOGGER = logging.getLogger(__name__)

MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIMS = int(os.getenv("EMBEDDING_DIMS", "384"))
#: Width of ``resume_embeddings.embedding``. Fixed in the column type, so it
#: is not configurable: ``EMBEDDING_DIMS`` can be pointed at another model,
#: but a vector that does not fit the column is refused, not truncated.
EMBEDDING_COLUMN_DIMS = 384
# Stored as the model_name for hash-fallback vectors so they never share a
# (resume_id, model_name) key with real sentence-transformer embeddings.
HASH_MODEL_NAME = "hash-v1"
DEFAULT_EMBEDDINGS_PROVIDER = "hash"
LOCAL_PROVIDER_NAMES = {"local", "sentence-transformers", "sentence_transformers"}
#: Bumped when the fingerprint recipe changes. Every stored fingerprint carries
#: the version that produced it, so an old one simply stops matching and the
#: vector is regenerated once — no migration required, no silent reuse of a
#: fingerprint computed under different rules.
FINGERPRINT_VERSION = "v1"
_EMBEDDING_METRICS = {
    "local_failure_count": 0,
    "fallback_to_hash_count": 0,
    "unknown_provider_fallback_count": 0,
    "generation_skipped_count": 0,
    "generation_count": 0,
}


class EmbeddingDimensionMismatch(ValueError):
    """A provider returned a vector the column cannot hold.

    ``resume_embeddings.embedding`` is ``Vector(384)``. A vector of another
    width is refused here, with the numbers in the message, rather than at the
    driver as an opaque write error — or, on SQLite, silently stored and left to
    poison every similarity search made against it.
    """

    def __init__(self, *, model_name: str, produced: int, expected: int):
        super().__init__(
            f"model {model_name!r} produced a {produced}-dimension vector; "
            f"resume_embeddings.embedding holds {expected}"
        )
        self.model_name = model_name
        self.produced = produced
        self.expected = expected


def normalize_embedding_text(text: str | None) -> str:
    """The exact string a provider would be handed.

    Deliberately the same transformation ``generate_embedding_with_model``
    applies — a plain ``strip()`` — and nothing more. A looser normalisation
    (collapsing inner whitespace, lowercasing) would let two texts that produce
    *different* vectors share a fingerprint, and the skip would then serve a
    wrong vector. Under-normalising only costs a regeneration.
    """
    return (text or "").strip()


def compute_text_fingerprint(text: str | None, *, model_name: str) -> str:
    """Fingerprint of the text, the model and the scheme version.

    The model is part of the key because the same text under two models is two
    different vectors, and the version is part of it so this recipe can change
    without anything having to reinterpret old values.
    """
    payload = "\x00".join(
        (FINGERPRINT_VERSION, model_name, normalize_embedding_text(text))
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
        "generation_count": _EMBEDDING_METRICS["generation_count"],
        "generation_skipped_count": _EMBEDDING_METRICS["generation_skipped_count"],
        "fingerprint_version": FINGERPRINT_VERSION,
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

    async def _stored_embedding(
        self, resume_id: UUID, model_name: str, *, refresh: bool = False
    ) -> ResumeEmbedding | None:
        """The stored row, or ``None``.

        ``refresh`` reloads it over whatever the session already has. The upsert
        writes through Core, which does not go past the identity map, so without
        this a caller would be handed the pre-write object and conclude nothing
        had changed.
        """
        statement = select(ResumeEmbedding).where(
            ResumeEmbedding.resume_id == resume_id,
            ResumeEmbedding.model_name == model_name,
        )
        if refresh:
            statement = statement.execution_options(populate_existing=True)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def upsert_resume_embedding_from_text(
        self,
        *,
        resume_id: UUID,
        text: str | None,
        model_name: str | None = None,
    ) -> ResumeEmbedding | None:
        """Store the embedding of ``text``, generating it only if it would differ.

        The old order was: generate, then look, then write — every call paid for
        a vector and a commit even when nothing had changed. With the hash
        provider that is CPU; with the local model it is a sentence-transformer
        forward pass and the RSS that comes with it. Now the fingerprint of
        (text, model, scheme version) is compared *first*, and an identical
        request costs one SELECT and nothing else.

        A stored row whose fingerprint is NULL has no demonstrable provenance —
        it predates the column — so it is regenerated once and then carries one.
        """
        expected_model = model_name or get_effective_model_name()
        clean_text = normalize_embedding_text(text)
        if not clean_text or not is_embedding_generation_enabled():
            return None

        fingerprint = compute_text_fingerprint(clean_text, model_name=expected_model)
        existing = await self._stored_embedding(resume_id, expected_model)
        if (
            existing is not None
            and existing.text_fingerprint == fingerprint
            and existing.fingerprint_version == FINGERPRINT_VERSION
            and existing.embedding is not None
        ):
            _EMBEDDING_METRICS["generation_skipped_count"] += 1
            return existing

        result = await generate_embedding_with_model(clean_text)
        if result is None:
            return None
        _EMBEDDING_METRICS["generation_count"] += 1
        embedding, effective_model_name = result

        # The provider may have fallen back (local -> hash), which is a
        # different vector space and a different key. Fingerprint under the
        # model that actually produced the vector, never the one we hoped for.
        stored_model = model_name or effective_model_name
        return await self.upsert_resume_embedding(
            resume_id=resume_id,
            model_name=stored_model,
            dims=len(embedding),
            embedding=embedding,
            text_fingerprint=compute_text_fingerprint(clean_text, model_name=stored_model),
        )

    async def upsert_resume_embedding(
        self,
        *,
        resume_id: UUID,
        model_name: str,
        dims: int,
        embedding: list[float],
        text_fingerprint: str | None = None,
    ) -> ResumeEmbedding:
        if len(embedding) != EMBEDDING_COLUMN_DIMS:
            raise EmbeddingDimensionMismatch(
                model_name=model_name,
                produced=len(embedding),
                expected=EMBEDDING_COLUMN_DIMS,
            )

        values = {
            "resume_id": resume_id,
            "model_name": model_name,
            "dims": dims,
            "embedding": embedding,
            "text_fingerprint": text_fingerprint,
            "fingerprint_version": FINGERPRINT_VERSION if text_fingerprint else None,
        }

        # Atomic on (resume_id, model_name): two first generations racing for
        # the same resume used to be a check-then-insert against a unique index,
        # so one of them lost with an IntegrityError.
        dialect = self.session.bind.dialect.name if self.session.bind is not None else ""
        if dialect in {"postgresql", "sqlite"}:
            if dialect == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as dialect_insert
            else:
                from sqlalchemy.dialects.sqlite import insert as dialect_insert

            statement = dialect_insert(ResumeEmbedding).values(
                id=uuid4(), **values
            )
            await self.session.execute(
                statement.on_conflict_do_update(
                    index_elements=["resume_id", "model_name"],
                    set_={
                        "dims": statement.excluded.dims,
                        "embedding": statement.excluded.embedding,
                        "text_fingerprint": statement.excluded.text_fingerprint,
                        "fingerprint_version": statement.excluded.fingerprint_version,
                        "updated_at": datetime.now(timezone.utc),
                    },
                )
            )
            await self.session.commit()
            stored = await self._stored_embedding(resume_id, model_name, refresh=True)
            assert stored is not None  # the upsert just wrote it
            return stored

        existing = await self._stored_embedding(resume_id, model_name)  # pragma: no cover
        if existing:  # pragma: no cover — no other engine is supported
            for field, value in values.items():
                setattr(existing, field, value)
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        resume_embedding = ResumeEmbedding(**values)  # pragma: no cover
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
