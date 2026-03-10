import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.communityModel import CommunityModel


@pytest.mark.asyncio
async def test_list_communities_can_filter_by_tags(
    client,
    auth_headers,
    db_session: AsyncSession,
    test_user,
):
    communities = [
        CommunityModel(
            id=uuid.uuid4(),
            name="Python Builders",
            description="Build things with Python",
            tags=["Python", "Backend"],
            member_count=12,
            created_by=test_user.id,
        ),
        CommunityModel(
            id=uuid.uuid4(),
            name="Data Circle",
            description="Data community",
            tags=["Data", "Python"],
            member_count=8,
            created_by=test_user.id,
        ),
        CommunityModel(
            id=uuid.uuid4(),
            name="Design Guild",
            description="Design discussions",
            tags=["Design"],
            member_count=5,
            created_by=test_user.id,
        ),
    ]
    db_session.add_all(communities)
    await db_session.commit()

    response = await client.get("/api/v1/communities?tags=python,backend", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert [item["name"] for item in payload] == ["Python Builders"]


@pytest.mark.asyncio
async def test_list_community_tags_returns_unique_sorted_values(
    client,
    auth_headers,
    db_session: AsyncSession,
    test_user,
):
    db_session.add_all(
        [
            CommunityModel(
                id=uuid.uuid4(),
                name="AI Lab",
                tags=["AI", "Python"],
                member_count=1,
                created_by=test_user.id,
            ),
            CommunityModel(
                id=uuid.uuid4(),
                name="Automation Hub",
                tags=["python", "Automation"],
                member_count=1,
                created_by=test_user.id,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/communities/tags?q=aut&limit=5", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == ["Automation"]


@pytest.mark.asyncio
async def test_list_community_tags_applies_limit_and_case_insensitive_search(
    client,
    auth_headers,
    db_session: AsyncSession,
    test_user,
):
    db_session.add_all(
        [
            CommunityModel(
                id=uuid.uuid4(),
                name="Tag Hub 1",
                tags=["Python", "PyTorch"],
                member_count=1,
                created_by=test_user.id,
            ),
            CommunityModel(
                id=uuid.uuid4(),
                name="Tag Hub 2",
                tags=["Pydantic", "PyCon"],
                member_count=1,
                created_by=test_user.id,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/communities/tags?q=PY&limit=2", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == ["PyCon", "Pydantic"]
