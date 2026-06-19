from io import BytesIO

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.services.storage.mediaStorageService import (
    S3MediaStorageService,
    get_media_storage_provider,
    get_media_storage_service,
)


class FakeStorageService:
    def __init__(self):
        self.uploaded = None

    async def upload_file(
        self,
        file_bytes: bytes,
        file_name: str,
        content_type: str = "application/octet-stream",
        folder: str = "resumes",
    ) -> dict:
        self.uploaded = {
            "file_bytes": file_bytes,
            "file_name": file_name,
            "content_type": content_type,
            "folder": folder,
        }
        return {
            "file_key": f"{folder}/{file_name}",
            "file_url": f"https://storage.example/{folder}/{file_name}",
            "bucket": "media-bucket",
        }

    async def download_file(self, file_key: str) -> bytes:
        return b""

    async def delete_file(self, file_key: str) -> bool:
        return True


def test_media_storage_provider_defaults_to_imagekit(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MEDIA_STORAGE_PROVIDER", raising=False)

    assert get_media_storage_provider() == "imagekit"


def test_media_storage_service_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported media storage provider"):
        get_media_storage_service(provider="unknown")


def test_media_storage_service_supports_s3_provider(monkeypatch: pytest.MonkeyPatch):
    fake_storage = FakeStorageService()
    monkeypatch.setenv("MEDIA_STORAGE_PROVIDER", "s3")
    monkeypatch.setattr("app.services.storage.mediaStorageService.get_storage_service", lambda bucket_name=None: fake_storage)

    service = get_media_storage_service()

    assert isinstance(service, S3MediaStorageService)


@pytest.mark.asyncio
async def test_s3_media_storage_uploads_via_configured_storage():
    fake_storage = FakeStorageService()
    service = S3MediaStorageService(storage_service=fake_storage)
    upload = UploadFile(
        filename="photo.png",
        file=BytesIO(b"image bytes"),
        headers=Headers({"content-type": "image/png"}),
    )

    result = await service.upload_media(upload, "../photo.png", folder="posts/")

    assert result.url == "https://storage.example/posts/photo.png"
    assert result.file_type == "image"
    assert result.name == "photo.png"
    assert fake_storage.uploaded == {
        "file_bytes": b"image bytes",
        "file_name": "photo.png",
        "content_type": "image/png",
        "folder": "posts",
    }
