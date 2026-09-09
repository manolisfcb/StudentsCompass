"""TASK-061 — the community feed, walked with a stable cursor.

The feed was the one listing in F-22 not scoped to a user: ``SELECT * FROM
posts ORDER BY created_at DESC`` with no ``LIMIT``, so its cost grew with the
whole platform's activity and every reader paid it.

The tests seed **repeated timestamps on purpose** (groups of 7). Posts created
in the same instant are ordinary — a seeded batch, two people posting at once —
and they are exactly the case a cursor over ``created_at`` alone gets wrong, by
either repeating a post or dropping it at the page boundary.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import MAX_COLLECTION_ROWS
from app.models.postModel import PostModel
from app.models.userModel import User
from app.services.community.postService import InvalidPostCursor, PostService

#: Posts sharing one timestamp. The tie-break is what is under test.
TIMESTAMP_GROUP = 7


async def seed_posts(session: AsyncSession, *, author: User, count: int) -> list[PostModel]:
    """Seed ``count`` posts, in groups of seven sharing a created_at."""
    base = datetime(2026, 1, 1, 12, 0, 0)
    posts = []
    for index in range(count):
        posts.append(
            PostModel(
                id=uuid.uuid4(),
                caption=f"post {index}",
                url=f"https://example.com/{index}.jpg",
                file_type="image",
                file_name=f"{index}.jpg",
                user_id=author.id,
                created_at=base + timedelta(seconds=index // TIMESTAMP_GROUP),
            )
        )
    session.add_all(posts)
    await session.commit()
    return posts


async def canonical_order(session: AsyncSession) -> list[uuid.UUID]:
    """The order the database itself considers canonical.

    Asked of the database rather than assumed from the seeding loop: within a
    group sharing a timestamp the tie-break is the random UUID, which is a
    total, stable order but not insertion order.
    """
    result = await session.execute(
        select(PostModel.id).order_by(PostModel.created_at.desc(), PostModel.id.desc())
    )
    return list(result.scalars().all())


class TestFeedPage:
    @pytest.mark.asyncio
    async def test_the_whole_feed_is_walked_exactly_once(
        self, db_session: AsyncSession, test_user: User
    ):
        """Ten thousand posts, fifty pages, no gaps and no repeats."""
        total = 10_000
        page_size = PostService.MAX_POST_PAGE_SIZE
        await seed_posts(db_session, author=test_user, count=total)
        service = PostService(db_session)

        seen: list[uuid.UUID] = []
        cursor = None
        pages = 0
        while True:
            page = await service.list_post_page(before=cursor, limit=page_size)
            seen.extend(item.id for item in page.items)
            pages += 1
            cursor = page.next_cursor
            if cursor is None:
                break
            assert pages < 200, "the walk is not terminating"

        assert pages == total // page_size
        assert len(seen) == total
        assert len(set(seen)) == total
        assert seen == await canonical_order(db_session)

    @pytest.mark.parametrize("page_size", [1, 7, 20, 100])
    @pytest.mark.asyncio
    async def test_the_same_feed_is_identical_at_every_page_size(
        self, db_session: AsyncSession, test_user: User, page_size: int
    ):
        """Page size is a transport detail; it must not change what is read."""
        await seed_posts(db_session, author=test_user, count=200)
        service = PostService(db_session)

        seen: list[uuid.UUID] = []
        cursor = None
        while True:
            page = await service.list_post_page(before=cursor, limit=page_size)
            assert len(page.items) <= page_size
            seen.extend(item.id for item in page.items)
            cursor = page.next_cursor
            if cursor is None:
                break

        assert seen == await canonical_order(db_session)

    @pytest.mark.asyncio
    async def test_a_post_published_mid_walk_does_not_shift_the_pages(
        self, db_session: AsyncSession, test_user: User
    ):
        """The reason this is a cursor and not an offset.

        A row inserted while a client pages shifts every offset after it, so an
        offset walk would skip a post. The cursor addresses a row, so the walk
        is unaffected by writes at the head of the feed.
        """
        await seed_posts(db_session, author=test_user, count=60)
        service = PostService(db_session)
        expected = await canonical_order(db_session)

        first = await service.list_post_page(limit=20)

        db_session.add(
            PostModel(
                id=uuid.uuid4(),
                caption="published mid-walk",
                url="https://example.com/new.jpg",
                file_type="image",
                file_name="new.jpg",
                user_id=test_user.id,
                created_at=datetime(2026, 6, 1, 12, 0, 0),
            )
        )
        await db_session.commit()

        seen = [item.id for item in first.items]
        cursor = first.next_cursor
        while cursor is not None:
            page = await service.list_post_page(before=cursor, limit=20)
            seen.extend(item.id for item in page.items)
            cursor = page.next_cursor

        # The new post is newer than the page already read, so it is not seen —
        # and, crucially, nothing that was in the original feed was missed.
        assert seen == expected

    @pytest.mark.parametrize("requested,expected", [(500, 100), (10_000, 100)])
    @pytest.mark.asyncio
    async def test_the_server_caps_the_page_however_much_is_asked_for(
        self, db_session: AsyncSession, test_user: User, requested: int, expected: int
    ):
        await seed_posts(db_session, author=test_user, count=300)
        service = PostService(db_session)

        page = await service.list_post_page(limit=requested)

        assert len(page.items) == expected
        assert page.limit == expected

    @pytest.mark.parametrize("requested", [0, -1])
    @pytest.mark.asyncio
    async def test_a_nonsense_page_size_lands_on_one(
        self, db_session: AsyncSession, test_user: User, requested: int
    ):
        await seed_posts(db_session, author=test_user, count=5)
        service = PostService(db_session)

        page = await service.list_post_page(limit=requested)

        assert len(page.items) == 1

    @pytest.mark.asyncio
    async def test_has_more_is_false_on_a_page_that_is_exactly_full(
        self, db_session: AsyncSession, test_user: User
    ):
        """The probe row, not ``len(items)``, decides.

        This is the boundary where guessing from a full page is wrong: the
        client would be told to follow a cursor into an empty page.
        """
        await seed_posts(db_session, author=test_user, count=20)
        service = PostService(db_session)

        page = await service.list_post_page(limit=20)

        assert len(page.items) == 20
        assert page.has_more is False
        assert page.next_cursor is None

    @pytest.mark.asyncio
    async def test_an_empty_feed_is_a_page_with_no_items(
        self, db_session: AsyncSession, test_user: User
    ):
        page = await PostService(db_session).list_post_page()

        assert page.items == []
        assert page.has_more is False
        assert page.next_cursor is None

    @pytest.mark.asyncio
    async def test_the_cursor_round_trips(self, db_session: AsyncSession, test_user: User):
        posts = await seed_posts(db_session, author=test_user, count=1)
        service = PostService(db_session)

        from app.core.pagination import decode_cursor

        cursor = service.encode_post_cursor(posts[0])

        assert decode_cursor(cursor) == (posts[0].created_at, posts[0].id)

    @pytest.mark.parametrize(
        "malformed", ["not-base64!!", "YWJj", "MjAyNi0wMS0wMXxub3QtYS11dWlk"]
    )
    @pytest.mark.asyncio
    async def test_a_malformed_cursor_is_refused(
        self, db_session: AsyncSession, malformed: str
    ):
        with pytest.raises(InvalidPostCursor):
            await PostService(db_session).list_post_page(before=malformed)

    @pytest.mark.asyncio
    async def test_an_empty_cursor_means_no_cursor(
        self, db_session: AsyncSession, test_user: User
    ):
        """``?before=`` is a client that sent the parameter without a value.

        Not an error: it is the same statement as omitting it, and it is what a
        form or a template interpolating an absent variable produces. This
        matches the message endpoint's existing behaviour rather than diverging
        from it.
        """
        await seed_posts(db_session, author=test_user, count=3)

        page = await PostService(db_session).list_post_page(before="")

        assert len(page.items) == 3


class TestFeedEndpoints:
    @pytest.mark.asyncio
    async def test_the_page_endpoint_returns_the_declared_envelope(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_user: User
    ):
        await seed_posts(db_session, author=test_user, count=50)

        response = await client.get("/api/v1/posts/page?limit=20", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"items", "next_cursor", "has_more", "limit"}
        assert len(body["items"]) == 20
        assert body["has_more"] is True
        assert body["limit"] == 20

    @pytest.mark.asyncio
    async def test_the_page_endpoint_refuses_a_malformed_cursor_with_400(
        self, client: AsyncClient, auth_headers: dict
    ):
        response = await client.get("/api/v1/posts/page?before=nonsense!", headers=auth_headers)

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_the_page_endpoint_needs_a_session(self, client: AsyncClient):
        response = await client.get("/api/v1/posts/page")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_the_legacy_list_is_bounded_and_keeps_its_shape(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_user: User
    ):
        """Same JSON shape as before — a bare array — but finite."""
        await seed_posts(db_session, author=test_user, count=MAX_COLLECTION_ROWS + 50)

        response = await client.get("/api/v1/posts", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == MAX_COLLECTION_ROWS

    @pytest.mark.asyncio
    async def test_the_legacy_list_truncates_at_the_oldest_end(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_user: User
    ):
        """A feed truncated at the newest end would be pinned to launch day."""
        await seed_posts(db_session, author=test_user, count=MAX_COLLECTION_ROWS + 50)
        newest = (await canonical_order(db_session))[:MAX_COLLECTION_ROWS]

        response = await client.get("/api/v1/posts", headers=auth_headers)

        assert [uuid.UUID(item["id"]) for item in response.json()] == newest


class TestFeedQueryBudget:
    @pytest.mark.asyncio
    async def test_a_page_costs_the_same_number_of_queries_at_any_feed_size(
        self, db_session: AsyncSession, test_user: User, query_counter
    ):
        """Constant cost per page: the point of the bound."""
        await seed_posts(db_session, author=test_user, count=50)
        service = PostService(db_session)

        with query_counter() as small:
            await service.list_post_page(limit=20)

        await seed_posts(db_session, author=test_user, count=5_000)

        with query_counter() as large:
            await service.list_post_page(limit=20)

        assert small.selects == large.selects == 1
