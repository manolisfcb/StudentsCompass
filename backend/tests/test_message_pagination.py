"""A conversation is walked one bounded page at a time, with nothing lost or repeated.

``GET /conversations/{id}/messages`` selected every message the conversation had
ever contained and serialised all of them. Two years of chat was one response.

The replacement is a keyset cursor over ``(created_at, id)``. The pair matters:
messages sent in the same millisecond are ordinary — a client retrying, two
people answering at once — and a cursor on the timestamp alone makes the
boundary between pages ambiguous, so a message either repeats or vanishes.
Every test here that seeds history seeds it with **repeated timestamps** for
exactly that reason.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.messageModel import ConversationModel, ConversationParticipantModel, MessageModel
from app.services.community.messageService import InvalidMessageCursor, MessageService
from tests.harness import count_queries
from tests.test_messages import create_user, login, make_friends

TIMESTAMP_GROUP_SIZE = 7


async def _conversation(db_session, first_user, second_user):
    conversation = ConversationModel(
        id=uuid.uuid4(),
        kind="direct",
        direct_key=":".join(sorted([str(first_user.id), str(second_user.id)])),
    )
    db_session.add(conversation)
    await db_session.flush()
    # Older than anything ``_seed_messages`` writes, so seeded history counts as
    # unread. A "read just now" participant would make every unread assertion
    # below trivially zero.
    last_read_at = datetime.utcnow() - timedelta(days=365)
    db_session.add_all(
        [
            ConversationParticipantModel(
                id=uuid.uuid4(),
                conversation_id=conversation.id,
                user_id=user.id,
                last_read_at=last_read_at,
            )
            for user in (first_user, second_user)
        ]
    )
    await db_session.commit()
    return conversation


async def _seed_messages(db_session, conversation, sender, count):
    """``count`` messages, in groups sharing one timestamp to the microsecond."""
    base = datetime.utcnow() - timedelta(days=30)
    messages = []
    for index in range(count):
        created_at = base + timedelta(seconds=index // TIMESTAMP_GROUP_SIZE)
        messages.append(
            MessageModel(
                id=uuid.uuid4(),
                conversation_id=conversation.id,
                sender_id=sender.id,
                content=f"message-{index:05d}",
                created_at=created_at,
                updated_at=created_at,
            )
        )
    db_session.add_all(messages)
    await db_session.commit()
    return messages


async def _canonical_order(db_session, conversation_id) -> list[str]:
    """What ``(created_at, id)`` ordering means, asked of the database directly.

    Not insertion order: inside a group of messages sharing a timestamp the
    tie-break is the id, which is a random UUID. That is still a total, stable
    order — which is all a keyset cursor needs — but it is not the order the
    rows were added in, so the walk is compared against this rather than
    against the seeding loop.
    """
    result = await db_session.execute(
        select(MessageModel.content)
        .where(MessageModel.conversation_id == conversation_id)
        .order_by(MessageModel.created_at.asc(), MessageModel.id.asc())
    )
    return [row[0] for row in result.all()]


async def _walk_everything(service, conversation_id, user_id, *, limit):
    """Page backwards to the beginning, collecting contents oldest-first."""
    collected: list[str] = []
    cursor = None
    pages = 0
    while True:
        page = await service.list_message_page(
            conversation_id=conversation_id, user_id=user_id, before=cursor, limit=limit
        )
        collected = [item.content for item in page.items] + collected
        pages += 1
        assert len(page.items) <= limit
        if not page.has_more:
            assert page.next_cursor is None
            break
        cursor = page.next_cursor
        assert cursor is not None
        assert pages < 10_000, "the walk is not terminating"
    return collected, pages


@pytest.fixture
async def conversation_pair(db_session):
    first = await create_user(
        db_session,
        email=f"a-{uuid.uuid4().hex[:8]}@example.invalid",
        nickname=f"a{uuid.uuid4().hex[:6]}",
        first_name="Ana",
        last_name="Ruiz",
    )
    second = await create_user(
        db_session,
        email=f"b-{uuid.uuid4().hex[:8]}@example.invalid",
        nickname=f"b{uuid.uuid4().hex[:6]}",
        first_name="Beto",
        last_name="Diaz",
    )
    await make_friends(db_session, first, second)
    conversation = await _conversation(db_session, first, second)
    return first, second, conversation


# ---------------------------------------------------------------------------
# The walk
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ten_thousand_messages_with_repeated_timestamps_are_walked_exactly_once(
    db_session, conversation_pair
):
    """The case the cursor exists for."""
    first, _second, conversation = conversation_pair
    await _seed_messages(db_session, conversation, first, 10_000)
    service = MessageService(db_session)

    collected, pages = await _walk_everything(
        service, conversation.id, first.id, limit=MessageService.MAX_MESSAGE_PAGE_SIZE
    )

    expected = await _canonical_order(db_session, conversation.id)
    assert len(collected) == 10_000
    assert len(set(collected)) == 10_000, "a message was returned twice"
    assert collected == expected, "the walk lost or reordered messages"
    assert pages == 50


@pytest.mark.asyncio
async def test_the_same_history_walks_identically_at_every_page_size(
    db_session, conversation_pair
):
    """Page size changes the number of requests, never the content."""
    first, _second, conversation = conversation_pair
    await _seed_messages(db_session, conversation, first, 137)
    service = MessageService(db_session)

    walks = {}
    for limit in (1, 7, 50, 200):
        walks[limit], _pages = await _walk_everything(
            service, conversation.id, first.id, limit=limit
        )

    assert len({tuple(walk) for walk in walks.values()}) == 1
    assert len(walks[1]) == 137


@pytest.mark.asyncio
async def test_a_message_sent_mid_walk_does_not_shift_the_pages(db_session, conversation_pair):
    """An offset would skip a message here; a keyset cursor cannot."""
    first, _second, conversation = conversation_pair
    await _seed_messages(db_session, conversation, first, 60)
    service = MessageService(db_session)

    newest = await service.list_message_page(
        conversation_id=conversation.id, user_id=first.id, limit=20
    )
    # Somebody says something while the client is still scrolling back.
    await service.send_message(
        conversation_id=conversation.id, sender_id=first.id, content="interrupting"
    )

    older = await service.list_message_page(
        conversation_id=conversation.id, user_id=first.id, before=newest.next_cursor, limit=20
    )

    contents = [item.content for item in newest.items] + [item.content for item in older.items]
    assert "interrupting" not in contents
    assert len(set(contents)) == 40, "a message was skipped or repeated"


# ---------------------------------------------------------------------------
# The bound
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_payload_is_capped_however_much_is_asked_for(db_session, conversation_pair):
    first, _second, conversation = conversation_pair
    await _seed_messages(db_session, conversation, first, 1_000)
    service = MessageService(db_session)

    for requested in (500, 10_000, -1, 0):
        page = await service.list_message_page(
            conversation_id=conversation.id, user_id=first.id, limit=requested
        )
        assert 1 <= len(page.items) <= MessageService.MAX_MESSAGE_PAGE_SIZE
        assert page.limit <= MessageService.MAX_MESSAGE_PAGE_SIZE


@pytest.mark.asyncio
async def test_the_legacy_endpoint_returns_the_newest_page_not_the_whole_history(
    db_session, conversation_pair
):
    """The shape is unchanged; the size is not."""
    first, _second, conversation = conversation_pair
    await _seed_messages(db_session, conversation, first, 1_000)
    service = MessageService(db_session)

    legacy = await service.list_messages(conversation_id=conversation.id, user_id=first.id)

    assert isinstance(legacy, list)
    assert len(legacy) == MessageService.DEFAULT_MESSAGE_PAGE_SIZE
    # The newest messages, in conversation order, so a client that scrolls to
    # the bottom still shows the right thing.
    canonical = await _canonical_order(db_session, conversation.id)
    assert [item.content for item in legacy] == canonical[
        -MessageService.DEFAULT_MESSAGE_PAGE_SIZE :
    ]


@pytest.mark.asyncio
async def test_the_number_of_queries_does_not_grow_with_the_history(
    db_session, conversation_pair
):
    first, _second, conversation = conversation_pair
    from tests.conftest import test_engine

    await _seed_messages(db_session, conversation, first, 50)
    service = MessageService(db_session)
    with count_queries(test_engine) as small:
        await service.list_message_page(conversation_id=conversation.id, user_id=first.id)

    await _seed_messages(db_session, conversation, first, 5_000)
    with count_queries(test_engine) as large:
        await service.list_message_page(conversation_id=conversation.id, user_id=first.id)

    assert small.selects == large.selects
    assert large.selects <= 3


# ---------------------------------------------------------------------------
# Cursors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_cursor_round_trips(db_session, conversation_pair):
    first, _second, conversation = conversation_pair
    seeded = await _seed_messages(db_session, conversation, first, 3)
    message = seeded[0]

    cursor = MessageService.encode_message_cursor(message)
    created_at, identifier = MessageService.decode_message_cursor(cursor)

    assert identifier == message.id
    assert created_at == message.created_at


@pytest.mark.parametrize(
    "cursor", ["", "not-base64", "!!!!", "YWJj", "MjAyNi0wMS0wMXxub3QtYS11dWlk"]
)
def test_a_malformed_cursor_is_refused_rather_than_ignored(cursor):
    """Silently dropping the filter would return the wrong page as if it were right."""
    with pytest.raises(InvalidMessageCursor):
        MessageService.decode_message_cursor(cursor)


@pytest.mark.asyncio
async def test_the_endpoint_answers_400_for_a_bad_cursor(client, db_session, conversation_pair):
    first, _second, conversation = conversation_pair
    await login(client, email=first.email)

    response = await client.get(
        f"/api/v1/conversations/{conversation.id}/messages/page",
        params={"before": "definitely-not-a-cursor"},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Authorisation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_stranger_cannot_page_someone_elses_conversation(
    client, db_session, conversation_pair
):
    first, _second, conversation = conversation_pair
    await _seed_messages(db_session, conversation, first, 10)
    stranger = await create_user(
        db_session,
        email=f"x-{uuid.uuid4().hex[:8]}@example.invalid",
        nickname=f"x{uuid.uuid4().hex[:6]}",
        first_name="Eve",
        last_name="Stranger",
    )
    await login(client, email=stranger.email)

    for path in ("messages", "messages/page"):
        response = await client.get(f"/api/v1/conversations/{conversation.id}/{path}")
        # The same answer as a conversation that does not exist: confirming it
        # exists would itself be a disclosure.
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_a_participant_pages_their_own_conversation(client, db_session, conversation_pair):
    first, _second, conversation = conversation_pair
    await _seed_messages(db_session, conversation, first, 120)
    await login(client, email=first.email)

    response = await client.get(
        f"/api/v1/conversations/{conversation.id}/messages/page", params={"limit": 25}
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 25
    assert payload["has_more"] is True
    assert payload["next_cursor"]
    assert payload["limit"] == 25
    assert all(item["is_mine"] for item in payload["items"])


@pytest.mark.asyncio
async def test_unread_counts_and_conversation_order_are_untouched(
    client, db_session, conversation_pair
):
    """Pagination must not disturb what the inbox list reports."""
    first, second, conversation = conversation_pair
    await _seed_messages(db_session, conversation, second, 300)

    service = MessageService(db_session)
    summaries = await service.list_conversations(first.id)

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.id == conversation.id
    assert summary.unread_count == 300
    assert summary.last_message_preview is not None


@pytest.mark.asyncio
async def test_an_empty_conversation_pages_to_nothing(db_session, conversation_pair):
    first, _second, conversation = conversation_pair
    page = await MessageService(db_session).list_message_page(
        conversation_id=conversation.id, user_id=first.id
    )

    assert page.items == []
    assert page.has_more is False
    assert page.next_cursor is None
