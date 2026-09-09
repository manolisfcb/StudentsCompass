import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import async_session
from app.services.analytics.capstoneAnalyticsSeedService import seed_capstone_analytics_minimum


async def main() -> None:
    async with async_session() as session:
        summary = await seed_capstone_analytics_minimum(session)
    print(summary)


if __name__ == "__main__":
    asyncio.run(main())
