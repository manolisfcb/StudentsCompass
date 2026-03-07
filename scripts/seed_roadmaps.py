import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.db import async_session
from app.services.roadmapSeedService import seed_roadmaps


async def run() -> None:
    async with async_session() as session:
        inserted = await seed_roadmaps(session)
        print(f"Seeded roadmaps. Created: {inserted}")


if __name__ == "__main__":
    asyncio.run(run())
