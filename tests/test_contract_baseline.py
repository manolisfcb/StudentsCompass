"""Characterization contracts captured before the refactor tasks start.

These pin *current* behavior at the boundaries the later tasks reshape — auth,
CV, AI quota, applications, progress and Career Lab. They are deliberately
about shape and access control, not about business rules: a refactor that keeps
the contract keeps these green, and a refactor that silently opens an endpoint,
drops a field or changes a status code fails here rather than in production.

If one of these has to change, that is a contract change and belongs in the
task that declares it — not a quiet edit.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


# --- Auth boundary ---------------------------------------------------------
# Every one of these is authenticated today. The matrix exists so a refactor
# cannot drop a dependency and turn one of them public unnoticed.
PROTECTED_JSON_ENDPOINTS = [
    ("GET", "/api/v1/users/me"),
    ("GET", "/api/v1/profile/cv"),
    ("GET", "/api/v1/profile/cv/course-audit-attempts"),
    ("GET", "/api/v1/applications"),
    ("GET", "/api/v1/applications/eligible-resumes"),
    ("GET", "/api/v1/dashboard/stats"),
    ("GET", "/api/v1/students_dashboard"),
    ("GET", "/api/v1/capstone/analytics/status"),
    ("GET", "/api/v1/capstone/analytics/roles"),
    ("GET", "/api/v1/capstone/gap-analysis"),
    ("GET", "/api/v1/resources"),
    ("GET", "/api/v1/posts"),
]


@pytest.mark.parametrize("method,path", PROTECTED_JSON_ENDPOINTS)
@pytest.mark.asyncio
async def test_json_endpoints_reject_anonymous_callers(client, method, path):
    response = await client.request(method, path, follow_redirects=False)

    assert response.status_code == 401, f"{method} {path} is no longer protected"


@pytest.mark.asyncio
async def test_html_pages_redirect_anonymous_callers_to_login(client):
    """Pages redirect; APIs 401. Mixing the two breaks the frontend."""
    response = await client.get("/career-lab", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_authenticated_identity_contract(client, auth_headers, test_user):
    response = await client.get("/api/v1/users/me", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(test_user.id)
    assert body["email"] == test_user.email
    # The password hash must never reach the client.
    assert "hashed_password" not in body
    assert "password" not in body


# --- CV ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cv_list_is_scoped_and_empty_for_a_new_user(client, auth_headers):
    response = await client.get("/api/v1/profile/cv", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == []


# --- AI quota ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_quota_contract_reports_base_daily_limit(client, auth_headers):
    from app.config import AI_BASE_DAILY_LIMIT

    response = await client.get(
        "/api/v1/profile/cv/course-audit-attempts", headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"attempts_today", "daily_limit", "attempts_remaining"}
    assert body["attempts_today"] == 0
    assert body["daily_limit"] == AI_BASE_DAILY_LIMIT
    assert body["attempts_remaining"] == AI_BASE_DAILY_LIMIT


# --- Applications -----------------------------------------------------------

@pytest.mark.asyncio
async def test_application_list_is_empty_for_a_new_user(client, auth_headers):
    response = await client.get("/api/v1/applications", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_application_create_validates_payload_before_touching_storage(
    client, auth_headers
):
    response = await client.post("/api/v1/applications", headers=auth_headers, json={})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unknown_application_id_is_not_a_server_error(client, auth_headers):
    import uuid

    response = await client.patch(
        f"/api/v1/applications/{uuid.uuid4()}",
        headers=auth_headers,
        json={"status": "in_review"},
    )

    assert response.status_code < 500


# --- Progress ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_dashboard_progress_contract(client, auth_headers):
    """Pins the projection shape the UI reads.

    TASK-016 unifies where these numbers come from; the *shape* must survive
    that change, so it is captured here first.
    """
    response = await client.get("/api/v1/dashboard/stats", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"stats", "progress", "recent_applications"}
    assert set(body["stats"]) == {
        "total_applications",
        "in_review",
        "interviews_scheduled",
        "offers_received",
    }
    assert set(body["progress"]) == {
        "resume",
        "linkedin",
        "interview_prep",
        "portfolio",
        "overall",
    }
    assert body["recent_applications"] == []


@pytest.mark.asyncio
async def test_dashboard_stats_currently_writes_a_user_stats_row_on_read(
    client, auth_headers, query_counter
):
    """Characterization, not an endorsement: this GET writes today.

    The first read lazily INSERTs the caller's ``user_stats`` row, so the
    endpoint is not a pure projection. That is finding F-15 and belongs to
    TASK-016 (unificar aprobación de CV y proyección de progreso), which states
    "GET no escribe caches". Pinned here so the change is visible and
    deliberate when TASK-016 lands: at that point this test flips to
    ``counted.writes == 0``.
    """
    with query_counter() as first_read:
        response = await client.get("/api/v1/dashboard/stats", headers=auth_headers)
    assert response.status_code == 200
    assert first_read.writes == 1
    assert first_read.matching("insert into user_stats")

    # The write is a one-off materialisation, not a write per request.
    with query_counter() as second_read:
        response = await client.get("/api/v1/dashboard/stats", headers=auth_headers)
    assert response.status_code == 200
    assert second_read.writes == 0, second_read.statements


# --- Career Lab -------------------------------------------------------------

@pytest.mark.asyncio
async def test_career_lab_analytics_status_contract(client, auth_headers):
    response = await client.get(
        "/api/v1/capstone/analytics/status", headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    # Only the keys later tasks must preserve, not the whole payload: pinning
    # every field would make unrelated additions fail.
    for key in (
        "schema_ready",
        "catalog_ready",
        "skills_count",
        "resume_skills_count",
        "semantic_matching_ready",
        "embedding_provider",
    ):
        assert key in body, f"analytics status lost {key}"
    assert body["schema_ready"] is True


@pytest.mark.asyncio
async def test_gap_analysis_requires_an_explicit_resume(client, auth_headers):
    """No implicit "latest resume" fallback: the caller names the resume."""
    response = await client.get("/api/v1/capstone/gap-analysis", headers=auth_headers)

    assert response.status_code == 422
    missing = {tuple(error["loc"]) for error in response.json()["detail"]}
    assert ("query", "resume_id") in missing
