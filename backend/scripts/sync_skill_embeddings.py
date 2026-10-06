"""Embed every catalog skill once for the configured provider (TASK-074).

Idempotent: a skill whose stored fingerprint still matches is skipped without a
provider call, so running it twice in a row costs one SELECT the second time.
Run it after seeding or growing the catalog, and after changing
``EMBEDDINGS_PROVIDER`` or ``GEMINI_EMBEDDING_MODEL``:

    cd backend && EMBEDDINGS_PROVIDER=gemini .venv/bin/python scripts/sync_skill_embeddings.py

Under ``EMBEDDINGS_PROVIDER=hash`` it stores nothing and says so.
"""
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import async_session
# Every mapper has to be registered before the first query: SkillModel's
# relationships name JobPosting by string, and outside the app nothing else
# imports it. Without this the first SELECT fails to configure the mappers.
from app.models.registry import import_all_models
from app.services.analytics.skillEmbeddingService import SkillEmbeddingService

import_all_models()


async def main() -> None:
    async with async_session() as session:
        report = await SkillEmbeddingService(session).sync_catalog()
    print(report)


if __name__ == "__main__":
    asyncio.run(main())
