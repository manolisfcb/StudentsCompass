import uuid

import pytest
from fastapi_users.password import PasswordHelper
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.friendshipModel import FriendRequestModel, FriendshipModel
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
async def test_user_can_send_friend_request(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    other_user = await create_user(
        db_session,
        email="friend@example.com",
        nickname="friend",
        first_name="Friendly",
        last_name="Student",
    )

    await login(client, email=test_user.email)
    response = await client.post(
        "/api/v1/friends/requests",
        json={"receiver_id": str(other_user.id)},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["sender"]["id"] == str(test_user.id)
    assert data["receiver"]["id"] == str(other_user.id)


@pytest.mark.asyncio
async def test_duplicate_friend_request_is_blocked(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    other_user = await create_user(
        db_session,
        email="duplicate@example.com",
        nickname="duplicate",
        first_name="Duplicate",
        last_name="User",
    )

    await login(client, email=test_user.email)
    first_response = await client.post(
        "/api/v1/friends/requests",
        json={"receiver_id": str(other_user.id)},
    )
    assert first_response.status_code == 201

    second_response = await client.post(
        "/api/v1/friends/requests",
        json={"receiver_id": str(other_user.id)},
    )
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Friend request already sent"


@pytest.mark.asyncio
async def test_user_can_accept_friend_request(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    other_user = await create_user(
        db_session,
        email="accept@example.com",
        nickname="accepting",
        first_name="Accepting",
        last_name="User",
    )

    await login(client, email=test_user.email)
    send_response = await client.post(
        "/api/v1/friends/requests",
        json={"receiver_id": str(other_user.id)},
    )
    request_id = send_response.json()["id"]

    await logout(client)
    await login(client, email=other_user.email)
    accept_response = await client.post(f"/api/v1/friends/requests/{request_id}/accept")

    assert accept_response.status_code == 200
    data = accept_response.json()
    assert data["status"] == "accepted"

    friendships = await db_session.execute(select(FriendshipModel))
    rows = friendships.scalars().all()
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_user_can_reject_or_cancel_friend_request(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    other_user = await create_user(
        db_session,
        email="reject@example.com",
        nickname="rejecting",
        first_name="Rejecting",
        last_name="User",
    )

    await login(client, email=test_user.email)
    send_response = await client.post(
        "/api/v1/friends/requests",
        json={"receiver_id": str(other_user.id)},
    )
    request_id = send_response.json()["id"]

    await logout(client)
    await login(client, email=other_user.email)
    reject_response = await client.post(f"/api/v1/friends/requests/{request_id}/reject")

    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"

    await logout(client)
    await login(client, email=test_user.email)
    resend_response = await client.post(
        "/api/v1/friends/requests",
        json={"receiver_id": str(other_user.id)},
    )
    resend_request_id = resend_response.json()["id"]
    cancel_response = await client.post(f"/api/v1/friends/requests/{resend_request_id}/cancel")

    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    friendships = await db_session.execute(select(FriendshipModel))
    assert friendships.scalars().all() == []


@pytest.mark.asyncio
async def test_user_can_list_friends_and_requests(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    other_user = await create_user(
        db_session,
        email="network@example.com",
        nickname="networker",
        first_name="Network",
        last_name="Buddy",
    )

    await login(client, email=test_user.email)
    send_response = await client.post(
        "/api/v1/friends/requests",
        json={"receiver_id": str(other_user.id)},
    )
    request_id = send_response.json()["id"]

    outgoing_response = await client.get("/api/v1/friends/requests/outgoing")
    assert outgoing_response.status_code == 200
    assert len(outgoing_response.json()) == 1

    status_response = await client.get(f"/api/v1/friends/status?user_ids={other_user.id}")
    assert status_response.status_code == 200
    assert status_response.json()[0]["status"] == "outgoing_request"

    await logout(client)
    await login(client, email=other_user.email)

    incoming_response = await client.get("/api/v1/friends/requests/incoming")
    assert incoming_response.status_code == 200
    assert len(incoming_response.json()) == 1

    accept_response = await client.post(f"/api/v1/friends/requests/{request_id}/accept")
    assert accept_response.status_code == 200

    friends_response = await client.get("/api/v1/friends")
    assert friends_response.status_code == 200
    assert len(friends_response.json()) == 1
    assert friends_response.json()[0]["friend"]["id"] == str(test_user.id)


@pytest.mark.asyncio
async def test_user_can_remove_friendship(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    other_user = await create_user(
        db_session,
        email="remove@example.com",
        nickname="removefriend",
        first_name="Remove",
        last_name="Friend",
    )

    request = FriendRequestModel(
        sender_id=test_user.id,
        receiver_id=other_user.id,
        status="accepted",
    )
    db_session.add(request)
    db_session.add(FriendshipModel(user_id=test_user.id, friend_id=other_user.id))
    db_session.add(FriendshipModel(user_id=other_user.id, friend_id=test_user.id))
    await db_session.commit()

    await login(client, email=test_user.email)
    delete_response = await client.delete(f"/api/v1/friends/{other_user.id}")
    assert delete_response.status_code == 204

    friendships = await db_session.execute(select(FriendshipModel))
    assert friendships.scalars().all() == []
