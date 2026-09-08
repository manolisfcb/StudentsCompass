"""What the planner actually does with the paged read, and what it used to do.

SQLite's query planner and its EXPLAIN say nothing about how PostgreSQL will
answer this, and the composite index only exists to change a PostgreSQL plan.
So the claim "the page is an index scan, not a sort of the whole conversation"
is made here or not at all.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.integration, pytest.mark.postgres]

KEYSET_INDEX = "ix_messages_conversation_created_id"
MESSAGE_COUNT = 20_000


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


async def _seed(session, count=MESSAGE_COUNT):
    from app.models.messageModel import ConversationModel, ConversationParticipantModel
    from app.models.userModel import User

    users = [
        User(
            id=uuid.uuid4(),
            email=f"m-{uuid.uuid4().hex[:8]}@example.invalid",
            hashed_password="x",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        for _ in range(2)
    ]
    session.add_all(users)
    await session.flush()

    conversation = ConversationModel(
        id=uuid.uuid4(),
        kind="direct",
        direct_key=":".join(sorted(str(user.id) for user in users)),
    )
    session.add(conversation)
    await session.flush()
    session.add_all(
        [
            ConversationParticipantModel(
                id=uuid.uuid4(),
                conversation_id=conversation.id,
                user_id=user.id,
                last_read_at=datetime.utcnow() - timedelta(days=365),
            )
            for user in users
        ]
    )

    # A second, equally large conversation, so filtering by conversation is not
    # free and the index has something to discriminate against.
    other = ConversationModel(id=uuid.uuid4(), kind="direct", direct_key=uuid.uuid4().hex)
    session.add(other)
    await session.flush()
    await session.commit()

    base = datetime.utcnow() - timedelta(days=60)
    for conversation_id in (conversation.id, other.id):
        rows = [
            {
                "id": uuid.uuid4(),
                "conversation_id": conversation_id,
                "sender_id": users[0].id,
                "content": f"message-{index:06d}",
                # Groups of 7 sharing a timestamp: the tie-break case.
                "created_at": base + timedelta(seconds=index // 7),
                "updated_at": base + timedelta(seconds=index // 7),
            }
            for index in range(count)
        ]
        for start in range(0, len(rows), 2000):
            await session.execute(
                text(
                    "INSERT INTO messages (id, conversation_id, sender_id, content, "
                    "created_at, updated_at) VALUES "
                    "(:id, :conversation_id, :sender_id, :content, :created_at, :updated_at)"
                ),
                rows[start : start + 2000],
            )
        await session.commit()
    await session.execute(text("ANALYZE messages"))
    await session.commit()
    return users[0], conversation


async def _explain(session, sql, params):
    result = await session.execute(text(f"EXPLAIN (ANALYZE, BUFFERS) {sql}"), params)
    return "\n".join(row[0] for row in result.all())


@pytest.mark.asyncio
async def test_the_newest_page_is_an_index_scan_and_the_old_read_was_not(
    schema, pg_sessionmaker
):
    from app.services.community.messageService import MessageService

    async with pg_sessionmaker() as session:
        _user, conversation = await _seed(session)
        params = {"cid": conversation.id, "limit": MessageService.MAX_MESSAGE_PAGE_SIZE}

        paged_plan = await _explain(
            session,
            "SELECT * FROM messages WHERE conversation_id = :cid "
            "ORDER BY created_at DESC, id DESC LIMIT :limit",
            params,
        )
        legacy_plan = await _explain(
            session,
            "SELECT * FROM messages WHERE conversation_id = :cid ORDER BY created_at ASC",
            {"cid": conversation.id},
        )

    # The page walks the keyset index backwards and stops.
    assert KEYSET_INDEX in paged_plan, paged_plan
    assert "Seq Scan" not in paged_plan, paged_plan

    # The unbounded read has to produce every row of the conversation.
    legacy_rows = _actual_rows(legacy_plan)
    paged_rows = _actual_rows(paged_plan)
    assert legacy_rows >= MESSAGE_COUNT, legacy_plan
    assert paged_rows <= MessageService.MAX_MESSAGE_PAGE_SIZE, paged_plan


def _actual_rows(plan: str) -> int:
    """Rows the top node actually produced, from EXPLAIN ANALYZE output."""
    import re

    match = re.search(r"rows=(\d+) loops=(\d+)\)", plan)
    assert match, plan
    return int(match.group(1)) * int(match.group(2))


@pytest.mark.asyncio
async def test_paging_backwards_with_a_cursor_stays_on_the_index(schema, pg_sessionmaker):
    from app.services.community.messageService import MessageService

    async with pg_sessionmaker() as session:
        user, conversation = await _seed(session)
        service = MessageService(session)
        first_page = await service.list_message_page(
            conversation_id=conversation.id, user_id=user.id, limit=200
        )
        assert first_page.next_cursor

        created_at, identifier = MessageService.decode_message_cursor(first_page.next_cursor)
        plan = await _explain(
            session,
            "SELECT * FROM messages WHERE conversation_id = :cid "
            "AND (created_at, id) < (:ts, :mid) "
            "ORDER BY created_at DESC, id DESC LIMIT 200",
            {"cid": conversation.id, "ts": created_at, "mid": identifier},
        )

    assert KEYSET_INDEX in plan, plan
    assert "Seq Scan" not in plan, plan
    assert _actual_rows(plan) <= 200, plan


@pytest.mark.asyncio
async def test_the_whole_conversation_walks_without_gaps_on_postgresql(
    schema, pg_sessionmaker
):
    """The same guarantee as the SQLite lane, on the engine that will run it."""
    from app.services.community.messageService import MessageService

    async with pg_sessionmaker() as session:
        user, conversation = await _seed(session, count=3_000)
        service = MessageService(session)

        collected: list[str] = []
        cursor = None
        while True:
            page = await service.list_message_page(
                conversation_id=conversation.id, user_id=user.id, before=cursor, limit=200
            )
            collected = [item.content for item in page.items] + collected
            if not page.has_more:
                break
            cursor = page.next_cursor

        assert len(collected) == 3_000
        assert len(set(collected)) == 3_000


@pytest.mark.asyncio
async def test_the_response_payload_is_bounded_in_bytes(schema, pg_sessionmaker):
    """What the client actually receives, before and after."""
    import json

    from app.services.community.messageService import MessageService

    async with pg_sessionmaker() as session:
        user, conversation = await _seed(session, count=5_000)
        service = MessageService(session)

        page = await service.list_message_page(
            conversation_id=conversation.id, user_id=user.id, limit=200
        )
        paged_bytes = len(json.dumps([item.model_dump(mode="json") for item in page.items]))

        # What the unbounded read would have serialised.
        every = await session.execute(
            text("SELECT COUNT(*) FROM messages WHERE conversation_id = :cid"),
            {"cid": conversation.id},
        )
        total = int(every.scalar())

    assert total == 5_000
    # One page is at most 200/5000 of the history, and a fixed ceiling however
    # long the conversation gets.
    assert paged_bytes < 100_000, paged_bytes
    assert len(page.items) == 200
