import argparse
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import async_session
from app.services.analytics.capstoneAnalyticsSeedService import seed_capstone_analytics_minimum  # noqa: F401
from app.services.analytics.capstoneAnalyticsService import CapstoneAnalyticsService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync capstone skill links from active job postings.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum active job postings to scan.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    async with async_session() as session:
        service = CapstoneAnalyticsService(session)
        summary = await service.extract_job_skills_for_open_postings(limit=args.limit)
    print(summary)


if __name__ == "__main__":
    asyncio.run(main())
