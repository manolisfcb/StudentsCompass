from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.resumeService import ResumeService
from app.schemas.resumeSchema import CreateResumeSchema, ResumeReadSchema
from app.db import get_session
from app.services.userService import current_active_user
from app.models.userModel import User
from uuid import UUID
import os
import logging
LOGGER = logging.getLogger(__name__)


LOGGER.setLevel(logging.DEBUG)

FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

router = APIRouter()


@router.post("/profile/cv/upload")
async def upload_resume(
    cv: UploadFile = File(..., alias="cv"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user)):
    LOGGER.debug(f"Received file: {cv.filename}, content type: {cv.content_type}")
    if cv.content_type not in {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"}:
        raise HTTPException(status_code=400, detail="Only PDF or DOC/DOCX files are allowed.")
    
    if not FOLDER_ID:
        LOGGER.error("GOOGLE_DRIVE_FOLDER_ID is not set")
        raise HTTPException(status_code=500, detail="Server misconfiguration: missing drive folder id")

    try:
        LOGGER.debug("Initializing ResumeService")
        resume_service = ResumeService(session)
        file_bytes = await cv.read()
        file_info = await resume_service.upload_pdf_to_drive(file_bytes, cv.filename, cv.content_type)
        LOGGER.debug(f"File uploaded to Google Drive: {file_info}")
        # Save resume info to database
        resume_create = CreateResumeSchema(
            view_url=file_info["view_url"],
            original_filename=cv.filename,
            storage_file_id=file_info["file_id"],
            folder_id=FOLDER_ID,
            user_id=user.id
        )
        resume = await resume_service.create_resume(resume_create)
        return {"file_url": file_info["view_url"], "resume_id": resume.id}
    except Exception as e:
        LOGGER.exception("Upload failed")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.get("/profile/cv", response_model=list[ResumeReadSchema])
async def list_resumes(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    resume_service = ResumeService(session)
    resumes = await resume_service.list_user_resumes(user.id)
    return [
        ResumeReadSchema(
            id=r.id,
            user_id=r.user_id,
            view_url=r.view_url,
            original_filename=r.original_filename,
            storage_file_id=r.storage_file_id,
            folder_id=r.folder_id,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in resumes
    ]


@router.delete("/profile/cv/{resume_id}")
async def delete_resume(
    resume_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    resume_service = ResumeService(session)
    deleted = await resume_service.delete_resume(resume_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Resume not found")
    return {"status": "deleted"}