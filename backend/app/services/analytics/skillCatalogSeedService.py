"""Load the ESCO / O*NET skill catalogue into ``skills`` and ``skill_aliases`` (TASK-082).

The catalogue file is built by ``scripts/build_skill_catalog.py`` and shipped
in ``app/data/skill_catalog``. Loading it is idempotent and conservative:

* A key (name, display name or alias, compared as the extractor compares them)
  that the database already has stays with the skill that has it. A seed never
  takes a key away from a hand-written skill.
* A catalogue skill that shares a key with an existing skill is not created
  twice: its other keys become aliases of the existing one.
* Nothing is updated or deleted. A second run inserts nothing.

Embeddings for the new skills are a separate step
(``scripts/sync_skill_embeddings.py``): they cost provider calls, and loading
the catalogue must not.
"""
from __future__ import annotations

import gzip
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skillModel import SkillAliasModel, SkillModel
from app.services.analytics.skillNormalizer import SkillNormalizer

CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "skill_catalog" / "skill_catalog_v1.json.gz"
#: Rows per INSERT: well under PostgreSQL's bind-parameter limit at 7 columns.
INSERT_BATCH = 2000

_NAME_MAX = 120
_DISPLAY_MAX = 160
_ALIAS_MAX = 160


@dataclass(frozen=True)
class SkillCatalogSeedReport:
    version: str
    catalog_skills: int
    created_skills: int
    merged_into_existing: int
    created_aliases: int
    skipped_keys: int


def load_catalog(path: Path = CATALOG_PATH) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


async def seed_skill_catalog(session: AsyncSession, catalog: dict | None = None) -> SkillCatalogSeedReport:
    catalog = catalog if catalog is not None else load_catalog()
    key = SkillNormalizer.match_key

    existing_skills = (
        await session.execute(
            select(SkillModel.id, SkillModel.normalized_name, SkillModel.display_name).order_by(
                SkillModel.created_at, SkillModel.id
            )
        )
    ).all()
    existing_aliases = (await session.execute(select(SkillAliasModel.alias, SkillAliasModel.skill_id))).all()

    # Who owns each key now. One key, one skill: that is also what keeps the
    # unique constraint on the raw alias from ever being hit, since two raw
    # strings with one key are never both inserted.
    owner: dict[str, uuid.UUID] = {}
    for skill_id, normalized_name, display_name in existing_skills:
        for raw in (normalized_name.replace("_", " "), display_name):
            owner.setdefault(key(raw), skill_id)
    for alias, skill_id in existing_aliases:
        owner.setdefault(key(alias), skill_id)
    taken_names = {normalized_name for _, normalized_name, _ in existing_skills}

    now = datetime.utcnow()
    new_skills: list[dict] = []
    new_aliases: list[dict] = []
    merged = skipped = 0

    for entry in catalog["skills"]:
        name = entry["name"][:_NAME_MAX]
        display = entry["display"][:_DISPLAY_MAX]
        labels = [display, *entry["aliases"]]
        keys = [key(label) for label in labels]

        target = next((owner[k] for k in keys if k in owner), None)
        if target is None and name in taken_names:
            # Same canonical name, different wording: nothing to attach it to
            # by key, and a second row with that name is refused.
            skipped += len(labels)
            continue
        if target is None:
            target = uuid.uuid4()
            new_skills.append(
                {
                    "id": target,
                    "normalized_name": name,
                    "display_name": display,
                    "category": entry["category"],
                    "source": entry["source"],
                    "created_at": now,
                    "updated_at": now,
                }
            )
            taken_names.add(name)
            # The skill's own name and display name are keys already.
            owner.setdefault(key(name.replace("_", " ")), target)
            owner.setdefault(keys[0], target)
        else:
            merged += 1

        for label, label_key in zip(labels, keys, strict=True):
            current = owner.get(label_key)
            if not label_key or current == target:
                continue  # empty, or it already leads to this skill
            if current is not None:
                skipped += 1  # another skill has it, and keeps it
                continue
            owner[label_key] = target
            new_aliases.append(
                {
                    "id": uuid.uuid4(),
                    "skill_id": target,
                    "alias": label[:_ALIAS_MAX],
                    "source": entry["source"],
                    "created_at": now,
                }
            )

    for start in range(0, len(new_skills), INSERT_BATCH):
        await session.execute(insert(SkillModel), new_skills[start : start + INSERT_BATCH])
    for start in range(0, len(new_aliases), INSERT_BATCH):
        await session.execute(insert(SkillAliasModel), new_aliases[start : start + INSERT_BATCH])
    await session.commit()

    return SkillCatalogSeedReport(
        version=catalog["version"],
        catalog_skills=len(catalog["skills"]),
        created_skills=len(new_skills),
        merged_into_existing=merged,
        created_aliases=len(new_aliases),
        skipped_keys=skipped,
    )
