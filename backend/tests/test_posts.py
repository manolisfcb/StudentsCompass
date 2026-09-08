import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.postModel import PostModel
from app.services.storage.mediaStorageService import MediaUploadResult


# A real PNG header. The endpoint now rejects a payload whose leading bytes
# contradict its declared Content-Type, so the fixture has to be an actual PNG.
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake image body"


class FakeMediaStorageService:
    def __init__(self):
        self.received_bytes = None

    async def upload_media(
        self,
        file,
        file_name: str,
        folder: str = "images/",
        *,
        file_bytes: bytes | None = None,
        content_type: str | None = None,
    ) -> MediaUploadResult:
        assert file_name == "photo.png"
        assert folder == "posts/"
        self.received_bytes = file_bytes
        return MediaUploadResult(
            url="https://media.example/posts/photo.png",
            file_type="image",
            name="photo.png",
        )


@pytest.mark.asyncio
async def test_upload_post_uses_media_storage_service(
    client: AsyncClient,
    auth_headers: dict,
    test_user,
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.routes.postRoute.get_media_storage_service",
        lambda: FakeMediaStorageService(),
    )

    response = await client.post(
        "/api/v1/upload_post",
        headers=auth_headers,
        data={"caption": "My update"},
        files={"file": ("photo.png", io.BytesIO(PNG_BYTES), "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["caption"] == "My update"
    assert payload["url"] == "https://media.example/posts/photo.png"
    assert payload["file_type"] == "image"
    assert payload["file_name"] == "photo.png"

    created_post = await db_session.scalar(select(PostModel).where(PostModel.id == uuid.UUID(payload["id"])))
    assert created_post is not None
    assert created_post.user_id == test_user.id


# --- Ownership of deletion (TASK-003 / F-02) --------------------------------
# The route authenticated the caller but never passed the actor down, so the
# service deleted by post_id alone: any logged-in user could delete anyone's
# post. These tests pin the corrected boundary.

@pytest.fixture
async def other_user(db_session):
    """A second account, so "someone else's post" is a real case."""
    from fastapi_users.password import PasswordHelper

    from app.models.userModel import User

    user = User(
        id=uuid.uuid4(),
        email="other@example.com",
        hashed_password=PasswordHelper().hash("password123"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        nickname="otheruser",
        first_name="Other",
        last_name="User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def other_auth_headers(client, other_user):
    response = await client.post(
        "/auth/jwt/login",
        data={"username": other_user.email, "password": "password123"},
    )
    assert response.status_code in (200, 204)
    return {}


async def _create_post(db_session, user_id) -> uuid.UUID:
    post = PostModel(
        id=uuid.uuid4(),
        caption="Owned post",
        url="https://media.example/posts/owned.png",
        file_type="image",
        file_name="owned.png",
        user_id=user_id,
    )
    db_session.add(post)
    await db_session.commit()
    return post.id


async def _post_exists(db_session, post_id: uuid.UUID) -> bool:
    """Re-read from the database.

    The request handler deletes through its own session, so the fixture
    session's identity map is stale; expunging forces a real query.
    """
    db_session.expunge_all()
    return await db_session.get(PostModel, post_id) is not None


@pytest.mark.asyncio
async def test_owner_can_delete_their_own_post(client, auth_headers, test_user, db_session):
    post_id = await _create_post(db_session, test_user.id)

    response = await client.delete(f"/api/v1/delete_post/{post_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"detail": "Post deleted successfully"}
    assert not await _post_exists(db_session, post_id)


@pytest.mark.asyncio
async def test_other_user_cannot_delete_a_post_they_do_not_own(
    client, auth_headers, other_auth_headers, test_user, db_session
):
    """B must not be able to delete A's post, and must not learn it exists."""
    post_id = await _create_post(db_session, test_user.id)

    # other_auth_headers logged the client in as the second user.
    response = await client.delete(
        f"/api/v1/delete_post/{post_id}", headers=other_auth_headers
    )

    assert response.status_code == 404
    assert await _post_exists(db_session, post_id)


@pytest.mark.asyncio
async def test_anonymous_caller_is_rejected(client, test_user, db_session):
    post_id = await _create_post(db_session, test_user.id)

    response = await client.delete(f"/api/v1/delete_post/{post_id}")

    assert response.status_code == 401
    assert await _post_exists(db_session, post_id)


@pytest.mark.asyncio
async def test_unknown_post_id_is_404_not_500(client, auth_headers):
    """Previously the service raised a bare Exception, surfacing as a 500."""
    response = await client.delete(
        f"/api/v1/delete_post/{uuid.uuid4()}", headers=auth_headers
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_legacy_post_without_an_author_is_not_deletable(
    client, auth_headers, db_session
):
    """user_id is nullable: pre-authorship posts belong to nobody.

    Deleting them is a separate, deliberate operation; the endpoint must not
    hand that power to whichever user asks first.
    """
    post_id = await _create_post(db_session, None)

    response = await client.delete(f"/api/v1/delete_post/{post_id}", headers=auth_headers)

    assert response.status_code == 404
    assert await _post_exists(db_session, post_id)
