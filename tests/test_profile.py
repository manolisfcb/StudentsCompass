import pytest

from httpx import AsyncClient


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
