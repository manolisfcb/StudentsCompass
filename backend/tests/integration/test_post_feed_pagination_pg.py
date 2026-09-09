"""What the planner does with the feed page, and what it did before.

SQLite's planner says nothing about how PostgreSQL answers this, and
``ix_posts_created_at_id`` exists only to change a PostgreSQL plan. So the
claim "the page is a bounded index scan, not a sort of every post on the
platform" is made here or not at all.

The measured difference is not the ``LIMIT``: bounding the read on its own
still costs a sequential scan and a top-N sort of the whole table. The index is
what turns the page into a walk of exactly the rows returned.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, text

pytestmark = [pytest.mark.integration, pytest.mark.postgres]

KEYSET_INDEX = "ix_posts_created_at_id"
POST_COUNT = 20_000
TIMESTAMP_GROUP = 7


@pytest.fixture
def _models():
    import tests.conftest  # noqa: F401

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


async def _seed(session, count=POST_COUNT):
    from app.models.postModel import PostModel
    from app.models.userModel import User

    author = User(
        id=uuid.uuid4(),
        email=f"feed-{uuid.uuid4().hex[:8]}@example.invalid",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(author)
    await session.flush()

    base = datetime(2026, 1, 1, 12, 0, 0)
    session.add_all(
        PostModel(
            id=uuid.uuid4(),
            caption=f"post {index}",
            url="https://example.invalid/p.jpg",
            file_type="image",
            file_name="p.jpg",
            user_id=author.id,
            created_at=base + timedelta(seconds=index // TIMESTAMP_GROUP),
        )
        for index in range(count)
    )
    await session.commit()
    await session.execute(text("ANALYZE posts"))
    return author


@pytest.mark.asyncio
async def test_the_keyset_index_exists_on_postgresql(schema, pg_session):
    result = await pg_session.execute(
        text("SELECT indexname FROM pg_indexes WHERE tablename = 'posts'")
    )
    assert KEYSET_INDEX in set(result.scalars().all())


@pytest.mark.asyncio
async def test_the_first_page_is_an_index_scan_not_a_sort(schema, pg_session):
    """The plan's shape, which is what does not depend on the row count.

    Before this task the same read had no ``LIMIT`` at all and sorted every
    post on the platform.
    """
    await _seed(pg_session)

    plan = await pg_session.execute(
        text(
            "EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM posts "
            "ORDER BY created_at DESC, id DESC LIMIT 100"
        )
    )
    plan_text = "\n".join(row[0] for row in plan)

    assert KEYSET_INDEX in plan_text
    assert "Seq Scan" not in plan_text
    assert "Sort Method" not in plan_text


@pytest.mark.asyncio
async def test_the_cursor_page_stays_inside_the_index(schema, pg_session):
    """The row-value comparison must become an ``Index Cond``, not a filter.

    Written as ``created_at < x OR (created_at = x AND id < y)`` it would be a
    filter applied after the scan, and the tie-break would cost rows read and
    thrown away.
    """
    from app.services.community.postService import PostService

    await _seed(pg_session)
    service = PostService(pg_session)
    first = await service.list_post_page(limit=100)
    assert first.next_cursor is not None

    from app.core.pagination import decode_cursor

    created_at, identifier = decode_cursor(first.next_cursor)
    plan = await pg_session.execute(
        text(
            "EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM posts "
            "WHERE (created_at, id) < (:created_at, :identifier) "
            "ORDER BY created_at DESC, id DESC LIMIT 100"
        ),
        {"created_at": created_at, "identifier": identifier},
    )
    plan_text = "\n".join(row[0] for row in plan)

    assert KEYSET_INDEX in plan_text
    assert "Index Cond" in plan_text
    assert "Seq Scan" not in plan_text


@pytest.mark.asyncio
async def test_the_whole_feed_is_walked_without_gaps_on_postgresql(schema, pg_session):
    """SQLite orders NULLs and ties differently enough to be worth repeating."""
    from app.models.postModel import PostModel
    from app.services.community.postService import PostService

    await _seed(pg_session, count=2_000)
    service = PostService(pg_session)

    seen = []
    cursor = None
    while True:
        page = await service.list_post_page(before=cursor, limit=100)
        seen.extend(item.id for item in page.items)
        cursor = page.next_cursor
        if cursor is None:
            break

    canonical = await pg_session.execute(
        select(PostModel.id).order_by(PostModel.created_at.desc(), PostModel.id.desc())
    )
    assert seen == list(canonical.scalars().all())
    assert len(set(seen)) == 2_000
