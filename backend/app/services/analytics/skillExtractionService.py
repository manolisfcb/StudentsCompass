from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skillModel import SkillModel
from app.services.analytics.skillNormalizer import SkillLookup, SkillNormalizer


@dataclass(frozen=True)
class SkillExtractionMatch:
    skill: SkillModel
    matched_text: str
    confidence_score: float
    evidence_text: str
    source_section: str | None
    extraction_method: str


class SkillExtractionService:
    """Rule-based skill extraction backed by the canonical skills catalog.

    A key matches where its whole token sequence appears in the normalized
    text. That is looked up by n-gram, so the cost follows the length of the
    text, not the size of the catalogue (TASK-082): the old scan tested every
    key against every line, which was free at 117 skills and is not at
    thousands.
    """

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

        tokens = self.normalizer.match_key(text).split()
        max_tokens = self._max_key_tokens(lookup)
        # The longest key wins as a skill's evidence, ties alphabetical: the
        # order the old scan over every key produced.
        best: dict[UUID, tuple[str, SkillModel]] = {}
        for start in range(len(tokens)):
            for size in range(1, min(max_tokens, len(tokens) - start) + 1):
                candidate = " ".join(tokens[start : start + size])
                skill = lookup.get(candidate)
                if skill is None:
                    continue
                current = best.get(skill.id)
                if current is None or (-len(candidate), candidate) < (-len(current[0]), current[0]):
                    best[skill.id] = (candidate, skill)

        matches = [
            SkillExtractionMatch(
                skill=skill,
                matched_text=candidate,
                confidence_score=self.DEFAULT_CONFIDENCE_SCORE,
                evidence_text=candidate,
                source_section=source_section,
                extraction_method=extraction_method,
            )
            for candidate, skill in best.values()
        ]
        return sorted(matches, key=lambda match: match.skill.display_name.lower())

    @staticmethod
    def _max_key_tokens(lookup: dict[str, SkillModel]) -> int:
        """The longest key, in tokens: how long an n-gram can still match.

        A ``SkillLookup`` carries it from when it was built. A plain dict (a
        caller's own) is measured here, once per call.
        """
        if isinstance(lookup, SkillLookup):
            return lookup.max_tokens
        return max((key.count(" ") + 1 for key in lookup), default=0)
