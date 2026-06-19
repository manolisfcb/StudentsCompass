import pytest


@pytest.mark.asyncio
async def test_career_lab_requires_login(client):
    response = await client.get("/career-lab", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_career_lab_renders_for_authenticated_student(client, auth_headers):
    response = await client.get("/career-lab", headers=auth_headers)

    assert response.status_code == 200
    assert "Career Intelligence Lab" in response.text
    assert "analyticsReadinessBadge" in response.text
    assert "overallReadinessScore" in response.text
    assert "contextSimilarityScore" in response.text
    assert "routeOptimizationForm" in response.text
    assert "routeHistoryList" in response.text
    assert "catalogQualityPanel" in response.text
    assert "marketSignalsList" in response.text
    assert "insightsList" in response.text
    assert "Loading target roles..." in response.text
    assert "career_lab.css" in response.text
    assert "career_lab.js" in response.text
