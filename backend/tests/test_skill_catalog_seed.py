"""The ESCO / O*NET skill catalogue: the file, its loading and what it changes (TASK-082)."""
from __future__ import annotations

import json
import time

import pytest
from sqlalchemy import func, select

from app.models.skillModel import SkillAliasModel, SkillModel
from app.services.analytics.capstoneAnalyticsSeedService import seed_capstone_analytics_minimum
from app.services.analytics.skillCatalogSeedService import CATALOG_PATH, load_catalog, seed_skill_catalog
from app.services.analytics.skillExtractionService import SkillExtractionService
from app.services.analytics.skillNormalizer import SkillNormalizer
from app.services.careerLab.jobDescriptionRules import is_employer_line, parse_job_description

RULES = json.loads((CATALOG_PATH.parent / "catalog_rules.json").read_text())


def _catalog(*skills: dict) -> dict:
    return {"version": "test", "attribution": [], "skills": list(skills)}


def _entry(name: str, display: str, aliases: list[str], source: str = "esco_1.2") -> dict:
    return {
        "name": name,
        "display": display,
        "category": "esco_knowledge",
        "source": source,
        "reference": f"test:{name}",
        "aliases": aliases,
    }


async def _count(session, model) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


# ---------------------------------------------------------------------------
# The shipped file
# ---------------------------------------------------------------------------


def test_the_shipped_catalogue_is_attributed_and_keyed_once():
    catalog = load_catalog()

    assert catalog["version"].startswith("esco1.2_onet31")
    assert any("ESCO" in line for line in catalog["attribution"])
    assert any("O*NET" in line and "CC BY 4.0" in line for line in catalog["attribution"])
    assert len(catalog["skills"]) > 10_000
    owners: dict[str, str] = {}
    for skill in catalog["skills"]:
        for label in [skill["display"], *skill["aliases"]]:
            key = SkillNormalizer.match_key(label)
            assert owners.setdefault(key, skill["name"]) == skill["name"], f"{key!r} has two skills"


def test_the_reviewed_lists_do_not_contradict_each_other():
    assert not set(RULES["everyday_words"]) & set(RULES["single_word_allow"])


def test_no_everyday_word_is_a_key_of_the_shipped_catalogue():
    everyday = {SkillNormalizer.match_key(word) for word in RULES["everyday_words"]}
    keys = {
        SkillNormalizer.match_key(label)
        for skill in load_catalog()["skills"]
        for label in [skill["display"], *skill["aliases"]]
    }
    assert not keys & everyday
    # The ones the review was about, by name.
    assert not keys & {"it", "lead", "access", "team", "drive", "meet", "security", "go", "chef"}
    assert {"contract law", "accounting", "apache kafka", "kafka", "jira", "html"} <= keys


# ---------------------------------------------------------------------------
# Loading it
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loading_adds_skills_and_never_takes_a_key_from_an_existing_one(db_session):
    await seed_capstone_analytics_minimum(db_session)
    excel = (await db_session.execute(select(SkillModel).where(SkillModel.normalized_name == "excel"))).scalar_one()

    report = await seed_skill_catalog(
        db_session,
        _catalog(
            _entry("contract_law", "contract law", ["law of contract", "derecho contractual"]),
            # Shares "microsoft excel" with the hand-written Excel: merged into it.
            _entry("microsoft_excel", "Microsoft Excel", ["Excel 365"], source="onet_31.0"),
            # Shares "SQL" with the hand-written SQL: merged into it too.
            _entry("structured_query", "Structured query", ["SQL"], source="onet_31.0"),
        ),
    )

    assert (report.created_skills, report.merged_into_existing) == (1, 2)
    lookup = await SkillNormalizer.build_lookup(db_session)
    assert lookup["contract law"].display_name == "contract law"
    assert lookup["law of contract"].display_name == "contract law"
    assert lookup["derecho contractual"].display_name == "contract law"
    assert lookup["excel 365"].id == excel.id
    assert lookup["sql"].display_name == "SQL"
    assert lookup["structured query"].display_name == "SQL"


@pytest.mark.asyncio
async def test_a_second_load_inserts_nothing(db_session):
    await seed_capstone_analytics_minimum(db_session)
    catalog = _catalog(_entry("contract_law", "contract law", ["law of contract"]))

    await seed_skill_catalog(db_session, catalog)
    skills, aliases = await _count(db_session, SkillModel), await _count(db_session, SkillAliasModel)
    again = await seed_skill_catalog(db_session, catalog)

    assert (again.created_skills, again.created_aliases) == (0, 0)
    assert (await _count(db_session, SkillModel), await _count(db_session, SkillAliasModel)) == (skills, aliases)


@pytest.mark.asyncio
async def test_the_real_catalogue_loads_and_reads_a_legal_posting(db_session, monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "hash")
    await seed_capstone_analytics_minimum(db_session)

    report = await seed_skill_catalog(db_session)

    assert report.created_skills > 10_000
    extractor = SkillExtractionService(db_session)
    started = time.perf_counter()
    parsed = await parse_job_description(
        "Commercial Counsel\n\nRequirements:\n"
        "- Experience leading negotiations of commercial agreements\n"
        "- Strong knowledge of contract law and data protection\n"
        "- Fluency in English and French\n",
        extractor=extractor,
    )
    elapsed = time.perf_counter() - started
    found = {item.display_name for item in parsed.requirements}
    assert {"Negotiation", "contract law", "data protection", "English", "French"} <= found
    # The catalogue is read once and cached; a parse is n-gram lookups.
    assert elapsed < 5


# ---------------------------------------------------------------------------
# What the parse no longer reads as a requirement
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "At Databricks, we are committed to fostering a diverse and inclusive culture where everyone can excel.",
        "If you need any accommodations, please inform your recruiting contact upon initial connection.",
        "The Covey tool has been reviewed by an independent auditor.",
        "Additional benefits for this role may include: equity, company bonus or sales commissions/bonuses.",
        "At Instacart, we invite the world to share love through food.",
    ],
)
def test_employer_lines_are_not_read_for_requirements(line):
    assert is_employer_line(line)


@pytest.mark.parametrize(
    "line",
    ["Experience with Excel and SQL", "You will lead negotiations with sales leadership", "At least 3 years of accounting"],
)
def test_role_lines_still_are(line):
    assert not is_employer_line(line)


@pytest.mark.asyncio
async def test_an_employer_section_runs_until_the_role_resumes(db_session):
    await seed_capstone_analytics_minimum(db_session)
    parsed = await parse_job_description(
        "Data Analyst\n\nRequirements:\n- SQL\n\nBenefits\nPython lunch club, Tableau of the month\n\n"
        "What you'll do\n- Build Power BI dashboards\n",
        extractor=SkillExtractionService(db_session),
    )
    found = {item.display_name for item in parsed.requirements}
    assert {"SQL", "Power BI"} <= found
    assert not found & {"Python", "Tableau"}


# ---------------------------------------------------------------------------
# Plurals
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("word", "folded"),
    [
        ("negotiations", "negotiation"),
        ("dashboards", "dashboard"),
        ("technologies", "technology"),
        ("business", "business"),
        ("analysis", "analysis"),
        ("analytics", "analytics"),
        ("status", "status"),
        ("news", "news"),
        ("excels", "excels"),
    ],
)
def test_plurals_fold_where_it_is_safe(word, folded):
    assert SkillNormalizer.fold_plural(word) == folded
