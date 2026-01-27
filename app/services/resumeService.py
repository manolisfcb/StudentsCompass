from app.models.resumeModel import ResumeModel
from sqlalchemy import select
from app.schemas.resumeSchema import CreateResumeSchema
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.services.s3Service import S3Service
import logging
from app.models.resumeEmbeddingsModel import ResumeEmbedding 
from datetime import datetime

LOGGER = logging.getLogger(__name__)

class ResumeService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.s3_service = S3Service()
        
    async def create_resume(self, resume_create: CreateResumeSchema) -> ResumeModel:
        resume = ResumeModel(
            user_id = resume_create.user_id,
            view_url=resume_create.view_url,
            original_filename=resume_create.original_filename,
            storage_file_id=resume_create.storage_file_id,
            folder_id=resume_create.folder_id
        )
        self.session.add(resume)
        await self.session.commit()
        await self.session.refresh(resume)
        return resume
    
    async def create_resume_embedding(self, resume_id: UUID, model_name: str, dims: int, embedding: list[float]) -> None:
        resume_embedding = ResumeEmbedding(
            resume_id=resume_id,
            model_name=model_name,
            dims=dims,
            embedding=embedding
        )
        self.session.add(resume_embedding)
        await self.session.commit()
        await self.session.refresh(resume_embedding)
        return resume_embedding

    async def list_user_resumes(self, user_id: UUID) -> list[ResumeModel]:
        result = await self.session.execute(
            select(ResumeModel)
            .where(ResumeModel.user_id == user_id)
            .order_by(ResumeModel.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def upload_pdf_to_s3(self, file_bytes: bytes, file_name: str, mime_type: str = "application/pdf") -> dict:
        """Upload PDF file to S3 bucket"""
        # Generate unique filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{file_name}"
        
        # Upload to S3
        upload_result = await self.s3_service.upload_file(file_bytes, unique_filename, mime_type)
        
        return {
            "file_key": upload_result["file_key"],
            "view_url": upload_result["file_url"],
            "original_filename": file_name
        }

    async def download_file_from_s3(self, file_key: str) -> bytes:
        """Download file from S3"""
        return await self.s3_service.download_file(file_key)

    async def delete_resume(self, resume_id: UUID, user_id: UUID) -> bool:
        resume = await self.session.get(ResumeModel, resume_id)
        if not resume or resume.user_id != user_id:
            return False

        # Try deleting from S3, but don't fail DB deletion if file missing
        try:
            await self.s3_service.delete_file(resume.storage_file_id)
        except Exception as e:
            # Log and continue (e.g., file already removed)
            LOGGER.warning("S3 delete failed for %s: %s", resume.storage_file_id, e)

        await self.session.delete(resume)
        await self.session.commit()
        return True