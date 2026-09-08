import xml.etree.ElementTree as ET

import pytest
from httpx import AsyncClient


SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@pytest.mark.asyncio
async def test_sitemap_lists_public_marketing_pages(client: AsyncClient):
    response = await client.get("/sitemap.xml")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")

    root = ET.fromstring(response.content)
    locs = [node.text for node in root.findall("sm:url/sm:loc", SITEMAP_NS)]

    assert "https://studentscompass.ca/" in locs
    assert "https://studentscompass.ca/about" in locs
    assert "https://studentscompass.ca/login" in locs
    assert "https://studentscompass.ca/register" in locs
    assert "https://studentscompass.ca/dashboard" not in locs
    assert "https://studentscompass.ca/api/v1/auth/register" not in locs
    assert "https://studentscompass.ca/home" not in locs


@pytest.mark.asyncio
async def test_robots_uses_configured_public_base_url(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://www.studentscompass.ca")

    response = await client.get("/robots.txt")

    assert response.status_code == 200
    assert "Sitemap: https://www.studentscompass.ca/sitemap.xml" in response.text
