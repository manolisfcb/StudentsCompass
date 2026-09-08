import pytest

from httpx import AsyncClient
from fastapi_users.password import PasswordHelper

from app.models.userModel import User


@pytest.mark.asyncio
async def test_user_can_update_optional_profile_fields(
    client: AsyncClient,
    auth_headers: dict,
):
    response = await client.patch(
        "/api/v1/profile",
        headers=auth_headers,
        json={
            "first_name": "Manuel",
            "last_name": "Rivera",
            "nickname": "manu",
            "email": "manuel@example.com",
            "phone": "+1 416 555 0101",
            "address": "Toronto, ON, Canada",
            "sex": "Male",
            "age": 24,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "Manuel"
    assert data["last_name"] == "Rivera"
    assert data["nickname"] == "manu"
    assert data["email"] == "manuel@example.com"
    assert data["phone"] == "+1 416 555 0101"
    assert data["address"] == "Toronto, ON, Canada"
    assert data["sex"] == "Male"
    assert data["age"] == 24


@pytest.mark.asyncio
async def test_user_cannot_update_profile_to_existing_email(
    client: AsyncClient,
    auth_headers: dict,
    db_session,
):
    password_helper = PasswordHelper()
    db_session.add(
        User(
            email="taken@example.com",
            hashed_password=password_helper.hash("password123"),
            is_active=True,
            is_superuser=False,
            is_verified=True,
            nickname="taken",
        )
    )
    await db_session.commit()

    response = await client.patch(
        "/api/v1/profile",
        headers=auth_headers,
        json={"email": "taken@example.com"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already in use"


@pytest.mark.asyncio
async def test_empty_profile_email_update_keeps_existing_email(
    client: AsyncClient,
    auth_headers: dict,
):
    response = await client.patch(
        "/api/v1/profile",
        headers=auth_headers,
        json={"email": None, "first_name": "Still"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["first_name"] == "Still"
