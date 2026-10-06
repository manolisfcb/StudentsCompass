from __future__ import annotations

import re
from collections.abc import Iterable

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skillModel import SkillAliasModel, SkillModel


@dataclass(frozen=True)
class CatalogSkill:
    """What an extraction needs of a skill, detached from any session."""

    id: UUID
    normalized_name: str
    display_name: str
    category: str | None


class SkillLookup(dict):
    """Normalized key → skill, plus the longest key in tokens.

    The extractor matches by n-gram and needs to know how long an n-gram can
    still be a key; computing it means walking every key, so it is done once,
    here, rather than once per line of text.
    """

    max_tokens: int = 0

    def __setitem__(self, key, value) -> None:
        super().__setitem__(key, value)
        self.max_tokens = max(self.max_tokens, key.count(" ") + 1)

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]


#: Verbs in -s whose stem is a skill: "someone who excels in…" is not Excel.
#: Found on 3,218 public postings (TASK-082); the stems themselves are left
#: to the catalogue.
_NOT_PLURALS = frozenset({"excels"})

#: (fingerprint, lookup) of the last catalogue read. One per process: the
#: catalogue is shared by every user, and readers never mutate the lookup.
_LOOKUP_CACHE: tuple[tuple, "SkillLookup"] | None = None


class SkillNormalizer:
    """Normalize capstone skill text into stable dictionary lookup keys."""

    @staticmethod
    def normalize_text(value: str | None) -> str:
        cleaned = re.sub(r"[^a-z0-9+#]+", " ", (value or "").lower()).strip()
        return re.sub(r"\s+", " ", cleaned)

    @staticmethod
    def fold_plural(token: str) -> str:
        """`negotiations` → negotiation, `technologies` → technology.

        Postings name skills in the plural ("leading negotiations", "build
        dashboards") and catalogues in the singular, and an exact match missed
        every one (TASK-082). Words under five letters are left alone ("news"
        is not "new"), and so are -ss, -us, -is and -ics endings: business,
        status, analysis, analytics.
        """
        if len(token) < 5 or token.endswith(("ss", "us", "is", "ics")) or token in _NOT_PLURALS:
            return token
        if token.endswith("ies") and len(token) >= 6:
            return token[:-3] + "y"
        if token.endswith("s"):
            return token[:-1]
        return token

    @classmethod
    def match_key(cls, value: str | None) -> str:
        """The form both catalogue keys and text are compared in."""
        return " ".join(cls.fold_plural(token) for token in cls.normalize_text(value).split())

    @classmethod
    def normalize_canonical_name(cls, value: str | None) -> str:
        return cls.normalize_text(value).replace(" ", "_")

    @classmethod
    async def build_lookup(cls, session: AsyncSession) -> SkillLookup:
        """Every catalogue key → its skill, cached per process (TASK-082).

        Read as plain rows into :class:`CatalogSkill` records, not ORM objects:
        at tens of thousands of skills and aliases, materialising the mapped
        graph on every CV and every posting cost seconds. The cache is keyed by
        a fingerprint of both tables, read with one aggregate query per call,
        so a seeded or edited catalogue is picked up on the next extraction.

        Oldest skill first: when two skills claim one key, the one that was in
        the catalogue first keeps it, so a seed never takes a key away from a
        hand-written skill.
        """
        global _LOOKUP_CACHE
        fingerprint = await cls._catalog_fingerprint(session)
        cached = _LOOKUP_CACHE
        if cached is not None and cached[0] == fingerprint:
            return cached[1]

        skills_result = await session.execute(
            select(
                SkillModel.id, SkillModel.normalized_name, SkillModel.display_name, SkillModel.category
            ).order_by(SkillModel.created_at, SkillModel.id)
        )
        skills = {row.id: CatalogSkill(*row) for row in skills_result.all()}
        aliases_result = await session.execute(
            select(SkillAliasModel.alias, SkillAliasModel.skill_id).order_by(
                SkillAliasModel.created_at, SkillAliasModel.id
            )
        )
        aliases = [
            SimpleNamespace(alias=row.alias, skill=skills[row.skill_id])
            for row in aliases_result.all()
            if row.skill_id in skills
        ]
        lookup = cls.build_lookup_from_records(skills=skills.values(), aliases=aliases)
        _LOOKUP_CACHE = (fingerprint, lookup)
        return lookup

    @staticmethod
    async def _catalog_fingerprint(session: AsyncSession) -> tuple:
        """Counts, newest change and highest id of both tables, in one query."""
        columns = [
            select(aggregate).scalar_subquery()
            for aggregate in (
                func.count(SkillModel.id),
                func.max(SkillModel.updated_at),
                # PostgreSQL has no max() over uuid; over its text it does.
                func.max(cast(SkillModel.id, String)),
                func.count(SkillAliasModel.id),
                func.max(SkillAliasModel.created_at),
                func.max(cast(SkillAliasModel.id, String)),
            )
        ]
        return tuple((await session.execute(select(*columns))).one())

    @classmethod
    def build_lookup_from_records(
        cls,
        *,
        skills: Iterable[SkillModel],
        aliases: Iterable[SkillAliasModel],
    ) -> SkillLookup:
        lookup = SkillLookup()
        for skill in skills:
            cls._add_lookup_key(lookup, skill.normalized_name.replace("_", " "), skill)
            cls._add_lookup_key(lookup, skill.display_name, skill)
        for alias in aliases:
            cls._add_lookup_key(lookup, alias.alias, alias.skill)
        return lookup

    @classmethod
    def _add_lookup_key(cls, lookup: dict[str, SkillModel], raw_key: str | None, skill: SkillModel) -> None:
        key = cls.match_key(raw_key)
        if key:
            lookup.setdefault(key, skill)
