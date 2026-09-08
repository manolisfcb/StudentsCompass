import uuid

import pytest

from app.models.resourceModel import ResourceLessonModel, ResourceModel, ResourceModuleModel
from app.services.admin.adminService import AdminService
from app.services.resources.resourceLessonContentCodec import ResourceLessonContentCodec
from app.services.resources.resourceService import ResourceFileNotFound, ResourceService
from app.services.storage.storageService import get_resource_storage_location_id


class FakeResourceStorageService:
    def __init__(self):
        self.uploaded = None
        self.downloaded_key = None
        self.download_calls = 0

    async def upload_file(
        self,
        file_bytes: bytes,
        file_name: str,
        content_type: str = "application/octet-stream",
        folder: str = "resumes",
        owner_id=None,
    ) -> dict:
        self.uploaded = {
            "file_bytes": file_bytes,
            "file_name": file_name,
            "content_type": content_type,
            "folder": folder,
            "owner_id": owner_id,
        }
        return {
            "file_key": f"{folder}/{file_name}",
            "file_url": f"https://storage.example/{folder}/{file_name}",
            "bucket": "resource-bucket",
        }

    async def download_file(self, file_key: str) -> bytes:
        self.download_calls += 1
        self.downloaded_key = file_key
        return b"resource content"

    async def delete_file(self, file_key: str) -> bool:
        return True


LESSON_FILE_KEY = "resources/20260101_1200_ab12cd34_guide.pdf"
LESSON_FILE_URL = f"https://storage.example/{LESSON_FILE_KEY}"


async def _seed_resource(
    session,
    *,
    lesson_value: str = LESSON_FILE_URL,
    content_type: str = "pdf_url",
    is_published: bool = True,
    is_locked: bool = False,
    external_url: str | None = None,
) -> ResourceModel:
    codec = ResourceLessonContentCodec()
    resource = ResourceModel(
        id=uuid.uuid4(),
        title=f"Course {uuid.uuid4().hex[:6]}",
        description="A course with an attached file.",
        category="career",
        is_published=is_published,
        is_locked=is_locked,
        external_url=external_url,
    )
    module = ResourceModuleModel(id=uuid.uuid4(), resource_id=resource.id, title="Module 1", position=1)
    lesson = ResourceLessonModel(
        id=uuid.uuid4(),
        module_id=module.id,
        title="Lesson 1",
        position=1,
        content_type=content_type,
        content=codec.encode(
            content_type=content_type,
            content=None,
            resource_url=lesson_value,
        ).storage_content,
    )
    session.add_all([resource, module, lesson])
    await session.commit()
    return resource


def test_resource_storage_location_prefers_resources_bucket(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BUCKET_NAME", "resume-bucket")
    monkeypatch.setenv("RESOURCES_BUCKET_NAME", "resource-bucket")

    assert get_resource_storage_location_id() == "resource-bucket"


@pytest.mark.asyncio
async def test_download_resource_file_uses_configured_storage(db_session):
    await _seed_resource(db_session)
    fake_storage = FakeResourceStorageService()
    service = ResourceService(session=db_session, storage_service=fake_storage)

    file_bytes, media_type, filename = await service.download_resource_file(LESSON_FILE_KEY)

    assert file_bytes == b"resource content"
    assert media_type == "application/pdf"
    assert filename == "20260101_1200_ab12cd34_guide.pdf"
    assert fake_storage.downloaded_key == LESSON_FILE_KEY


@pytest.mark.asyncio
async def test_key_stored_as_a_bare_key_still_resolves(db_session):
    """Authorized links keep working whichever form the lesson stored."""
    await _seed_resource(db_session, lesson_value=LESSON_FILE_KEY, content_type="external_link")
    fake_storage = FakeResourceStorageService()
    service = ResourceService(session=db_session, storage_service=fake_storage)

    file_bytes, _, _ = await service.download_resource_file(LESSON_FILE_KEY)

    assert file_bytes == b"resource content"


@pytest.mark.asyncio
async def test_percent_encoded_reference_resolves_to_the_same_key(db_session):
    key = "resources/20260101_1200_ab12cd34_my guide.pdf"
    await _seed_resource(db_session, lesson_value="https://storage.example/resources/20260101_1200_ab12cd34_my%20guide.pdf")
    fake_storage = FakeResourceStorageService()
    service = ResourceService(session=db_session, storage_service=fake_storage)

    file_bytes, _, _ = await service.download_resource_file(key)

    assert file_bytes == b"resource content"


@pytest.mark.asyncio
async def test_resource_level_external_url_authorizes_its_own_file(db_session):
    await _seed_resource(db_session, lesson_value="https://example.com/watch", content_type="external_link", external_url=LESSON_FILE_URL)
    fake_storage = FakeResourceStorageService()
    service = ResourceService(session=db_session, storage_service=fake_storage)

    file_bytes, _, _ = await service.download_resource_file(LESSON_FILE_KEY)

    assert file_bytes == b"resource content"


@pytest.mark.asyncio
async def test_locked_resource_file_is_not_downloadable(db_session):
    """F-07: knowing the key used to be enough to bypass the catalogue."""
    await _seed_resource(db_session, is_locked=True)
    fake_storage = FakeResourceStorageService()
    service = ResourceService(session=db_session, storage_service=fake_storage)

    with pytest.raises(ResourceFileNotFound):
        await service.download_resource_file(LESSON_FILE_KEY)

    # And nothing was fetched from the provider on the way to refusing.
    assert fake_storage.download_calls == 0


@pytest.mark.asyncio
async def test_unpublished_resource_file_is_not_downloadable(db_session):
    await _seed_resource(db_session, is_published=False)
    fake_storage = FakeResourceStorageService()
    service = ResourceService(session=db_session, storage_service=fake_storage)

    with pytest.raises(ResourceFileNotFound):
        await service.download_resource_file(LESSON_FILE_KEY)

    assert fake_storage.download_calls == 0


@pytest.mark.asyncio
async def test_key_no_resource_references_is_not_downloadable(db_session):
    await _seed_resource(db_session)
    fake_storage = FakeResourceStorageService()
    service = ResourceService(session=db_session, storage_service=fake_storage)

    for key in (
        "resources/someone_elses_upload.pdf",
        "resources/",
        "resources/../resumes/private.pdf",
        "resumes/private.pdf",
        "",
    ):
        with pytest.raises(ResourceFileNotFound):
            await service.download_resource_file(key)

    assert fake_storage.download_calls == 0


@pytest.mark.asyncio
async def test_a_lesson_of_a_locked_resource_cannot_lend_its_key(db_session):
    """Two resources, one visible and one locked, each with its own file."""
    locked_key = "resources/20260101_1200_ffffffff_secret.pdf"
    await _seed_resource(db_session)
    await _seed_resource(db_session, lesson_value=f"https://storage.example/{locked_key}", is_locked=True)
    fake_storage = FakeResourceStorageService()
    service = ResourceService(session=db_session, storage_service=fake_storage)

    assert await service.resolve_authorized_file_key(LESSON_FILE_KEY) == LESSON_FILE_KEY
    assert await service.resolve_authorized_file_key(locked_key) is None


@pytest.mark.asyncio
async def test_route_serves_authorized_file_and_refuses_locked_one(
    client, db_session, auth_headers, monkeypatch
):
    import app.services.resources.resourceService as resource_service_module

    locked_key = "resources/20260101_1200_ffffffff_secret.pdf"
    await _seed_resource(db_session)
    await _seed_resource(db_session, lesson_value=f"https://storage.example/{locked_key}", is_locked=True)

    fake_storage = FakeResourceStorageService()
    monkeypatch.setattr(resource_service_module, "get_resource_storage_location_id", lambda: "resource-bucket")
    monkeypatch.setattr(resource_service_module, "get_storage_service", lambda **kwargs: fake_storage)

    allowed = await client.get("/api/v1/resources/file", params={"key": LESSON_FILE_KEY}, headers=auth_headers)
    assert allowed.status_code == 200
    assert allowed.content == b"resource content"

    refused = await client.get("/api/v1/resources/file", params={"key": locked_key}, headers=auth_headers)
    assert refused.status_code == 404
    assert fake_storage.download_calls == 1  # only the authorized one


@pytest.mark.asyncio
async def test_route_requires_authentication(client, db_session):
    await _seed_resource(db_session)

    response = await client.get("/api/v1/resources/file", params={"key": LESSON_FILE_KEY})

    assert response.status_code == 401


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


def test_codec_extracts_storage_key_from_both_reference_forms():
    codec = ResourceLessonContentCodec()

    assert codec.extract_storage_key(LESSON_FILE_URL, prefix="resources/") == LESSON_FILE_KEY
    assert codec.extract_storage_key(LESSON_FILE_KEY, prefix="resources/") == LESSON_FILE_KEY
    assert codec.extract_storage_key(f"{LESSON_FILE_URL}?token=abc", prefix="resources/") == LESSON_FILE_KEY
    assert codec.extract_storage_key("https://example.com/watch", prefix="resources/") is None
    assert codec.extract_storage_key("", prefix="resources/") is None
