from app.models.resumeModel import ResumeModel
from sqlalchemy import select
from app.schemas.resumeSchema import CreateResumeSchema
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import logging
from datetime import datetime
from app.services.storageService import StorageService, get_storage_service

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
        file_info = await self.upload_resume_file(file_bytes, file_name, mime_type)
        resume = await self.create_resume(
            CreateResumeSchema(
                view_url=file_info["view_url"],
                original_filename=file_name,
                storage_file_id=file_info["file_key"],
                folder_id=storage_location_id,
                user_id=user_id,
            )
        )
        return resume, file_info
    
    async def create_resume_embedding(self, resume_id: UUID, model_name: str, dims: int, embedding: list[float]) -> None:
        # Desactivado: No guardar embeddings
        LOGGER.info("create_resume_embedding called, but embedding generation is disabled. No embedding will be saved.")
        return None

    async def list_user_resumes(self, user_id: UUID) -> list[ResumeModel]:
        result = await self.session.execute(
            select(ResumeModel)
            .where(ResumeModel.user_id == user_id)
            .order_by(ResumeModel.created_at.desc())
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
    ) -> dict:
        """Upload resume file to the configured storage provider."""
        # Generate unique filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{file_name}"
        
        upload_result = await self.storage_service.upload_file(file_bytes, unique_filename, mime_type)
        
        return {
            "file_key": upload_result["file_key"],
            "view_url": upload_result["file_url"],
            "original_filename": file_name
        }

    async def upload_resume_file(self, file_bytes: bytes, file_name: str, mime_type: str = "application/pdf") -> dict:
        """Upload resume file using the configured storage provider."""
        return await self._upload_resume_file_to_storage(file_bytes, file_name, mime_type)

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

    async def delete_resume(self, resume_id: UUID, user_id: UUID) -> bool:
        resume = await self.session.get(ResumeModel, resume_id)
        if not resume or resume.user_id != user_id:
            return False

        # Try deleting from storage, but don't fail DB deletion if file missing
        try:
            await self.storage_service.delete_file(resume.storage_file_id)
        except Exception as e:
            LOGGER.warning("Storage delete failed for %s: %s", resume.storage_file_id, e)

        await self.session.delete(resume)
        await self.session.commit()
        return True
