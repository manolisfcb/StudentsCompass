"""The n-gram extractor answers exactly what the old scan over every key did (TASK-082)."""
from __future__ import annotations

import random
import uuid
from types import SimpleNamespace

import pytest

from app.services.analytics.skillExtractionService import SkillExtractionService
from app.services.analytics.skillNormalizer import SkillNormalizer

WORDS = ["data", "analysis", "sql", "power", "bi", "c++", "c#", "machine", "learning", "contract", "law", "the", "and"]


def _reference(text: str, lookup: dict) -> dict:
    """The pre-TASK-082 algorithm: every key, longest first, as a padded substring."""
    normalized = f" {SkillNormalizer.normalize_text(text)} "
    found = {}
    for candidate, skill in sorted(lookup.items(), key=lambda item: (-len(item[0]), item[0])):
        if f" {candidate} " in normalized:
            found.setdefault(skill.id, candidate)
    return found


def _skill(name: str):
    return SimpleNamespace(id=uuid.uuid4(), display_name=name, normalized_name=name.replace(" ", "_"))


@pytest.mark.asyncio
async def test_same_matches_and_evidence_as_the_full_scan():
    rng = random.Random(82)
    extractor = SkillExtractionService(session=None)
    for _ in range(300):
        skills = [_skill(" ".join(rng.sample(WORDS, rng.randint(1, 3)))) for _ in range(rng.randint(1, 12))]
        lookup = {}
        for skill in skills:
            lookup.setdefault(SkillNormalizer.normalize_text(skill.display_name), skill)
            alias = " ".join(rng.sample(WORDS, rng.randint(1, 4)))
            lookup.setdefault(SkillNormalizer.normalize_text(alias), skill)
        text = " ".join(rng.choice(WORDS + ["Power-BI", "SQL!", "(C++)"]) for _ in range(rng.randint(0, 25)))

        matches = await extractor.extract_known_skills_from_text(text, lookup=lookup)

        assert {match.skill.id: match.matched_text for match in matches} == _reference(text, lookup)


def test_a_built_lookup_knows_its_longest_key():
    from app.services.analytics.skillNormalizer import SkillLookup

    lookup = SkillLookup()
    lookup.setdefault("sql", _skill("sql"))
    lookup["contract law"] = _skill("contract law")
    lookup.setdefault("sql", _skill("other"))
    assert lookup.max_tokens == 2
    assert lookup["sql"].display_name == "sql"
