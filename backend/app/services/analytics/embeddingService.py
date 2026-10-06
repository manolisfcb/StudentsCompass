from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
from uuid import UUID, uuid4

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.observability import external_call
from app.models.resumeEmbeddingsModel import ResumeEmbedding

LOGGER = logging.getLogger(__name__)

EMBEDDING_DIMS = int(os.getenv("EMBEDDING_DIMS", "384"))
#: Width of ``resume_embeddings.embedding``. Fixed in the column type, so it
#: is not configurable: ``EMBEDDING_DIMS`` can be pointed at another model,
#: but a vector that does not fit the column is refused, not truncated.
EMBEDDING_COLUMN_DIMS = 384
# Stored as the model_name for hash vectors so they never share a
# (resume_id, model_name) key with vectors from a real embedding model.
HASH_MODEL_NAME = "hash-v1"
DEFAULT_EMBEDDINGS_PROVIDER = "hash"
#: Bumped when the fingerprint recipe changes. Every stored fingerprint carries
#: the version that produced it, so an old one simply stops matching and the
#: vector is regenerated once — no migration required, no silent reuse of a
#: fingerprint computed under different rules.
FINGERPRINT_VERSION = "v1"

GEMINI_PROVIDER = "gemini"
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
#: Part of the vector space, not a tuning knob: two vectors compare only if
#: both sides were embedded with the same task type. Changing it means a new
#: model name (see ``gemini_model_name``), never a silent reinterpretation.
GEMINI_EMBEDDING_TASK_TYPE = "SEMANTIC_SIMILARITY"
#: The API caps one embed request at 100 inputs.
GEMINI_EMBEDDING_BATCH_SIZE = 100
EMBEDDING_TIMEOUT_SECONDS = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "10"))

_EMBEDDING_METRICS = {
    "local_failure_count": 0,
    "provider_failure_count": 0,
    "fallback_to_hash_count": 0,
    "unknown_provider_fallback_count": 0,
    "generation_skipped_count": 0,
    "generation_count": 0,
}


class EmbeddingProviderUnavailable(RuntimeError):
    """The configured provider could not produce a vector for this request."""


@dataclass(frozen=True)
class SimilarityProfile:
    """How to read a cosine produced by one embedding model.

    A cosine is not a portable number: each model spreads its scores over its
    own range. ``semantic_match`` / ``weak_match`` decide when a current skill
    stands in for a required one. Context similarity is banded on the raw
    cosine (``context_strong`` / ``context_moderate``) and reported rescaled to
    [0, 1] between ``context_floor`` and ``context_ceiling``, so that an
    unrelated CV scores 0 rather than the model's background similarity.
    """

    semantic_match: float
    weak_match: float
    context_strong: float
    context_moderate: float
    context_floor: float = 0.0
    context_ceiling: float = 1.0

    def rescale_context(self, cosine: float) -> float:
        span = self.context_ceiling - self.context_floor
        return max(0.0, min((cosine - self.context_floor) / span, 1.0))


#: The thresholds the matcher always had, calibrated for MiniLM. Used when the
#: caller injects its own embedding function (tests, custom callers): there is
#: no stored model to look up, and those callers were written against them.
LEGACY_SIMILARITY_PROFILE = SimilarityProfile(
    semantic_match=0.72,
    weak_match=0.48,
    context_strong=0.78,
    context_moderate=0.62,
)

#: Calibrated profiles, keyed by storage model name. A model with no entry here
#: is never semantically ready: comparing its cosines against another model's
#: thresholds is exactly the error this table exists to prevent.
#:
#: ``gemini-embedding-001@384`` — measured 2026-10-05 (TASK-072/073) with
#: ``task_type=SEMANTIC_SIMILARITY`` on skill texts shaped like ``_skill_text``:
#: synonyms 0.95–0.99, related skills 0.88–0.94, unrelated 0.74–0.80. A related
#: skill is a weak match, not a substitute. Context CV↔job: aligned 0.87,
#: adjacent role 0.84, other stack 0.76, other profession 0.68. The context
#: values rest on four synthetic pairs and are provisional until TASK-079
#: calibrates them against real postings.
SIMILARITY_PROFILES: dict[str, SimilarityProfile] = {
    "gemini-embedding-001@384": SimilarityProfile(
        semantic_match=0.95,
        weak_match=0.88,
        context_strong=0.85,
        context_moderate=0.80,
        context_floor=0.70,
        context_ceiling=0.90,
    ),
}


def get_similarity_profile(model_name: str | None = None) -> SimilarityProfile | None:
    """The calibrated profile of ``model_name`` (default: the configured one)."""
    return SIMILARITY_PROFILES.get(model_name or get_effective_model_name())


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


def gemini_model_name() -> str:
    """Storage name of the Gemini vector space: model plus width.

    The same model truncated to another width is another space, so the width
    is part of the name. A hash vector is never stored under this name.
    """
    return f"{GEMINI_EMBEDDING_MODEL}@{EMBEDDING_COLUMN_DIMS}"


def get_effective_model_name() -> str:
    """Model name under which embeddings are stored for the configured provider.

    Mirrors the model name reported by ``generate_embedding_with_model`` so that
    corpus searches query the matching vector space, and so the fingerprint skip
    in ``upsert_resume_embedding_from_text`` looks for the row the provider is
    about to write. Unknown providers fall back to hash, so they report hash.
    """
    if get_embedding_provider() == GEMINI_PROVIDER:
        return gemini_model_name()
    return HASH_MODEL_NAME


def is_provider_configured() -> bool:
    """Whether the configured provider can be called at all.

    ``hash`` needs nothing. ``gemini`` needs an API key; without one every
    request falls back to hash, which is a configuration error worth showing.
    """
    provider = get_embedding_provider()
    if provider == "hash":
        return True
    if provider == GEMINI_PROVIDER:
        return bool(os.getenv("GENAI_API_KEY"))
    return False


def is_semantic_matching_ready() -> bool:
    """Whether cosines from the configured provider can be acted on.

    Three conditions, all required: generation is on, the provider produces
    vectors with meaning and can be called (hash never qualifies; Gemini needs
    its key), and its model has a calibrated ``SimilarityProfile``.
    """
    return (
        is_embedding_generation_enabled()
        and get_embedding_provider() != "hash"
        and is_provider_configured()
        and get_similarity_profile() is not None
    )


def get_embedding_status() -> dict:
    provider = get_embedding_provider()
    # The local_* keys stay in the public status contract, but there is no local
    # provider any more: they are always False.
    return {
        "enabled": is_embedding_generation_enabled(),
        "provider": provider,
        "provider_configured": is_provider_configured(),
        "model_name": get_effective_model_name(),
        "dims": EMBEDDING_COLUMN_DIMS if provider == GEMINI_PROVIDER else EMBEDDING_DIMS,
        "semantic_matching_ready": is_semantic_matching_ready(),
        "local_provider_configured": False,
        "local_package_available": False,
        "fallback_provider": "hash",
        "model_cache_strategy": "none",
        "local_failure_count": _EMBEDDING_METRICS["local_failure_count"],
        "provider_failure_count": _EMBEDDING_METRICS["provider_failure_count"],
        "fallback_to_hash_count": _EMBEDDING_METRICS["fallback_to_hash_count"],
        "unknown_provider_fallback_count": _EMBEDDING_METRICS["unknown_provider_fallback_count"],
        "generation_count": _EMBEDDING_METRICS["generation_count"],
        "generation_skipped_count": _EMBEDDING_METRICS["generation_skipped_count"],
        "fingerprint_version": FINGERPRINT_VERSION,
        "production_recommendation": (
            "Hash embeddings only: semantic matching stays off until an API embedding provider is configured."
            if provider == "hash"
            else "Monitor fallback_to_hash_count before relying on semantic scoring."
        ),
    }


def _l2_normalize(vector: list[float]) -> list[float]:
    """Unit-length copy of ``vector``.

    Gemini only pre-normalises its native 3072-dimension output. Truncated to
    384 the norm comes back around 0.43, and a cosine computed as a plain dot
    product over such vectors would be quietly wrong.
    """
    array = np.asarray(vector, dtype=np.float64)
    norm = float(np.linalg.norm(array))
    if norm == 0.0:
        return array.tolist()
    return (array / norm).tolist()


@lru_cache(maxsize=1)
def _build_gemini_client(api_key: str) -> Any:
    from google import genai

    return genai.Client(api_key=api_key)


def _get_gemini_client() -> Any | None:
    api_key = os.getenv("GENAI_API_KEY")
    if not api_key:
        return None
    return _build_gemini_client(api_key)


async def _gemini_embed(texts: list[str]) -> list[list[float]]:
    """Embed ``texts`` with Gemini, in order, or raise ``EmbeddingProviderUnavailable``.

    One attempt per chunk and no retries: a failure falls back to hash in the
    caller, which is cheaper than retrying a paid call against an API that just
    refused it.
    """
    from app import config

    # The kill switch stops every paid provider call, not only generation.
    if config.AI_KILL_SWITCH:
        raise EmbeddingProviderUnavailable("AI kill switch is on")
    client = _get_gemini_client()
    if client is None:
        raise EmbeddingProviderUnavailable("GENAI_API_KEY is not set")

    from google.genai import types

    embed_config = types.EmbedContentConfig(
        task_type=GEMINI_EMBEDDING_TASK_TYPE,
        output_dimensionality=EMBEDDING_COLUMN_DIMS,
    )
    vectors: list[list[float]] = []
    for start in range(0, len(texts), GEMINI_EMBEDDING_BATCH_SIZE):
        chunk = texts[start : start + GEMINI_EMBEDDING_BATCH_SIZE]
        try:
            with external_call("gemini_embeddings"):
                response = await asyncio.wait_for(
                    client.aio.models.embed_content(
                        model=GEMINI_EMBEDDING_MODEL,
                        contents=chunk,
                        config=embed_config,
                    ),
                    timeout=EMBEDDING_TIMEOUT_SECONDS,
                )
        except Exception as exc:
            raise EmbeddingProviderUnavailable(f"{type(exc).__name__}: {exc}") from exc

        embeddings = list(response.embeddings or [])
        if len(embeddings) != len(chunk):
            raise EmbeddingProviderUnavailable(
                f"asked for {len(chunk)} embeddings, received {len(embeddings)}"
            )
        for embedding in embeddings:
            values = list(embedding.values or [])
            if len(values) != EMBEDDING_COLUMN_DIMS:
                raise EmbeddingProviderUnavailable(
                    str(
                        EmbeddingDimensionMismatch(
                            model_name=gemini_model_name(),
                            produced=len(values),
                            expected=EMBEDDING_COLUMN_DIMS,
                        )
                    )
                )
            vectors.append(_l2_normalize(values))
    return vectors


async def generate_embeddings_batch(texts: list[str]) -> tuple[list[list[float]], str] | None:
    """Embed several texts in one go and report the model that produced them.

    All vectors of one call share one model name: if the provider fails for any
    chunk, the whole batch falls back to hash, so a caller never holds a list
    that mixes two vector spaces. Texts are stripped exactly as
    ``normalize_embedding_text`` does; an empty text is refused, because its
    position in the result would otherwise be ambiguous.
    """
    clean_texts = [normalize_embedding_text(text) for text in texts]
    if not clean_texts or not is_embedding_generation_enabled():
        return None
    if any(not text for text in clean_texts):
        raise ValueError("generate_embeddings_batch received an empty text")

    provider = get_embedding_provider()
    if provider == GEMINI_PROVIDER:
        try:
            return await _gemini_embed(clean_texts), gemini_model_name()
        except EmbeddingProviderUnavailable as exc:
            LOGGER.warning(
                "Gemini embeddings unavailable (%s). Falling back to hash embeddings.", exc
            )
            _EMBEDDING_METRICS["provider_failure_count"] += 1
            _EMBEDDING_METRICS["fallback_to_hash_count"] += 1
            return [generate_hash_embedding(text) for text in clean_texts], HASH_MODEL_NAME

    if provider != "hash":
        LOGGER.warning("Unknown EMBEDDINGS_PROVIDER=%s. Falling back to hash embeddings.", provider)
        _EMBEDDING_METRICS["unknown_provider_fallback_count"] += 1
        _EMBEDDING_METRICS["fallback_to_hash_count"] += 1
    return [generate_hash_embedding(text) for text in clean_texts], HASH_MODEL_NAME


async def generate_embedding_with_model(text: str) -> tuple[list[float], str] | None:
    """Generate an embedding and report the model name actually used.

    The returned model name distinguishes a real model's vector from a
    hash-fallback vector, so callers can persist them under separate keys.
    ``EMBEDDINGS_PROVIDER=local`` names the retired sentence-transformer and is
    now an unknown provider: it falls back to hash and is counted as such.
    """
    clean_text = normalize_embedding_text(text)
    if not clean_text:
        return None
    result = await generate_embeddings_batch([clean_text])
    if result is None:
        return None
    vectors, model_name = result
    return vectors[0], model_name


async def generate_embedding(text: str) -> list[float] | None:
    result = await generate_embedding_with_model(text)
    return result[0] if result else None


async def generate_embedding_in_active_space(text: str) -> list[float] | None:
    """A vector from the configured model, or ``None``.

    A hash fallback has the same width as a Gemini vector, so nothing would stop
    it from being compared against one — and the cosine between two different
    spaces is noise. Whatever compares vectors uses this, and treats a fallback
    as "no vector" rather than as a vector.
    """
    result = await generate_embedding_with_model(text)
    if result is None:
        return None
    vector, model_name = result
    if model_name != get_effective_model_name():
        return None
    return vector


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
        provider that is CPU; with a model provider it is a paid call. Now the
        fingerprint of (text, model, scheme version) is compared *first*, and an
        identical request costs one SELECT and nothing else.

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

        # The provider may have fallen back to hash, which is a
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
