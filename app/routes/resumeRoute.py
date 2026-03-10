from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.resumeService import ResumeService
from app.services.resumeCourseAuditService import ResumeCourseAuditService
from app.schemas.resumeSchema import (
    CreateResumeSchema,
    ResumeCourseAuditAttemptsRead,
    ResumeCourseAuditRead,
    ResumeReadSchema,
)
from app.db import get_session
from app.services.userService import current_active_user
from app.models.userModel import User
from uuid import UUID
import os
import logging
LOGGER = logging.getLogger(__name__)


LOGGER.setLevel(logging.DEBUG)

BUCKET_NAME = os.getenv("BUCKET_NAME")

router = APIRouter()


@router.post("/profile/cv/upload")
async def upload_resume(
    cv: UploadFile = File(..., alias="cv"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user)):
    LOGGER.debug(f"Received file: {cv.filename}, content type: {cv.content_type}")
    if cv.content_type not in {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"}:
        raise HTTPException(status_code=400, detail="Only PDF or DOC/DOCX files are allowed.")
    
    if not BUCKET_NAME:
        LOGGER.error("BUCKET_NAME is not set")
        raise HTTPException(status_code=500, detail="Server misconfiguration: missing S3 bucket name")

    try:
        LOGGER.debug("Initializing ResumeService")
        resume_service = ResumeService(session)
        file_bytes = await cv.read()
        file_info = await resume_service.upload_pdf_to_s3(file_bytes, cv.filename, cv.content_type)
        LOGGER.debug(f"File uploaded to S3: {file_info}")
        
        # Save resume info to database
        resume_create = CreateResumeSchema(
            view_url=file_info["view_url"],
            original_filename=cv.filename,
            storage_file_id=file_info["file_key"],
            folder_id=BUCKET_NAME,
            user_id=user.id
        )
        resume = await resume_service.create_resume(resume_create)
        LOGGER.debug(f"Resume record created: {resume.id}")
        
        # Desactivado: No se generan ni guardan embeddings para el resume
        return {"file_url": file_info["view_url"], "resume_id": resume.id}
    except Exception as e:
        LOGGER.exception("Upload failed")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.post("/profile/cv/course-audit-upload", response_model=ResumeCourseAuditRead)
async def upload_resume_for_course_audit(
    cv: UploadFile = File(..., alias="cv"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    LOGGER.debug(f"Course audit upload received: {cv.filename}, type={cv.content_type}")
    valid_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    if cv.content_type not in valid_types:
        raise HTTPException(status_code=400, detail="Only PDF or DOCX files are allowed for AI audit.")

    if not BUCKET_NAME:
        raise HTTPException(status_code=500, detail="Server misconfiguration: missing S3 bucket name")

    audit_service = ResumeCourseAuditService(session)
    await audit_service.ensure_daily_limit(user.id)

    file_bytes = await cv.read()
    payload, _ = await audit_service.upload_and_evaluate_resume(
        user_id=user.id,
        bucket_name=BUCKET_NAME,
        file_bytes=file_bytes,
        filename=cv.filename,
        content_type=cv.content_type,
    )
    return ResumeCourseAuditRead(**payload)


@router.get("/profile/cv/course-audit-attempts", response_model=ResumeCourseAuditAttemptsRead)
async def get_course_audit_attempts(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    audit_service = ResumeCourseAuditService(session)
    attempts_today = await audit_service.get_daily_attempts(user.id)
    daily_limit = audit_service.DAILY_LIMIT
    return ResumeCourseAuditAttemptsRead(
        attempts_today=attempts_today,
        daily_limit=daily_limit,
        attempts_remaining=max(0, daily_limit - attempts_today),
    )


@router.get("/profile/cv", response_model=list[ResumeReadSchema])
async def list_resumes(
    response: Response,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    resume_service = ResumeService(session)
    resumes = [resume for resume in await resume_service.list_user_resumes(user.id) if resume.user_id == user.id]
    return [
        ResumeReadSchema(
            id=r.id,
            user_id=r.user_id,
            view_url=r.view_url,
            original_filename=r.original_filename,
            storage_file_id=r.storage_file_id,
            folder_id=r.folder_id,
            ai_summary=r.ai_summary,
            contact_phone=r.contact_phone,
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
