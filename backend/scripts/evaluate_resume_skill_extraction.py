from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.models.skillModel import SkillAliasModel, SkillModel
from app.services.analytics.capstoneAnalyticsSeedService import CAPSTONE_SKILL_SEED_DATA
from app.services.analytics.resumeSkillDatasetEvaluator import summarize_resume_skill_dataset
from app.services.analytics.skillExtractionService import SkillExtractionService
from app.services.analytics.skillNormalizer import SkillNormalizer


class SeedCatalogExtractionService(SkillExtractionService):
    def __init__(self):
        super().__init__(session=None)  # type: ignore[arg-type]

    async def build_skill_lookup(self) -> dict[str, SkillModel]:
        skills: list[SkillModel] = []
        aliases: list[SkillAliasModel] = []
        for skill_data in CAPSTONE_SKILL_SEED_DATA:
            skill = SkillModel(
                id=uuid.uuid4(),
                normalized_name=skill_data["name"],
                display_name=skill_data["display"],
                category=skill_data["category"],
                source="capstone_seed",
            )
            skills.append(skill)
            aliases.extend(
                SkillAliasModel(skill=skill, alias=alias, source="capstone_seed")
                for alias in skill_data["aliases"]
            )
        return SkillNormalizer.build_lookup_from_records(skills=skills, aliases=aliases)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize aggregate skill extraction signals from the resume CSV without storing resume text.",
    )
    parser.add_argument(
        "--resume-csv",
        type=Path,
        default=Path("data/resumes 3/Resume/Resume.csv"),
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    summary = await summarize_resume_skill_dataset(
        csv_path=args.resume_csv,
        extraction_service=SeedCatalogExtractionService(),
        limit=args.limit,
    )
    payload = json.dumps(summary, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    asyncio.run(main())
