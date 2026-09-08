"""How many members a community has, settled under real concurrency.

The counter column drifted for two reasons SQLite cannot reproduce: two people
joining at the same instant on separate connections both read the same number
before writing it back, and deleting a user takes their memberships with them
through ON DELETE CASCADE without anyone touching a counter.

The answer served to clients is derived from ``community_members``, so these
tests assert that what a reader sees always equals COUNT(*) — and, separately,
that the surviving cache column moves atomically and can be reconciled.

Sessions are opened per block and closed before the schema fixture tears down:
a session left open in a transaction would block ``DROP TABLE`` forever.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import func, select

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


@pytest.fixture
def _models():
    import tests.conftest  # noqa: F401  (imports the full model set)
    from app.db import Base

    return Base


@pytest.fixture
async def schema(pg_engine, _models):
    async with pg_engine.begin() as conn:
        await conn.run_sync(_models.metadata.create_all)
    try:
        yield
    finally:
        async with pg_engine.begin() as conn:
            await conn.run_sync(_models.metadata.drop_all)


async def _make_user(session):
    from app.models.userModel import User

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


async def _seed_community(session):
    """A community with only its creator in it. Returns (community_id, owner)."""
    from app.schemas.communitySchema import CommunityCreate
    from app.services.community.communityService import CommunityService

    owner = await _make_user(session)
    created = await CommunityService(session).create_community(
        CommunityCreate(name=f"Compass Club {uuid.uuid4().hex[:6]}", description="Members."),
        owner.id,
    )
    return created.id, owner


async def _real_count(session, community_id) -> int:
    from app.models.communityModel import CommunityMemberModel

    return await session.scalar(
        select(func.count(CommunityMemberModel.id)).where(
            CommunityMemberModel.community_id == community_id
        )
    )


async def _cached_count(session, community_id) -> int:
    from app.models.communityModel import CommunityModel

    return await session.scalar(
        select(CommunityModel.__table__.c.member_count).where(CommunityModel.id == community_id)
    )


async def _served_count(session, community_id) -> int:
    """What a reader is actually told, loaded fresh from the database."""
    from app.models.communityModel import CommunityModel

    community = await session.scalar(
        select(CommunityModel)
        .where(CommunityModel.id == community_id)
        .execution_options(populate_existing=True)
    )
    return community.member_count


@pytest.mark.asyncio
async def test_simultaneous_joins_on_separate_connections_are_all_counted(
    schema, pg_sessionmaker
):
    """Six concurrent joins, six memberships — and six is what a reader sees."""
    from app.services.community.communityService import CommunityService

    async with pg_sessionmaker() as setup:
        community_id, _owner = await _seed_community(setup)
        joiners = [await _make_user(setup) for _ in range(6)]

    async def join(user_id):
        async with pg_sessionmaker() as session:
            await CommunityService(session).join_community(community_id, user_id)

    await asyncio.gather(*(join(user.id) for user in joiners))

    async with pg_sessionmaker() as check:
        assert await _real_count(check, community_id) == 7  # creator + 6
        assert await _served_count(check, community_id) == 7
        # The cache moves in SQL, so concurrent writers cannot lose each
        # other's increments either.
        assert await _cached_count(check, community_id) == 7


@pytest.mark.asyncio
async def test_simultaneous_joins_and_leaves_leave_the_count_exact(schema, pg_sessionmaker):
    from app.services.community.communityService import CommunityService

    async with pg_sessionmaker() as setup:
        community_id, _owner = await _seed_community(setup)
        stayers = [await _make_user(setup) for _ in range(4)]
        leavers = [await _make_user(setup) for _ in range(4)]
        for user in leavers:
            await CommunityService(setup).join_community(community_id, user.id)

    async def join(user_id):
        async with pg_sessionmaker() as session:
            await CommunityService(session).join_community(community_id, user_id)

    async def leave(user_id):
        async with pg_sessionmaker() as session:
            await CommunityService(session).leave_community(community_id, user_id)

    await asyncio.gather(
        *(join(user.id) for user in stayers),
        *(leave(user.id) for user in leavers),
    )

    async with pg_sessionmaker() as check:
        assert await _real_count(check, community_id) == 5  # creator + 4 stayers
        assert await _served_count(check, community_id) == 5
        assert await _cached_count(check, community_id) == 5


@pytest.mark.asyncio
async def test_the_same_user_joining_twice_at_once_is_counted_once(schema, pg_sessionmaker):
    """The unique constraint decides; the loser gets a conflict, not a count."""
    from app.services.community.communityService import AlreadyMemberError, CommunityService

    async with pg_sessionmaker() as setup:
        community_id, _owner = await _seed_community(setup)
        joiner = await _make_user(setup)

    async def join():
        async with pg_sessionmaker() as session:
            try:
                await CommunityService(session).join_community(community_id, joiner.id)
                return "joined"
            except AlreadyMemberError:
                return "refused"

    outcomes = await asyncio.gather(join(), join())

    # Under real contention the second insert loses on the constraint rather
    # than on the pre-check; either way exactly one membership exists.
    assert outcomes.count("joined") == 1
    assert outcomes.count("refused") == 1
    async with pg_sessionmaker() as check:
        assert await _real_count(check, community_id) == 2  # creator + joiner
        assert await _served_count(check, community_id) == 2
        assert await _cached_count(check, community_id) == 2


@pytest.mark.asyncio
async def test_deleting_a_user_cascades_and_the_served_count_follows(schema, pg_sessionmaker):
    """ON DELETE CASCADE removes memberships; the derived count notices."""
    from app.models.userModel import User
    from app.services.community.communityService import CommunityService

    async with pg_sessionmaker() as session:
        community_id, _owner = await _seed_community(session)
        service = CommunityService(session)
        joiner = await _make_user(session)
        await service.join_community(community_id, joiner.id)
        assert await _served_count(session, community_id) == 2

        await session.execute(User.__table__.delete().where(User.__table__.c.id == joiner.id))
        await session.commit()

        assert await _real_count(session, community_id) == 1
        assert await _served_count(session, community_id) == 1
        # Nothing updated the cache — precisely why it is not the answer.
        assert await _cached_count(session, community_id) == 2
        drift = await service.member_count_drift(community_id)
        assert [(entry["cached"], entry["members"]) for entry in drift] == [(2, 1)]

        assert await service.reconcile_member_counts(community_id) == 1
        assert await _cached_count(session, community_id) == 1
        assert await service.member_count_drift(community_id) == []


@pytest.mark.asyncio
async def test_listing_communities_is_one_query_regardless_of_how_many(
    schema, pg_sessionmaker, pg_query_counter
):
    """The derived count is a correlated subquery, not a per-row lookup."""
    from app.schemas.communitySchema import CommunityCreate
    from app.services.community.communityService import CommunityService

    async with pg_sessionmaker() as session:
        service = CommunityService(session)
        owner = await _make_user(session)
        for index in range(8):
            created = await service.create_community(
                CommunityCreate(name=f"Club {index} {uuid.uuid4().hex[:6]}"), owner.id
            )
            joiner = await _make_user(session)
            await service.join_community(created.id, joiner.id)

        with pg_query_counter() as counter:
            communities = await service.list_communities()

        assert len(communities) >= 8
        assert all(item.member_count == 2 for item in communities)
        assert counter.total == 1
