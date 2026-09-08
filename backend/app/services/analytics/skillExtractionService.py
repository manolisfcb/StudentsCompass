from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skillModel import SkillModel
from app.services.analytics.skillNormalizer import SkillNormalizer


@dataclass(frozen=True)
class SkillExtractionMatch:
    skill: SkillModel
    matched_text: str
    confidence_score: float
    evidence_text: str
    source_section: str | None
    extraction_method: str


class SkillExtractionService:
    """Rule-based skill extraction backed by the canonical skills catalog."""

    DEFAULT_CONFIDENCE_SCORE = 0.75

    def __init__(self, session: AsyncSession, normalizer: type[SkillNormalizer] = SkillNormalizer):
        self.session = session
        self.normalizer = normalizer

    async def build_skill_lookup(self) -> dict[str, SkillModel]:
        return await self.normalizer.build_lookup(self.session)

    async def extract_known_skills_from_text(
        self,
        text: str,
        *,
        lookup: dict[str, SkillModel] | None = None,
        extraction_method: str = "rules_v1",
        source_section: str | None = None,
    ) -> list[SkillExtractionMatch]:
        if lookup is None:
            lookup = await self.build_skill_lookup()
        if not lookup:
            return []

        normalized_text = f" {self.normalizer.normalize_text(text)} "
        matches_by_skill: dict[UUID, SkillExtractionMatch] = {}

        for candidate, skill in self._ordered_candidates(lookup):
            if f" {candidate} " not in normalized_text:
                continue
            matches_by_skill.setdefault(
                skill.id,
                SkillExtractionMatch(
                    skill=skill,
                    matched_text=candidate,
                    confidence_score=self.DEFAULT_CONFIDENCE_SCORE,
                    evidence_text=candidate,
                    source_section=source_section,
                    extraction_method=extraction_method,
                ),
            )

        return sorted(matches_by_skill.values(), key=lambda match: match.skill.display_name.lower())

    @staticmethod
    def _ordered_candidates(lookup: dict[str, SkillModel]) -> list[tuple[str, SkillModel]]:
        return sorted(
            lookup.items(),
            key=lambda item: (-len(item[0]), item[0]),
        )
