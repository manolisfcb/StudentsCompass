from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Awaitable, Callable

from app.services.analytics.embeddingService import generate_embedding, get_embedding_status


EmbeddingFn = Callable[[str], Awaitable[list[float] | None]]

SEMANTIC_MATCH_THRESHOLD = 0.72
WEAK_MATCH_THRESHOLD = 0.48


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
        # embedding for every required skill (was an N x M embedding blow-up).
        candidate_embeddings: list[tuple[dict, list[float]]] = []
        if semantic_ready and available_semantic_candidates:
            for candidate in available_semantic_candidates:
                embedding = await self.embedding_fn(self._skill_text(candidate))
                if embedding:
                    candidate_embeddings.append((candidate, embedding))

        for required in required_skills:
            current = exact_current_by_id.get(required["skill_id"])
            importance = self._importance(required)
            if current:
                confidence = float(current.get("confidence_score") or 0.75)
                exact_score += importance * max(0.0, min(confidence, 1.0))
                exact_matches.append(required)
                continue

            semantic_match = None
            if semantic_ready and candidate_embeddings:
                semantic_match = await self._best_semantic_match(required, candidate_embeddings)

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
        candidate_embeddings: list[tuple[dict, list[float]]],
    ) -> dict | None:
        required_embedding = await self.embedding_fn(self._skill_text(required_skill))
        if not required_embedding:
            return None

        best_payload = None
        best_score = 0.0
        for current_skill, current_embedding in candidate_embeddings:
            similarity = _cosine_similarity(required_embedding, current_embedding)
            if similarity > best_score:
                best_score = similarity
                best_payload = {
                    "match_type": "semantic" if similarity >= SEMANTIC_MATCH_THRESHOLD else "weak",
                    "matched_skill_id": current_skill["skill_id"],
                    "matched_skill_display_name": current_skill["display_name"],
                    "similarity_score": round(similarity, 4),
                }
        return best_payload

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


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(0.0, min(dot / (left_norm * right_norm), 1.0))
