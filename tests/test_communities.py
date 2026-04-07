import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.communityModel import CommunityMemberModel, CommunityModel


async def _create_joined_community(
    db_session: AsyncSession,
    *,
    test_user,
    name: str = "Career Builders",
) -> CommunityModel:
    community = CommunityModel(
        id=uuid.uuid4(),
        name=name,
        description="A community for student growth",
        tags=["Career", "Networking"],
        member_count=1,
        created_by=test_user.id,
    )
    membership = CommunityMemberModel(
        id=uuid.uuid4(),
        community_id=community.id,
        user_id=test_user.id,
    )
    db_session.add(community)
    db_session.add(membership)
    await db_session.commit()
    await db_session.refresh(community)
    return community


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


@pytest.mark.asyncio
async def test_create_community_post_defaults_to_discussion(
    client,
    auth_headers,
    db_session: AsyncSession,
    test_user,
):
    community = await _create_joined_community(db_session, test_user=test_user)

    response = await client.post(
        f"/api/v1/communities/{community.id}/posts",
        json={"title": "Need advice", "content": "How should I structure my first portfolio project?"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["post_type"] == "discussion"

    posts = await client.get(
        f"/api/v1/communities/{community.id}/posts",
        headers=auth_headers,
    )
    assert posts.status_code == 200
    posts_payload = posts.json()
    assert posts_payload[0]["post_type"] == "discussion"


@pytest.mark.asyncio
async def test_create_community_post_accepts_structured_post_types(
    client,
    auth_headers,
    db_session: AsyncSession,
    test_user,
):
    community = await _create_joined_community(db_session, test_user=test_user, name="Interview Prep")

    response = await client.post(
        f"/api/v1/communities/{community.id}/posts",
        json={
            "title": "Can someone review this STAR example?",
            "content": "I want feedback on whether the impact sounds strong enough.",
            "post_type": "question",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["post_type"] == "question"


@pytest.mark.asyncio
async def test_create_community_post_rejects_unknown_post_type(
    client,
    auth_headers,
    db_session: AsyncSession,
    test_user,
):
    community = await _create_joined_community(db_session, test_user=test_user, name="UX Guild")

    response = await client.post(
        f"/api/v1/communities/{community.id}/posts",
        json={
            "title": "Invalid post",
            "content": "This should fail validation.",
            "post_type": "announcement",
        },
        headers=auth_headers,
    )

    assert response.status_code == 422
