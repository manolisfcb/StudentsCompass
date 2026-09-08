from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from app.models.skillModel import SkillModel
from app.services.analytics.skillExtractionService import SkillExtractionService


async def summarize_resume_skill_dataset(
    *,
    csv_path: Path,
    extraction_service: SkillExtractionService,
    text_column: str = "Resume_str",
    category_column: str = "Category",
    limit: int | None = None,
) -> dict:
    """Extract aggregate skill signals from a resume CSV without storing resume text."""

    lookup = await extraction_service.build_skill_lookup()
    resumes_scanned = 0
    resumes_with_skills = 0
    skill_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    skill_category_counts: dict[str, Counter[str]] = defaultdict(Counter)

    with csv_path.open(newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if limit is not None and resumes_scanned >= limit:
                break
            text = row.get(text_column) or ""
            category = (row.get(category_column) or "unknown").strip() or "unknown"
            matches = await extraction_service.extract_known_skills_from_text(text, lookup=lookup)
            extracted_names = {match.skill.normalized_name for match in matches}

            resumes_scanned += 1
            category_counts[category] += 1
            if extracted_names:
                resumes_with_skills += 1

            for name in extracted_names:
                skill_counts[name] += 1
                skill_category_counts[category][name] += 1

    return {
        "source": str(csv_path),
        "resumes_scanned": resumes_scanned,
        "resumes_with_skills": resumes_with_skills,
        "coverage_ratio": round(resumes_with_skills / resumes_scanned, 4) if resumes_scanned else 0.0,
        "categories": dict(sorted(category_counts.items())),
        "top_skills": _top_skill_rows(skill_counts, lookup),
        "top_skills_by_category": {
            category: _top_skill_rows(counter, lookup, limit=10)
            for category, counter in sorted(skill_category_counts.items())
        },
    }


def _top_skill_rows(
    counts: Counter[str],
    lookup: dict[str, SkillModel],
    *,
    limit: int = 25,
) -> list[dict]:
    skills_by_name = {skill.normalized_name: skill for skill in lookup.values()}
    rows = []
    for normalized_name, count in counts.most_common(limit):
        skill = skills_by_name.get(normalized_name)
        rows.append(
            {
                "normalized_name": normalized_name,
                "display_name": skill.display_name if skill else normalized_name,
                "category": skill.category if skill else None,
                "resume_count": count,
            }
        )
    return rows
