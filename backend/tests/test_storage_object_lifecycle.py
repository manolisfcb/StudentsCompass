"""Object identity and a recoverable delete.

Two defects are pinned here. Keys used to be derived from the upload's filename
and a second-resolution timestamp, so two users uploading ``cv.pdf`` in the same
second shared one key and ``put_object`` silently destroyed one of the files.
And deleting a resume removed the object *before* the database committed, with
the provider's answer ignored — so a rollback left a row pointing at nothing,
and a provider error left an object nobody could ever find again.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.resumeModel import ResumeModel
from app.models.storageDeletionIntentModel import StorageDeletionIntentModel
from app.services.resumes.resumeService import ResumeService
from app.services.storage.objectKeys import build_object_key, extension_for
from app.services.storage.storageCleanupService import StorageCleanupService


class RecordingStorage:
    """An object store that remembers what it holds, and can be made to fail."""

    def __init__(self, *, fail_delete: bool = False, fail_upload: bool = False):
        self.objects: dict[str, bytes] = {}
        self.uploads: list[dict] = []
        self.delete_calls: list[str] = []
        self.fail_delete = fail_delete
        self.fail_upload = fail_upload

    async def upload_file(
        self,
        file_bytes: bytes,
        file_name: str,
        content_type: str = "application/octet-stream",
        folder: str = "resumes",
        owner_id=None,
    ) -> dict:
        if self.fail_upload:
            raise RuntimeError("provider refused the upload")
        key = build_object_key(folder=folder, file_name=file_name, owner_id=owner_id)
        # put_object overwrites: this is exactly how a shared key destroyed data.
        self.objects[key] = file_bytes
        self.uploads.append({"key": key, "file_name": file_name, "owner_id": owner_id})
        return {
            "file_key": key,
            "file_url": f"https://storage.example/{key}",
            "bucket": "test-bucket",
        }

    async def download_file(self, file_key: str) -> bytes:
        return self.objects[file_key]

    async def delete_file(self, file_key: str) -> bool:
        self.delete_calls.append(file_key)
        if self.fail_delete:
            raise RuntimeError("provider is unavailable")
        self.objects.pop(file_key, None)
        return True


# --------------------------------------------------------------------------
# Key identity
# --------------------------------------------------------------------------


def test_same_name_and_instant_still_produce_different_keys():
    keys = {
        build_object_key(folder="resumes", file_name="cv.pdf", owner_id=uuid.uuid4())
        for _ in range(200)
    }
    assert len(keys) == 200


def test_key_does_not_carry_the_uploaded_filename():
    key = build_object_key(folder="resumes", file_name="Estado de cuenta.pdf")
    assert "Estado" not in key
    assert key.endswith(".pdf")


def test_key_is_filed_under_its_owner_when_known():
    owner = uuid.uuid4()
    key = build_object_key(folder="resumes", file_name="cv.pdf", owner_id=owner)
    assert key.startswith(f"resumes/{owner}/")


@pytest.mark.parametrize(
    "folder",
    ["../../etc", "resumes/../../secrets", "/", "", None],
)
def test_a_hostile_folder_cannot_escape_its_prefix(folder):
    key = build_object_key(folder=folder, file_name="cv.pdf")
    assert ".." not in key
    assert not key.startswith("/")


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [
        ("cv.pdf", ".pdf"),
        ("cv.PDF", ".pdf"),
        ("archive.tar.gz", ".gz"),
        ("no-extension", ""),
        ("weird.exe;.pdf%00", ""),
        (None, ""),
    ],
)
def test_extension_is_whitelisted_by_shape(file_name, expected):
    assert extension_for(file_name) == expected


@pytest.mark.asyncio
async def test_two_uploads_of_the_same_filename_keep_both_files(setup_db, db_session, test_user):
    storage = RecordingStorage()
    service = ResumeService(db_session, storage_service=storage)

    first, _ = await service.create_resume_from_upload(
        user_id=test_user.id,
        storage_location_id="test-bucket",
        file_bytes=b"first document",
        file_name="cv.pdf",
        mime_type="application/pdf",
    )
    second, _ = await service.create_resume_from_upload(
        user_id=test_user.id,
        storage_location_id="test-bucket",
        file_bytes=b"second document",
        file_name="cv.pdf",
        mime_type="application/pdf",
    )

    assert first.storage_file_id != second.storage_file_id
    assert len(storage.objects) == 2
    assert await storage.download_file(first.storage_file_id) == b"first document"
    assert await storage.download_file(second.storage_file_id) == b"second document"


@pytest.mark.asyncio
async def test_deleting_one_upload_leaves_the_other_intact(setup_db, db_session, test_user):
    storage = RecordingStorage()
    service = ResumeService(db_session, storage_service=storage)

    kept, _ = await service.create_resume_from_upload(
        user_id=test_user.id,
        storage_location_id="test-bucket",
        file_bytes=b"keep me",
        file_name="cv.pdf",
        mime_type="application/pdf",
    )
    removed, _ = await service.create_resume_from_upload(
        user_id=test_user.id,
        storage_location_id="test-bucket",
        file_bytes=b"remove me",
        file_name="cv.pdf",
        mime_type="application/pdf",
    )

    assert await service.delete_resume(removed.id, test_user.id) is True

    assert await storage.download_file(kept.storage_file_id) == b"keep me"
    assert removed.storage_file_id not in storage.objects


# --------------------------------------------------------------------------
# Upload compensation
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_failed_database_insert_removes_the_uploaded_object(
    setup_db, db_session, test_user, monkeypatch
):
    """Otherwise the bucket is paid for forever and nothing can find the file."""
    storage = RecordingStorage()
    service = ResumeService(db_session, storage_service=storage)

    async def refuse(*args, **kwargs):
        raise RuntimeError("database rejected the row")

    monkeypatch.setattr(service, "create_resume", refuse)

    with pytest.raises(RuntimeError, match="database rejected the row"):
        await service.create_resume_from_upload(
            user_id=test_user.id,
            storage_location_id="test-bucket",
            file_bytes=b"orphan",
            file_name="cv.pdf",
            mime_type="application/pdf",
        )

    assert storage.objects == {}
    assert len(storage.delete_calls) == 1


@pytest.mark.asyncio
async def test_an_orphan_the_provider_will_not_delete_is_queued(
    setup_db, db_session, test_user, monkeypatch
):
    storage = RecordingStorage(fail_delete=True)
    service = ResumeService(db_session, storage_service=storage)

    async def refuse(*args, **kwargs):
        raise RuntimeError("database rejected the row")

    monkeypatch.setattr(service, "create_resume", refuse)

    with pytest.raises(RuntimeError):
        await service.create_resume_from_upload(
            user_id=test_user.id,
            storage_location_id="test-bucket",
            file_bytes=b"orphan",
            file_name="cv.pdf",
            mime_type="application/pdf",
        )

    intents = (await db_session.execute(select(StorageDeletionIntentModel))).scalars().all()
    assert len(intents) == 1
    assert intents[0].completed_at is None
    assert intents[0].object_key == storage.uploads[0]["key"]


# --------------------------------------------------------------------------
# Deletion: database first, durable intent, idempotent retry
# --------------------------------------------------------------------------


async def _create_resume(service, user, *, contents=b"document") -> ResumeModel:
    resume, _ = await service.create_resume_from_upload(
        user_id=user.id,
        storage_location_id="test-bucket",
        file_bytes=contents,
        file_name="cv.pdf",
        mime_type="application/pdf",
    )
    return resume


@pytest.mark.asyncio
async def test_delete_removes_row_and_object_and_closes_the_intent(
    setup_db, db_session, test_user
):
    storage = RecordingStorage()
    service = ResumeService(db_session, storage_service=storage)
    resume = await _create_resume(service, test_user)
    key = resume.storage_file_id

    assert await service.delete_resume(resume.id, test_user.id) is True

    assert await db_session.get(ResumeModel, resume.id) is None
    assert key not in storage.objects

    intent = (
        await db_session.execute(
            select(StorageDeletionIntentModel).where(
                StorageDeletionIntentModel.object_key == key
            )
        )
    ).scalar_one()
    assert intent.completed_at is not None


@pytest.mark.asyncio
async def test_a_provider_failure_does_not_block_the_delete_but_is_recorded(
    setup_db, db_session, test_user
):
    """The row must still go, and the object must stay on the work queue."""
    storage = RecordingStorage()
    service = ResumeService(db_session, storage_service=storage)
    resume = await _create_resume(service, test_user)
    key = resume.storage_file_id

    storage.fail_delete = True
    assert await service.delete_resume(resume.id, test_user.id) is True

    assert await db_session.get(ResumeModel, resume.id) is None
    assert key in storage.objects, "object is still there — that is the point of the intent"

    intent = (
        await db_session.execute(
            select(StorageDeletionIntentModel).where(
                StorageDeletionIntentModel.object_key == key
            )
        )
    ).scalar_one()
    assert intent.completed_at is None
    assert intent.attempts == 1
    assert intent.last_error


@pytest.mark.asyncio
async def test_a_pending_deletion_converges_when_the_provider_recovers(
    setup_db, db_session, test_user
):
    storage = RecordingStorage()
    service = ResumeService(db_session, storage_service=storage)
    resume = await _create_resume(service, test_user)
    key = resume.storage_file_id

    storage.fail_delete = True
    await service.delete_resume(resume.id, test_user.id)

    cleanup = StorageCleanupService(db_session, storage_service=storage)

    # Still broken: retrying must not lose the intent.
    assert await cleanup.process_pending() == {"processed": 1, "completed": 0}

    storage.fail_delete = False
    assert await cleanup.process_pending() == {"processed": 1, "completed": 1}
    assert key not in storage.objects

    # Converged: nothing left to do, and running again is harmless.
    assert await cleanup.process_pending() == {"processed": 0, "completed": 0}


@pytest.mark.asyncio
async def test_retrying_an_already_deleted_object_succeeds(setup_db, db_session, test_user):
    """delete_object on an absent key is a no-op; that is what makes it retryable."""
    storage = RecordingStorage()
    service = ResumeService(db_session, storage_service=storage)
    resume = await _create_resume(service, test_user)
    key = resume.storage_file_id

    await service.delete_resume(resume.id, test_user.id)
    storage.objects.pop(key, None)

    cleanup = StorageCleanupService(db_session, storage_service=storage)
    assert await cleanup.process_pending() == {"processed": 0, "completed": 0}


@pytest.mark.asyncio
async def test_an_object_two_rows_share_is_not_deleted(setup_db, db_session, test_user):
    """Legacy keys were name-derived and could be shared. Inventory first."""
    storage = RecordingStorage()
    service = ResumeService(db_session, storage_service=storage)

    shared_key = "resumes/20260101_120000_cv.pdf"
    storage.objects[shared_key] = b"shared legacy document"
    rows = []
    for _ in range(2):
        row = ResumeModel(
            user_id=test_user.id,
            view_url=f"https://storage.example/{shared_key}",
            storage_file_id=shared_key,
            original_filename="cv.pdf",
            folder_id="test-bucket",
        )
        db_session.add(row)
        rows.append(row)
    await db_session.commit()

    assert await service.delete_resume(rows[0].id, test_user.id) is True

    assert storage.delete_calls == []
    assert storage.objects[shared_key] == b"shared legacy document"
    intents = (await db_session.execute(select(StorageDeletionIntentModel))).scalars().all()
    assert intents == []

    # The last reference goes, so now the object may go too.
    assert await service.delete_resume(rows[1].id, test_user.id) is True
    assert shared_key not in storage.objects


@pytest.mark.asyncio
async def test_delete_still_refuses_someone_elses_resume(setup_db, db_session, test_user):
    """Unchanged contract: ownership is checked before anything is touched."""
    storage = RecordingStorage()
    service = ResumeService(db_session, storage_service=storage)
    resume = await _create_resume(service, test_user)

    assert await service.delete_resume(resume.id, uuid.uuid4()) is False
    assert await db_session.get(ResumeModel, resume.id) is not None
    assert resume.storage_file_id in storage.objects


@pytest.mark.asyncio
async def test_legacy_keys_are_still_readable(setup_db, db_session, test_user):
    """Nothing rewrites stored keys, so old objects stay reachable."""
    storage = RecordingStorage()
    legacy_key = "resumes/20260101_120000_cv.pdf"
    storage.objects[legacy_key] = b"legacy document"

    service = ResumeService(db_session, storage_service=storage)
    assert await service.download_resume_file(legacy_key) == b"legacy document"
