import pytest

from app.services.adminService import AdminService
from app.services.resourceService import ResourceService
from app.services.storageService import get_resource_storage_location_id


class FakeResourceStorageService:
    def __init__(self):
        self.uploaded = None
        self.downloaded_key = None

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
            "bucket": "resource-bucket",
        }

    async def download_file(self, file_key: str) -> bytes:
        self.downloaded_key = file_key
        return b"resource content"

    async def delete_file(self, file_key: str) -> bool:
        return True


def test_resource_storage_location_prefers_resources_bucket(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BUCKET_NAME", "resume-bucket")
    monkeypatch.setenv("RESOURCES_BUCKET_NAME", "resource-bucket")

    assert get_resource_storage_location_id() == "resource-bucket"


@pytest.mark.asyncio
async def test_download_resource_file_uses_configured_storage():
    fake_storage = FakeResourceStorageService()
    service = ResourceService(session=None, storage_service=fake_storage)

    file_bytes, media_type, filename = await service.download_resource_file("resources/guide.pdf")

    assert file_bytes == b"resource content"
    assert media_type == "application/pdf"
    assert filename == "guide.pdf"
    assert fake_storage.downloaded_key == "resources/guide.pdf"


@pytest.mark.asyncio
async def test_admin_upload_resource_file_uses_configured_storage():
    fake_storage = FakeResourceStorageService()
    service = AdminService(session=None, storage_service=fake_storage)

    payload = await service.upload_resource_file(
        file_bytes=b"resource content",
        file_name="../guide.pdf",
        content_type="application/pdf",
    )

    assert payload["file_key"].startswith("resources/")
    assert payload["file_url"].startswith("https://storage.example/resources/")
    assert payload["original_filename"] == "guide.pdf"
    assert payload["content_type"] == "application/pdf"
    assert fake_storage.uploaded["file_bytes"] == b"resource content"
    assert fake_storage.uploaded["content_type"] == "application/pdf"
    assert fake_storage.uploaded["folder"] == "resources"
    assert fake_storage.uploaded["file_name"].endswith("_guide.pdf")
