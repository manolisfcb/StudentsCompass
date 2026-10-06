"""Load the ESCO / O*NET skill catalogue into the database (TASK-082).

Idempotent: a second run inserts nothing. It never edits or deletes a skill,
and a key the database already has stays with the skill that has it.

    cd backend && .venv/bin/python scripts/seed_skill_catalog.py

Then embed the new skills, which is the step that costs provider calls:

    cd backend && EMBEDDINGS_PROVIDER=gemini .venv/bin/python scripts/sync_skill_embeddings.py
"""
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import async_session
# Every mapper has to be registered before the first query (see
# sync_skill_embeddings.py for why).
from app.models.registry import import_all_models
from app.services.analytics.skillCatalogSeedService import seed_skill_catalog

import_all_models()


async def main() -> None:
    async with async_session() as session:
        report = await seed_skill_catalog(session)
    print(report)


if __name__ == "__main__":
    asyncio.run(main())
