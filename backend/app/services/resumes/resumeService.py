from app.core.pagination import MAX_COLLECTION_ROWS
from app.models.resumeModel import ResumeModel
from sqlalchemy import select
from app.schemas.resumeSchema import CreateResumeSchema
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import logging
from app.services.analytics.embeddingService import ResumeEmbeddingService, generate_embedding
from app.services.storage.storageCleanupService import (
    StorageCleanupService,
    record_deletion_intent,
)
from app.services.storage.storageService import StorageService, get_storage_service

LOGGER = logging.getLogger(__name__)

RESUME_UPLOAD_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    }
)

RESUME_AUDIT_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)


def is_allowed_resume_content_type(content_type: str | None, allowed_types: frozenset[str]) -> bool:
    return bool(content_type and content_type in allowed_types)


class ResumeService:
    def __init__(self, session: AsyncSession, storage_service: StorageService | None = None):
        self.session = session
        self.storage_service = storage_service or get_storage_service()
        
    async def create_resume(self, resume_create: CreateResumeSchema) -> ResumeModel:
        resume = ResumeModel(
            user_id = resume_create.user_id,
            view_url=resume_create.view_url,
            original_filename=resume_create.original_filename,
            storage_file_id=resume_create.storage_file_id,
            folder_id=resume_create.folder_id,
            ai_summary=resume_create.ai_summary,
            contact_phone=resume_create.contact_phone,
        )
        self.session.add(resume)
        await self.session.commit()
        await self.session.refresh(resume)
        return resume

    async def create_resume_from_upload(
        self,
        *,
        user_id: UUID,
        storage_location_id: str,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
    ) -> tuple[ResumeModel, dict]:
        file_info = await self.upload_resume_file(
            file_bytes, file_name, mime_type, owner_id=user_id
        )
        try:
            resume = await self.create_resume(
                CreateResumeSchema(
                    view_url=file_info["view_url"],
                    original_filename=file_name,
                    storage_file_id=file_info["file_key"],
                    folder_id=storage_location_id,
                    user_id=user_id,
                )
            )
        except Exception:
            # The object is already in the bucket but nothing references it, so
            # it would be paid for forever with no way left to find it. Undo the
            # upload; if the provider will not cooperate, leave a durable intent
            # so the sweeper finishes the job.
            await self._compensate_orphan_upload(
                storage_location_id=storage_location_id,
                object_key=file_info["file_key"],
            )
            raise
        return resume, file_info

    async def _compensate_orphan_upload(self, *, storage_location_id: str, object_key: str) -> None:
        await self.session.rollback()
        try:
            await self.storage_service.delete_file(object_key)
            return
        except Exception as error:
            LOGGER.warning(
                "Could not remove orphaned upload %s, queueing it: %s", object_key, error
            )

        try:
            await record_deletion_intent(
                self.session,
                storage_location_id=storage_location_id,
                object_key=object_key,
            )
            await self.session.commit()
        except Exception:
            # Nothing left to try; the object is logged so it can be reclaimed
            # by hand. Never mask the original upload failure with this one.
            await self.session.rollback()
            LOGGER.exception("Orphaned upload could not be queued for deletion: %s", object_key)
    
    async def create_resume_embedding(self, resume_id: UUID, model_name: str, dims: int, embedding: list[float]) -> None:
        embedding_service = ResumeEmbeddingService(self.session)
        await embedding_service.upsert_resume_embedding(
            resume_id=resume_id,
            model_name=model_name,
            dims=dims,
            embedding=embedding,
        )

    async def create_resume_embedding_from_text(self, resume_id: UUID, text: str | None, model_name: str) -> bool:
        embedding = await generate_embedding(text or "")
        if embedding is None:
            return False
        await self.create_resume_embedding(
            resume_id=resume_id,
            model_name=model_name,
            dims=len(embedding),
            embedding=embedding,
        )
        return True

    async def list_user_resumes(self, user_id: UUID) -> list[ResumeModel]:
        result = await self.session.execute(
            select(ResumeModel)
            .where(ResumeModel.user_id == user_id)
            .order_by(ResumeModel.created_at.desc())
            .limit(MAX_COLLECTION_ROWS)
        )
        return list(result.scalars().all())

    async def get_latest_user_resume(self, user_id: UUID) -> ResumeModel | None:
        result = await self.session.execute(
            select(ResumeModel)
            .where(ResumeModel.user_id == user_id)
            .order_by(ResumeModel.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_user_resume(self, *, resume_id: UUID, user_id: UUID) -> ResumeModel | None:
        result = await self.session.execute(
            select(ResumeModel).where(
                ResumeModel.id == resume_id,
                ResumeModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_resume_analysis(
        self,
        *,
        resume_id: UUID,
        ai_summary: str | None = None,
        contact_phone: str | None = None,
    ) -> ResumeModel | None:
        resume = await self.session.get(ResumeModel, resume_id)
        if resume is None:
            return None

        resume.ai_summary = ai_summary
        resume.contact_phone = contact_phone
        await self.session.commit()
        await self.session.refresh(resume)
        return resume
    
    async def _upload_resume_file_to_storage(
        self,
        file_bytes: bytes,
        file_name: str,
        mime_type: str = "application/pdf",
        owner_id: UUID | None = None,
    ) -> dict:
        """Upload resume file to the configured storage provider.

        The key is chosen by the storage layer and is unique per object. It used
        to be ``<timestamp to the second>_<filename>``, which two users could
        produce at once, and the second upload then overwrote the first.
        """
        upload_result = await self.storage_service.upload_file(
            file_bytes, file_name, mime_type, owner_id=owner_id
        )

        return {
            "file_key": upload_result["file_key"],
            "view_url": upload_result["file_url"],
            "original_filename": file_name
        }

    async def upload_resume_file(
        self,
        file_bytes: bytes,
        file_name: str,
        mime_type: str = "application/pdf",
        owner_id: UUID | None = None,
    ) -> dict:
        """Upload resume file using the configured storage provider."""
        return await self._upload_resume_file_to_storage(
            file_bytes, file_name, mime_type, owner_id=owner_id
        )

    async def upload_pdf_to_s3(self, file_bytes: bytes, file_name: str, mime_type: str = "application/pdf") -> dict:
        """Backward-compatible alias for existing callers."""
        return await self.upload_resume_file(file_bytes, file_name, mime_type)

    async def _download_resume_file_from_storage(self, file_key: str) -> bytes:
        """Download resume file from the configured storage provider."""
        return await self.storage_service.download_file(file_key)

    async def download_resume_file(self, file_key: str) -> bytes:
        """Download resume file using the configured storage provider."""
        return await self._download_resume_file_from_storage(file_key)

    async def download_file_from_s3(self, file_key: str) -> bytes:
        """Backward-compatible alias for existing callers."""
        return await self.download_resume_file(file_key)

    async def is_object_still_referenced(self, *, storage_file_id: str, excluding_resume_id: UUID) -> bool:
        """Does any other resume row point at this same object?

        Old keys were derived from the filename and could be shared by more than
        one row. Deleting the object for one of them would break the others, so
        the object is only removed once nothing references it.
        """
        if not storage_file_id:
            return False
        other = await self.session.execute(
            select(ResumeModel.id)
            .where(
                ResumeModel.storage_file_id == storage_file_id,
                ResumeModel.id != excluding_resume_id,
            )
            .limit(1)
        )
        return other.scalar_one_or_none() is not None

    async def delete_resume(self, resume_id: UUID, user_id: UUID) -> bool:
        """Delete the row, then the object — never the other way round.

        Removing the file first meant a rollback left a row whose file was
        already gone, and a provider error left the object orphaned with nothing
        recording that it should not exist. Here the database decides and the
        decision is durable before the provider is touched at all.
        """
        resume = await self.session.get(ResumeModel, resume_id)
        if not resume or resume.user_id != user_id:
            return False

        storage_location_id = resume.folder_id
        object_key = resume.storage_file_id
        shared = await self.is_object_still_referenced(
            storage_file_id=object_key, excluding_resume_id=resume_id
        )

        await self.session.delete(resume)
        if not shared:
            # Same transaction as the delete: commit and the object is on record
            # as unwanted, roll back and nothing happened at all.
            await record_deletion_intent(
                self.session,
                storage_location_id=storage_location_id,
                object_key=object_key,
            )
        else:
            LOGGER.info(
                "Keeping stored object %s: still referenced by another resume", object_key
            )
        await self.session.commit()

        if not shared:
            # Best effort, and it is allowed to fail: the intent is committed,
            # so a later sweep converges. Deleting an absent key succeeds, which
            # is what makes the retry idempotent.
            cleanup = StorageCleanupService(self.session, storage_service=self.storage_service)
            await cleanup.execute_intent(
                storage_location_id=storage_location_id, object_key=object_key
            )

        return True
