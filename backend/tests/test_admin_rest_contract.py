"""TASK-053: the React admin console talks only to the normalized REST API."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.app import app
from app.routes import adminRoute


class StubAdminService:
    def __init__(self):
        self.session = None
        self.user = SimpleNamespace(
            id=uuid4(),
            email="student@example.invalid",
            first_name="Ada",
            last_name="Lovelace",
            nickname="ada",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        self.user_updates: list[dict] = []
        self.resource_updates: list[dict] = []

    async def list_users(self, *, skip: int, limit: int):
        assert (skip, limit) == (20, 20)
        return [self.user]

    async def count_users(self):
        return 41

    async def update_user_flags(self, user_id, **changes):
        assert user_id == self.user.id
        self.user_updates.append(changes)
        for name, value in changes.items():
            setattr(self.user, name, value)
        return self.user

    async def update_resource_state(self, resource_id, **changes):
        self.resource_updates.append(changes)
        return SimpleNamespace(
            id=resource_id,
            title="Course",
            is_published=changes.get("is_published", True),
            is_locked=changes.get("is_locked", False),
        )


def _override_admin(service=None):
    admin = SimpleNamespace(id=uuid4(), is_superuser=True)
    app.dependency_overrides[adminRoute.current_admin_user] = lambda: admin
    app.dependency_overrides[adminRoute.require_same_origin_for_write] = lambda: None
    if service is not None:
        app.dependency_overrides[adminRoute._get_service] = lambda: service
    return admin


def _clear_overrides():
    for dependency in (
        adminRoute.current_admin_user,
        adminRoute.require_same_origin_for_write,
        adminRoute._get_service,
    ):
        app.dependency_overrides.pop(dependency, None)


async def test_users_use_numbered_page_shape_and_keep_the_legacy_adapter(client):
    service = StubAdminService()
    _override_admin(service)
    try:
        response = await client.get("/api/v1/admin/users?page=2&page_size=20")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 2
    assert body["page_size"] == 20
    assert body["total"] == 41
    assert body["items"] == body["users"]


async def test_user_patch_is_explicit_and_replay_safe(client):
    service = StubAdminService()
    _override_admin(service)
    try:
        first = await client.patch(
            f"/api/v1/admin/users/{service.user.id}", json={"is_active": False}
        )
        second = await client.patch(
            f"/api/v1/admin/users/{service.user.id}", json={"is_active": False}
        )
    finally:
        _clear_overrides()

    assert first.status_code == second.status_code == 200
    assert first.json()["is_active"] is False
    assert second.json()["is_active"] is False
    assert service.user_updates == [{"is_active": False}, {"is_active": False}]


async def test_resource_patch_sets_the_requested_flags(client):
    service = StubAdminService()
    resource_id = uuid4()
    _override_admin(service)
    try:
        response = await client.patch(
            f"/api/v1/admin/resources/{resource_id}",
            json={"is_published": False, "is_locked": True},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert response.json()["is_published"] is False
    assert response.json()["is_locked"] is True
    assert service.resource_updates == [{"is_published": False, "is_locked": True}]


async def test_company_catalogue_no_longer_reads_a_nonexistent_email(client, test_company):
    _override_admin()
    try:
        response = await client.get("/api/v1/admin/companies?page=1&page_size=20")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == str(test_company.id)
    assert response.json()["items"][0]["email"] is None


async def test_non_admin_is_still_forbidden(client, auth_headers):
    response = await client.get("/api/v1/admin/stats", headers=auth_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_openapi_publishes_new_paths_and_deprecates_toggles():
    paths = app.openapi()["paths"]
    assert "/api/v1/admin/resource-files" in paths
    assert "/api/v1/admin/job-postings" in paths
    assert paths["/api/v1/admin/users/{user_id}"]["patch"]["operationId"] == "admin_update_user"
    assert paths["/api/v1/admin/users/{user_id}/toggle-active"]["patch"]["deprecated"] is True
    assert paths["/api/v1/admin/resources/{resource_id}/toggle-locked"]["patch"]["deprecated"] is True
