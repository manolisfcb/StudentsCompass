from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Awaitable, Callable

import numpy as np

from app.services.analytics.embeddingService import (
    LEGACY_SIMILARITY_PROFILE,
    SimilarityProfile,
    generate_embedding_in_active_space,
    get_effective_model_name,
    get_embedding_status,
    get_similarity_profile,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


EmbeddingFn = Callable[[str], Awaitable[list[float] | None]]

# The MiniLM-era thresholds, kept as names for callers that read them. The
# matcher itself reads its thresholds from a per-model ``SimilarityProfile``.
SEMANTIC_MATCH_THRESHOLD = LEGACY_SIMILARITY_PROFILE.semantic_match
WEAK_MATCH_THRESHOLD = LEGACY_SIMILARITY_PROFILE.weak_match

# Process-wide LRU cache for skill-text embeddings. Skill texts are short and
# repeat heavily across gap-analysis requests, so caching the default embedder
# avoids recomputing them on every request. Keyed by model name, so a provider
# change never serves a vector from the previous space.
_SKILL_EMBEDDING_CACHE: "OrderedDict[tuple[str, str], list[float]]" = OrderedDict()
_SKILL_EMBEDDING_CACHE_MAXSIZE = 2048


def _store_shared_skill_embedding(key: tuple[str, str], embedding: list[float]) -> None:
    _SKILL_EMBEDDING_CACHE[key] = embedding
    _SKILL_EMBEDDING_CACHE.move_to_end(key)
    while len(_SKILL_EMBEDDING_CACHE) > _SKILL_EMBEDDING_CACHE_MAXSIZE:
        _SKILL_EMBEDDING_CACHE.popitem(last=False)


@dataclass(frozen=True)
class SemanticMatchSummary:
    analysis_version: str
    coverage_ratio: float
    match_score: float
    semantic_score: float
    priority_gap_score: float
    exact_match_count: int
    semantic_match_count: int
    weak_match_count: int
    matched_required_skills: list[dict]
    semantic_matched_skills: list[dict]
    weak_matched_skills: list[dict]
    missing_skills: list[dict]


@dataclass(frozen=True)
class SemanticContextSummary:
    context_similarity_score: float
    context_match_level: str
    semantic_context_ready: bool
    provider: str
    evidence_sources: list[str]
    message: str


class SemanticMatchingService:
    def __init__(
        self,
        embedding_fn: EmbeddingFn = generate_embedding_in_active_space,
        semantic_ready_override: bool | None = None,
        profile: SimilarityProfile | None = None,
        session: "AsyncSession | None" = None,
    ):
        self.embedding_fn = embedding_fn
        # With a session, catalog skill vectors come from ``skill_embeddings``:
        # one SELECT per analysis, and a provider call only for a skill that has
        # never been embedded. Without one, each skill text is embedded here.
        self.session = session
        self.semantic_ready_override = semantic_ready_override
        # Only the default embedder is safe to share across requests in a
        # process-wide cache. Injected functions (tests, custom callers) use a
        # per-instance cache so they never read another caller's cached vectors.
        self._use_shared_cache = embedding_fn is generate_embedding_in_active_space
        self._local_cache: dict[str, list[float]] = {}
        # The default embedder reads cosines with its own model's profile. An
        # injected function has no stored model to look one up by, so it keeps
        # the thresholds its callers were written against.
        self.profile = (
            profile
            or (get_similarity_profile() if self._use_shared_cache else None)
            or LEGACY_SIMILARITY_PROFILE
        )

    async def analyze_required_skill_matches(
        self,
        *,
        current_skills: list[dict],
        required_skills: list[dict],
    ) -> SemanticMatchSummary:
        exact_current_by_id = {skill["skill_id"]: skill for skill in current_skills}
        exact_matches: list[dict] = []
        semantic_matches: list[dict] = []
        weak_matches: list[dict] = []
        missing_skills: list[dict] = []

        total_importance = sum(self._importance(skill) for skill in required_skills)
        exact_score = 0.0
        semantic_score_total = 0.0
        weak_score = 0.0
        required_ids = {required["skill_id"] for required in required_skills}
        available_semantic_candidates = [
            skill for skill in current_skills if skill["skill_id"] not in required_ids
        ]
        semantic_ready = self._semantic_ready()

        # Fetch every vector the analysis needs in one go — candidates and the
        # required skills that are not exact matches — then stack the candidates
        # into a single normalized matrix so each required skill is matched with
        # one vectorized matrix-vector product instead of pairwise cosine calls.
        candidate_pairs: list[tuple[dict, list[float]]] = []
        vectors: dict[str, list[float]] = {}
        if semantic_ready and available_semantic_candidates:
            pending_required = [
                required for required in required_skills
                if required["skill_id"] not in exact_current_by_id
            ]
            vectors = await self._skill_vectors(available_semantic_candidates + pending_required)
            for candidate in available_semantic_candidates:
                embedding = vectors.get(str(candidate["skill_id"]))
                if embedding:
                    candidate_pairs.append((candidate, embedding))

        candidate_matrix, kept = _normalize_matrix([emb for _, emb in candidate_pairs])
        candidate_skills = [candidate_pairs[i][0] for i in kept]

        for required in required_skills:
            current = exact_current_by_id.get(required["skill_id"])
            importance = self._importance(required)
            if current:
                confidence = float(current.get("confidence_score") or 0.75)
                exact_score += importance * max(0.0, min(confidence, 1.0))
                exact_matches.append(required)
                continue

            semantic_match = None
            required_embedding = vectors.get(str(required["skill_id"]))
            if candidate_matrix is not None and required_embedding:
                semantic_match = self._best_semantic_match(required_embedding, candidate_matrix, candidate_skills)

            if semantic_match and semantic_match["similarity_score"] >= self.profile.semantic_match:
                score = importance * semantic_match["similarity_score"] * 0.82
                semantic_score_total += score
                semantic_matches.append({**required, **semantic_match})
                continue

            if semantic_match and semantic_match["similarity_score"] >= self.profile.weak_match:
                score = importance * semantic_match["similarity_score"] * 0.35
                weak_score += score
                weak_matches.append({**required, **semantic_match})
                missing_skills.append(required)
                continue

            missing_skills.append(required)

        earned_score = exact_score + semantic_score_total + weak_score
        coverage_ratio = (len(exact_matches) + len(semantic_matches)) / len(required_skills) if required_skills else 0.0
        match_score = earned_score / total_importance if total_importance else 0.0
        semantic_score = semantic_score_total / total_importance if total_importance else 0.0
        priority_gap_score = 1.0 - match_score if required_skills else 0.0

        return SemanticMatchSummary(
            analysis_version="semantic_gap_v1",
            coverage_ratio=round(coverage_ratio, 4),
            match_score=round(max(0.0, min(match_score, 1.0)), 4),
            semantic_score=round(max(0.0, min(semantic_score, 1.0)), 4),
            priority_gap_score=round(max(0.0, min(priority_gap_score, 1.0)), 4),
            exact_match_count=len(exact_matches),
            semantic_match_count=len(semantic_matches),
            weak_match_count=len(weak_matches),
            matched_required_skills=exact_matches + semantic_matches,
            semantic_matched_skills=semantic_matches,
            weak_matched_skills=weak_matches,
            missing_skills=missing_skills,
        )

    async def analyze_context_similarity(
        self,
        *,
        resume_text: str,
        role_text: str,
        evidence_sources: list[str],
    ) -> SemanticContextSummary:
        embedding_status = get_embedding_status()
        if not resume_text.strip() or not role_text.strip():
            return SemanticContextSummary(
                context_similarity_score=0.0,
                context_match_level="unavailable",
                semantic_context_ready=False,
                provider=embedding_status["provider"],
                evidence_sources=evidence_sources,
                message="Context similarity is unavailable because the resume or role context is empty.",
            )

        if not self._semantic_ready():
            return SemanticContextSummary(
                context_similarity_score=0.0,
                context_match_level="fallback_disabled",
                semantic_context_ready=False,
                provider=embedding_status["provider"],
                evidence_sources=evidence_sources,
                message="Context similarity requires a semantic embedding provider; current provider is fallback-only.",
            )

        resume_embedding = await self.embedding_fn(resume_text)
        role_embedding = await self.embedding_fn(role_text)
        if not resume_embedding or not role_embedding:
            return SemanticContextSummary(
                context_similarity_score=0.0,
                context_match_level="unavailable",
                semantic_context_ready=False,
                provider=embedding_status["provider"],
                evidence_sources=evidence_sources,
                message="Context similarity is unavailable because embeddings could not be generated.",
            )

        return self.context_from_vectors(
            resume_embedding, role_embedding, evidence_sources=evidence_sources
        )

    def context_from_vectors(
        self,
        resume_embedding: list[float],
        role_embedding: list[float],
        *,
        evidence_sources: list[str],
    ) -> SemanticContextSummary:
        """Context similarity of two vectors already in the profile's space.

        For callers that hold stored vectors (a CV's ``resume_embeddings`` row,
        a posting's ``job_description_parses`` row) and should not pay to embed
        the same texts again. Banded on the raw cosine, reported rescaled: each
        model has its own background similarity, and an unrelated CV should
        score 0, not it.
        """
        cosine = _cosine_similarity(resume_embedding, role_embedding)
        similarity = round(self.profile.rescale_context(cosine), 4)
        if cosine >= self.profile.context_strong:
            match_level = "strong"
            message = "The full resume context is strongly aligned with the target role context."
        elif cosine >= self.profile.context_moderate:
            match_level = "moderate"
            message = "The full resume context has partial alignment with the target role context."
        else:
            match_level = "weak"
            message = "The full resume context has weak alignment with the target role context."

        return SemanticContextSummary(
            context_similarity_score=similarity,
            context_match_level=match_level,
            semantic_context_ready=True,
            provider=get_embedding_status()["provider"],
            evidence_sources=evidence_sources,
            message=message,
        )

    async def _skill_vectors(self, skills: list[dict]) -> dict[str, list[float]]:
        """Vectors of ``skills``, keyed by ``str(skill_id)``.

        The default embedder with a session reads the catalog's stored vectors
        (``SkillEmbeddingService``). Anything else embeds each skill's text here,
        evidence included, as the matcher always did.
        """
        if self.session is not None and self._use_shared_cache:
            from app.services.analytics.skillEmbeddingService import SkillEmbeddingService

            stored = await SkillEmbeddingService(self.session).get_vectors(skills)
            return {str(skill_id): vector for skill_id, vector in stored.items()}

        vectors: dict[str, list[float]] = {}
        for skill in skills:
            key = str(skill["skill_id"])
            if key in vectors:
                continue
            embedding = await self._embed_cached(self._skill_text(skill))
            if embedding:
                vectors[key] = embedding
        return vectors

    def _best_semantic_match(
        self,
        required_embedding: list[float],
        candidate_matrix: np.ndarray,
        candidate_skills: list[dict],
    ) -> dict | None:
        vector = np.asarray(required_embedding, dtype=np.float64)
        if vector.shape[0] != candidate_matrix.shape[1]:
            return None
        norm = float(np.linalg.norm(vector))
        if norm == 0.0:
            return None

        # candidate_matrix rows are already L2-normalized, so this matrix-vector
        # product yields the cosine similarity against every candidate at once.
        similarities = np.clip(candidate_matrix @ (vector / norm), 0.0, 1.0)
        best_index = int(np.argmax(similarities))
        best_score = float(similarities[best_index])
        if best_score <= 0.0:
            return None

        matched_skill = candidate_skills[best_index]
        return {
            "match_type": "semantic" if best_score >= self.profile.semantic_match else "weak",
            "matched_skill_id": matched_skill["skill_id"],
            "matched_skill_display_name": matched_skill["display_name"],
            "similarity_score": round(best_score, 4),
        }

    async def _embed_cached(self, text: str) -> list[float] | None:
        """Embed ``text`` with a cache to avoid recomputing repeated skill texts."""
        if self._use_shared_cache:
            key = (get_effective_model_name(), text)
            cached = _SKILL_EMBEDDING_CACHE.get(key)
            if cached is not None:
                _SKILL_EMBEDDING_CACHE.move_to_end(key)
                return cached
            embedding = await self.embedding_fn(text)
            if embedding:
                _store_shared_skill_embedding(key, embedding)
            return embedding

        cached = self._local_cache.get(text)
        if cached is not None:
            return cached
        embedding = await self.embedding_fn(text)
        if embedding:
            self._local_cache[text] = embedding
        return embedding

    @staticmethod
    def _skill_text(skill: dict) -> str:
        parts = [
            skill.get("display_name"),
            skill.get("normalized_name"),
            skill.get("category"),
            skill.get("evidence_text"),
        ]
        return " ".join(str(part) for part in parts if part)

    @staticmethod
    def _importance(skill: dict) -> float:
        value = float(skill.get("importance_score") or skill.get("confidence_score") or 0.75)
        return max(0.05, min(value, 1.0))

    def _semantic_ready(self) -> bool:
        if self.semantic_ready_override is not None:
            return self.semantic_ready_override
        return bool(get_embedding_status()["semantic_matching_ready"])


def _normalize_matrix(vectors: list[list[float]]) -> tuple[np.ndarray | None, list[int]]:
    """Stack embeddings into an L2-normalized matrix for batched cosine matching.

    Returns ``(matrix, kept_indices)`` where each matrix row is the normalized
    form of ``vectors[kept_indices[row]]``. Vectors with a mismatched
    dimensionality or a zero norm are dropped (they could never be a non-zero
    cosine match), so the matrix rows stay aligned with ``kept_indices``.
    """
    if not vectors:
        return None, []

    dims = len(vectors[0])
    rows: list[np.ndarray] = []
    kept: list[int] = []
    for index, vector in enumerate(vectors):
        if len(vector) != dims:
            continue
        array = np.asarray(vector, dtype=np.float64)
        norm = np.linalg.norm(array)
        if norm == 0.0:
            continue
        rows.append(array / norm)
        kept.append(index)

    if not rows:
        return None, []
    return np.vstack(rows), kept


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_array = np.asarray(left, dtype=np.float64)
    right_array = np.asarray(right, dtype=np.float64)
    left_norm = float(np.linalg.norm(left_array))
    right_norm = float(np.linalg.norm(right_array))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    similarity = float(np.dot(left_array, right_array) / (left_norm * right_norm))
    return max(0.0, min(similarity, 1.0))
