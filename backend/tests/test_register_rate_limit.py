import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_registration_is_rate_limited_per_ip(client: AsyncClient):
    """Scripted account farming (each account unlocks free AI quota) is blocked
    once the per-IP registration burst limit is exceeded."""
    statuses = []
    for i in range(6):  # REGISTER_RATE_LIMIT_MAX defaults to 5
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": f"farm{i}@example.com", "password": "StrongPass123!"},
        )
        statuses.append(response.status_code)

    assert 429 in statuses
    assert statuses[-1] == 429
