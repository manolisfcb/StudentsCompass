from __future__ import annotations

import re
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.skillModel import SkillAliasModel, SkillModel


class SkillNormalizer:
    """Normalize capstone skill text into stable dictionary lookup keys."""

    @staticmethod
    def normalize_text(value: str | None) -> str:
        cleaned = re.sub(r"[^a-z0-9+#]+", " ", (value or "").lower()).strip()
        return re.sub(r"\s+", " ", cleaned)

    @classmethod
    def normalize_canonical_name(cls, value: str | None) -> str:
        return cls.normalize_text(value).replace(" ", "_")

    @classmethod
    async def build_lookup(cls, session: AsyncSession) -> dict[str, SkillModel]:
        skills_result = await session.execute(select(SkillModel))
        skills = list(skills_result.scalars().all())

        aliases_result = await session.execute(
            select(SkillAliasModel).options(selectinload(SkillAliasModel.skill))
        )
        aliases = list(aliases_result.scalars().all())

        return cls.build_lookup_from_records(skills=skills, aliases=aliases)

    @classmethod
    def build_lookup_from_records(
        cls,
        *,
        skills: Iterable[SkillModel],
        aliases: Iterable[SkillAliasModel],
    ) -> dict[str, SkillModel]:
        lookup: dict[str, SkillModel] = {}
        for skill in skills:
            cls._add_lookup_key(lookup, skill.normalized_name.replace("_", " "), skill)
            cls._add_lookup_key(lookup, skill.display_name, skill)
        for alias in aliases:
            cls._add_lookup_key(lookup, alias.alias, alias.skill)
        return lookup

    @classmethod
    def _add_lookup_key(cls, lookup: dict[str, SkillModel], raw_key: str | None, skill: SkillModel) -> None:
        key = cls.normalize_text(raw_key)
        if key:
            lookup.setdefault(key, skill)
