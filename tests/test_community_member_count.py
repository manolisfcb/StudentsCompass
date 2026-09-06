"""How many members a community has is answered by the membership rows.

It used to be answered by a counter that Python incremented and decremented.
That number drifted for two reasons no amount of care fixes: two people joining
at once both read the same value before writing it back, and deleting a user
takes their memberships with them (ON DELETE CASCADE) without anyone touching a
counter.

The cached column is still there and still maintained — atomically now — but it
is not what anyone is told.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.models.communityModel import CommunityMemberModel, CommunityModel
from app.models.userModel import User
from app.schemas.communitySchema import CommunityCreate
from app.services.community.communityService import CommunityService
from tests.harness import count_queries


async def _make_user(session) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"member-{uuid.uuid4().hex[:8]}@example.invalid",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(user)
    await session.commit()
    return user


async def _cached_count(session, community_id) -> int:
    return await session.scalar(
        select(CommunityModel.__table__.c.member_count).where(CommunityModel.id == community_id)
    )


async def _real_count(session, community_id) -> int:
    return await session.scalar(
        select(func.count(CommunityMemberModel.id)).where(
            CommunityMemberModel.community_id == community_id
        )
    )


@pytest.fixture
async def community(db_session, test_user):
    service = CommunityService(db_session)
    return await service.create_community(
        CommunityCreate(name=f"Compass Club {uuid.uuid4().hex[:6]}", description="Members."),
        test_user.id,
    )


@pytest.mark.asyncio
async def test_the_reported_count_is_the_number_of_memberships(db_session, community, test_user):
    service = CommunityService(db_session)
    for _ in range(3):
        joiner = await _make_user(db_session)
        await service.join_community(community.id, joiner.id)

    fresh = await db_session.scalar(
        select(CommunityModel)
        .where(CommunityModel.id == community.id)
        .execution_options(populate_existing=True)
    )
    assert fresh.member_count == 4  # creator + 3
    assert fresh.member_count == await _real_count(db_session, community.id)


async def _drop_membership_row(session, community_id, user_id) -> None:
    """Remove a membership the way a cascade does: without telling the counter.

    Deleting the *user* is what does this in production (ON DELETE CASCADE), and
    that is exercised in the PostgreSQL lane — SQLite does not enforce foreign
    keys unless asked, so a cascade here would prove nothing.
    """
    from sqlalchemy import delete

    await session.execute(
        delete(CommunityMemberModel).where(
            CommunityMemberModel.community_id == community_id,
            CommunityMemberModel.user_id == user_id,
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_memberships_removed_behind_the_counters_back_are_still_counted_right(
    db_session, community, test_user
):
    service = CommunityService(db_session)
    joiner = await _make_user(db_session)
    await service.join_community(community.id, joiner.id)

    await _drop_membership_row(db_session, community.id, joiner.id)

    fresh = await db_session.scalar(
        select(CommunityModel)
        .where(CommunityModel.id == community.id)
        .execution_options(populate_existing=True)
    )
    assert fresh.member_count == 1
    # The cache is now stale — which is exactly why it is not the answer.
    assert await _cached_count(db_session, community.id) == 2
    drift = await service.member_count_drift(community.id)
    assert drift == [
        {"community_id": community.id, "name": community.name, "cached": 2, "members": 1}
    ]


@pytest.mark.asyncio
async def test_reconciliation_repairs_the_cache_and_is_explicit(db_session, community, test_user):
    service = CommunityService(db_session)
    joiner = await _make_user(db_session)
    await service.join_community(community.id, joiner.id)
    await _drop_membership_row(db_session, community.id, joiner.id)

    repaired = await service.reconcile_member_counts(community.id)

    assert repaired == 1
    assert await _cached_count(db_session, community.id) == 1
    assert await service.member_count_drift(community.id) == []
    # Running it again finds nothing to do.
    assert await service.reconcile_member_counts(community.id) == 0


@pytest.mark.asyncio
async def test_listing_communities_does_not_write(db_session, community, test_user):
    """A GET must not repair caches: it would hide the drift and write on reads."""
    service = CommunityService(db_session)
    joiner = await _make_user(db_session)
    await service.join_community(community.id, joiner.id)
    await _drop_membership_row(db_session, community.id, joiner.id)

    cached_before = await _cached_count(db_session, community.id)
    communities = await service.list_communities()
    cached_after = await _cached_count(db_session, community.id)

    assert [c.member_count for c in communities if c.id == community.id] == [1]
    assert cached_after == cached_before


@pytest.mark.asyncio
async def test_joining_and_leaving_repeatedly_is_stable(db_session, community, test_user):
    service = CommunityService(db_session)
    joiner = await _make_user(db_session)

    for _ in range(4):
        await service.join_community(community.id, joiner.id)
        await service.leave_community(community.id, joiner.id)

    fresh = await db_session.scalar(
        select(CommunityModel)
        .where(CommunityModel.id == community.id)
        .execution_options(populate_existing=True)
    )
    assert fresh.member_count == 1
    assert await _cached_count(db_session, community.id) == 1, "the cache tracks it atomically"


@pytest.mark.asyncio
async def test_a_repeated_join_is_refused_and_changes_nothing(db_session, community, test_user):
    from app.services.community.communityService import AlreadyMemberError

    service = CommunityService(db_session)
    joiner = await _make_user(db_session)
    await service.join_community(community.id, joiner.id)

    with pytest.raises(AlreadyMemberError):
        await service.join_community(community.id, joiner.id)

    assert await _real_count(db_session, community.id) == 2
    assert await _cached_count(db_session, community.id) == 2


@pytest.mark.asyncio
async def test_listing_many_communities_stays_one_query(db_session, test_user):
    """The count is derived, not fetched per row: no N+1 hiding behind it."""
    from tests.conftest import test_engine

    service = CommunityService(db_session)
    for index in range(8):
        created = await service.create_community(
            CommunityCreate(name=f"Club {index} {uuid.uuid4().hex[:6]}"), test_user.id
        )
        joiner = await _make_user(db_session)
        await service.join_community(created.id, joiner.id)

    with count_queries(test_engine) as counter:
        communities = await service.list_communities()

    assert len(communities) >= 8
    assert counter.selects == 1, f"expected one SELECT, got: {counter.statements}"
    assert counter.writes == 0
    assert all(c.member_count >= 1 for c in communities)
