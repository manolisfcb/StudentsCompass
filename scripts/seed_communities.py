import asyncio
import os
import sys
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.db import async_session
from app.models.userModel import User
from app.models.communityModel import CommunityModel, CommunityMemberModel
from app.models.postModel import PostModel
from app.models.questionnaireModel import UserQuestionnaire
from app.models.resumeModel import ResumeModel
from app.models.jobAnalysisModel import JobAnalysisModel
from app.models.userStatsModel import UserStatsModel
from app.models.communityPostModel import CommunityPostModel, CommunityPostLikeModel, CommunityPostCommentModel


SEED_COMMUNITIES = [
    {
        "name": "Python Data Analytics",
        "description": "Aprende Python para análisis de datos con pandas, NumPy y matplotlib.",
        "icon": "🐍",
        "activity_status": "Very active",
        "tags": ["Python", "Pandas", "Data Science"],
        "member_count": 1234,
    },
    {
        "name": "R Analytics Community",
        "description": "Domina R para análisis estadístico y visualización con tidyverse y ggplot2.",
        "icon": "📊",
        "activity_status": "Active",
        "tags": ["R", "Statistics", "ggplot2"],
        "member_count": 892,
    },
    {
        "name": "SQL & Database Analytics",
        "description": "Consultas SQL para análisis de datos: desde lo básico a lo avanzado.",
        "icon": "🗄️",
        "activity_status": "Very active",
        "tags": ["SQL", "PostgreSQL", "MySQL"],
        "member_count": 1567,
    },
    {
        "name": "Tableau Visualization",
        "description": "Crea visualizaciones impactantes y comparte dashboards en Tableau.",
        "icon": "📈",
        "activity_status": "Active",
        "tags": ["Tableau", "Dashboards", "Viz"],
        "member_count": 756,
    },
    {
        "name": "Power BI Analytics",
        "description": "Aprende Power BI y DAX para inteligencia de negocio.",
        "icon": "📉",
        "activity_status": "Very active",
        "tags": ["Power BI", "DAX", "Business Intelligence"],
        "member_count": 1089,
    },
    {
        "name": "Excel Data Analytics",
        "description": "Análisis de datos en Excel con Power Query, tablas dinámicas y VBA.",
        "icon": "📑",
        "activity_status": "Low activity",
        "tags": ["Excel", "Power Query", "VBA"],
        "member_count": 2145,
    },
]


def _get_seed_user_email() -> str | None:
    return os.getenv("COMMUNITY_SEED_USER_EMAIL")


async def _get_seed_user(session: AsyncSession) -> User | None:
    email = _get_seed_user_email()
    if email:
        result = await session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
    result = await session.execute(select(User).limit(1))
    return result.scalar_one_or_none()


async def _ensure_creator_membership(
    session: AsyncSession,
    community_id,
    user_id,
):
    result = await session.execute(
        select(CommunityMemberModel).where(
            CommunityMemberModel.community_id == community_id,
            CommunityMemberModel.user_id == user_id,
        )
    )
    if result.scalar_one_or_none() is None:
        session.add(CommunityMemberModel(community_id=community_id, user_id=user_id))


async def seed_communities(seed_data: Iterable[dict]):
    async with async_session() as session:
        user = await _get_seed_user(session)
        if not user:
            print("No user found. Create a user first or set COMMUNITY_SEED_USER_EMAIL.")
            return

        for data in seed_data:
            result = await session.execute(
                select(CommunityModel).where(CommunityModel.name == data["name"])
            )
            existing = result.scalar_one_or_none()
            if existing:
                continue

            community = CommunityModel(
                name=data["name"],
                description=data.get("description"),
                icon=data.get("icon"),
                activity_status=data.get("activity_status"),
                tags=data.get("tags"),
                member_count=data.get("member_count", 0),
                created_by=user.id,
            )
            session.add(community)
            await session.flush()
            await _ensure_creator_membership(session, community.id, user.id)

        await session.commit()
        print("Seeded communities successfully.")


if __name__ == "__main__":
    asyncio.run(seed_communities(SEED_COMMUNITIES))
