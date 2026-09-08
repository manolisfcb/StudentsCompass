import uuid

import pytest
from fastapi_users.password import PasswordHelper
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.friendshipModel import FriendshipModel
from app.models.userModel import User


async def create_user(
    db_session: AsyncSession,
    *,
    email: str,
    nickname: str,
    first_name: str,
    last_name: str,
    password: str = "password123",
) -> User:
    helper = PasswordHelper()
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=helper.hash(password),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        nickname=nickname,
        first_name=first_name,
        last_name=last_name,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def make_friends(db_session: AsyncSession, first_user: User, second_user: User) -> None:
    db_session.add(FriendshipModel(user_id=first_user.id, friend_id=second_user.id))
    db_session.add(FriendshipModel(user_id=second_user.id, friend_id=first_user.id))
    await db_session.commit()


async def login(client: AsyncClient, *, email: str, password: str = "password123") -> None:
    response = await client.post(
        "/auth/jwt/login",
        data={"username": email, "password": password},
    )
    assert response.status_code in (200, 204)


async def logout(client: AsyncClient) -> None:
    response = await client.post("/auth/jwt/logout")
    assert response.status_code in (200, 204)


@pytest.mark.asyncio
async def test_user_can_start_direct_conversation_with_friend(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    friend = await create_user(
        db_session,
        email="dmfriend@example.com",
        nickname="dmfriend",
        first_name="Direct",
        last_name="Friend",
    )
    await make_friends(db_session, test_user, friend)

    await login(client, email=test_user.email)
    response = await client.post(
        "/api/v1/conversations/direct",
        json={"friend_id": str(friend.id)},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["kind"] == "direct"
    assert payload["other_user"]["id"] == str(friend.id)
    assert payload["unread_count"] == 0


@pytest.mark.asyncio
async def test_user_cannot_start_direct_conversation_with_non_friend(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    stranger = await create_user(
        db_session,
        email="stranger@example.com",
        nickname="stranger",
        first_name="Not",
        last_name="Friend",
    )

    await login(client, email=test_user.email)
    response = await client.post(
        "/api/v1/conversations/direct",
        json={"friend_id": str(stranger.id)},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "You can only start chats with friends"


@pytest.mark.asyncio
async def test_direct_conversation_is_reused_for_same_friend_pair(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    friend = await create_user(
        db_session,
        email="reuse@example.com",
        nickname="reuse",
        first_name="Reuse",
        last_name="Pair",
    )
    await make_friends(db_session, test_user, friend)

    await login(client, email=test_user.email)
    first = await client.post("/api/v1/conversations/direct", json={"friend_id": str(friend.id)})
    second = await client.post("/api/v1/conversations/direct", json={"friend_id": str(friend.id)})

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.asyncio
async def test_friends_can_send_and_list_messages(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    friend = await create_user(
        db_session,
        email="messages@example.com",
        nickname="messages",
        first_name="Message",
        last_name="Buddy",
    )
    await make_friends(db_session, test_user, friend)

    await login(client, email=test_user.email)
    conversation = await client.post("/api/v1/conversations/direct", json={"friend_id": str(friend.id)})
    conversation_id = conversation.json()["id"]

    send_response = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Hey, want to prep interviews together this week?"},
    )
    assert send_response.status_code == 201
    assert send_response.json()["is_mine"] is True

    await logout(client)
    await login(client, email=friend.email)

    list_response = await client.get(f"/api/v1/conversations/{conversation_id}/messages")
    assert list_response.status_code == 200
    messages = list_response.json()
    assert len(messages) == 1
    assert messages[0]["content"] == "Hey, want to prep interviews together this week?"
    assert messages[0]["is_mine"] is False


@pytest.mark.asyncio
async def test_list_conversations_tracks_unread_and_mark_read(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    friend = await create_user(
        db_session,
        email="unread@example.com",
        nickname="unread",
        first_name="Unread",
        last_name="Buddy",
    )
    await make_friends(db_session, test_user, friend)

    await login(client, email=test_user.email)
    conversation = await client.post("/api/v1/conversations/direct", json={"friend_id": str(friend.id)})
    conversation_id = conversation.json()["id"]
    await logout(client)

    await login(client, email=friend.email)
    await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Yes, let us do a mock interview tomorrow."},
    )

    await logout(client)
    await login(client, email=test_user.email)

    before_read = await client.get("/api/v1/conversations")
    assert before_read.status_code == 200
    assert before_read.json()[0]["unread_count"] == 1

    read_response = await client.post(f"/api/v1/conversations/{conversation_id}/read")
    assert read_response.status_code == 200

    after_read = await client.get("/api/v1/conversations")
    assert after_read.status_code == 200
    assert after_read.json()[0]["unread_count"] == 0


@pytest.mark.asyncio
async def test_non_participant_cannot_view_or_send_messages(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    friend = await create_user(
        db_session,
        email="participant@example.com",
        nickname="participant",
        first_name="Participant",
        last_name="Friend",
    )
    stranger = await create_user(
        db_session,
        email="outsider@example.com",
        nickname="outsider",
        first_name="Outside",
        last_name="Viewer",
    )
    await make_friends(db_session, test_user, friend)

    await login(client, email=test_user.email)
    conversation = await client.post("/api/v1/conversations/direct", json={"friend_id": str(friend.id)})
    conversation_id = conversation.json()["id"]
    await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Private message"},
    )

    await logout(client)
    await login(client, email=stranger.email)

    list_response = await client.get(f"/api/v1/conversations/{conversation_id}/messages")
    assert list_response.status_code == 404

    send_response = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "I should not be here"},
    )
    assert send_response.status_code == 404
