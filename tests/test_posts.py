import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.postModel import PostModel
from app.services.mediaStorageService import MediaUploadResult


class FakeMediaStorageService:
    def upload_media(self, file, file_name: str, folder: str = "images/") -> MediaUploadResult:
        assert file_name == "photo.png"
        assert folder == "posts/"
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
        files={"file": ("photo.png", io.BytesIO(b"fake image"), "image/png")},
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
