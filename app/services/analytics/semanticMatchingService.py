from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Awaitable, Callable

import numpy as np

from app.services.analytics.embeddingService import (
    generate_embedding,
    get_embedding_provider,
    get_embedding_status,
)


EmbeddingFn = Callable[[str], Awaitable[list[float] | None]]

SEMANTIC_MATCH_THRESHOLD = 0.72
WEAK_MATCH_THRESHOLD = 0.48

# Process-wide LRU cache for skill-text embeddings. Skill texts are short and
# repeat heavily across gap-analysis requests, so caching the deterministic
# default embedder avoids recomputing them on every request.
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
    def __init__(self, embedding_fn: EmbeddingFn = generate_embedding, semantic_ready_override: bool | None = None):
        self.embedding_fn = embedding_fn
        self.semantic_ready_override = semantic_ready_override
        # Only the deterministic default embedder is safe to share across requests
        # in a process-wide cache. Injected functions (tests, custom callers) use a
        # per-instance cache so they never read another caller's cached vectors.
        self._use_shared_cache = embedding_fn is generate_embedding
        self._local_cache: dict[str, list[float]] = {}

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

        # Embed each candidate skill once up front instead of recomputing its
        # embedding for every required skill (was an N x M embedding blow-up),
        # then stack them into a single normalized matrix so each required skill
        # is matched with one vectorized matrix-vector product instead of an
        # inner Python loop of pairwise cosine calls.
        candidate_pairs: list[tuple[dict, list[float]]] = []
        if semantic_ready and available_semantic_candidates:
            for candidate in available_semantic_candidates:
                embedding = await self._embed_cached(self._skill_text(candidate))
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
            if semantic_ready and candidate_matrix is not None:
                semantic_match = await self._best_semantic_match(required, candidate_matrix, candidate_skills)

            if semantic_match and semantic_match["similarity_score"] >= SEMANTIC_MATCH_THRESHOLD:
                score = importance * semantic_match["similarity_score"] * 0.82
                semantic_score_total += score
                semantic_matches.append({**required, **semantic_match})
                continue

            if semantic_match and semantic_match["similarity_score"] >= WEAK_MATCH_THRESHOLD:
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

        similarity = round(_cosine_similarity(resume_embedding, role_embedding), 4)
        if similarity >= 0.78:
            match_level = "strong"
            message = "The full resume context is strongly aligned with the target role context."
        elif similarity >= 0.62:
            match_level = "moderate"
            message = "The full resume context has partial alignment with the target role context."
        else:
            match_level = "weak"
            message = "The full resume context has weak alignment with the target role context."

        return SemanticContextSummary(
            context_similarity_score=similarity,
            context_match_level=match_level,
            semantic_context_ready=True,
            provider=embedding_status["provider"],
            evidence_sources=evidence_sources,
            message=message,
        )

    async def _best_semantic_match(
        self,
        required_skill: dict,
        candidate_matrix: np.ndarray,
        candidate_skills: list[dict],
    ) -> dict | None:
        required_embedding = await self._embed_cached(self._skill_text(required_skill))
        if not required_embedding:
            return None

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
            "match_type": "semantic" if best_score >= SEMANTIC_MATCH_THRESHOLD else "weak",
            "matched_skill_id": matched_skill["skill_id"],
            "matched_skill_display_name": matched_skill["display_name"],
            "similarity_score": round(best_score, 4),
        }

    async def _embed_cached(self, text: str) -> list[float] | None:
        """Embed ``text`` with a cache to avoid recomputing repeated skill texts."""
        if self._use_shared_cache:
            key = (get_embedding_provider(), text)
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
