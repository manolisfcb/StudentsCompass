from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.resumeService import (
    RESUME_AUDIT_CONTENT_TYPES,
    RESUME_UPLOAD_CONTENT_TYPES,
    ResumeService,
    is_allowed_resume_content_type,
)
from app.services.resumeCourseAuditService import ResumeCourseAuditService
from app.schemas.resumeSchema import (
    ResumeCourseAuditAttemptsRead,
    ResumeCourseAuditRead,
    ResumeReadSchema,
)
from app.db import get_session
from app.services.userService import current_active_user
from app.services.storageService import get_resume_storage_location_id
from app.models.userModel import User
from uuid import UUID
import logging
LOGGER = logging.getLogger(__name__)


LOGGER.setLevel(logging.DEBUG)

router = APIRouter()


def _require_resume_storage_location_id() -> str:
    storage_location_id = get_resume_storage_location_id()
    if not storage_location_id:
        LOGGER.error("Resume storage location is not configured")
        raise HTTPException(
            status_code=500,
            detail="Server misconfiguration: missing resume storage configuration",
        )
    return storage_location_id


@router.post("/profile/cv/upload")
async def upload_resume(
    cv: UploadFile = File(..., alias="cv"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    LOGGER.debug(f"Received file: {cv.filename}, content type: {cv.content_type}")
    if not is_allowed_resume_content_type(cv.content_type, RESUME_UPLOAD_CONTENT_TYPES):
        raise HTTPException(status_code=400, detail="Only PDF or DOC/DOCX files are allowed.")
    
    storage_location_id = _require_resume_storage_location_id()

    try:
        LOGGER.debug("Initializing ResumeService")
        resume_service = ResumeService(session)
        file_bytes = await cv.read()
        resume, file_info = await resume_service.create_resume_from_upload(
            user_id=user.id,
            storage_location_id=storage_location_id,
            file_bytes=file_bytes,
            file_name=cv.filename,
            mime_type=cv.content_type,
        )
        LOGGER.debug("Resume uploaded to storage and record created: %s", resume.id)
        
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
    if not is_allowed_resume_content_type(cv.content_type, RESUME_AUDIT_CONTENT_TYPES):
        raise HTTPException(status_code=400, detail="Only PDF or DOCX files are allowed for AI audit.")

    storage_location_id = _require_resume_storage_location_id()

    audit_service = ResumeCourseAuditService(session)
    await audit_service.ensure_daily_limit(user.id)

    file_bytes = await cv.read()
    payload, _ = await audit_service.upload_and_evaluate_resume(
        user_id=user.id,
        storage_location_id=storage_location_id,
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
    daily_limit = await audit_service.get_daily_limit(user.id)
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
    resumes = await resume_service.list_user_resumes(user.id)
    return [ResumeReadSchema.from_model(resume) for resume in resumes]


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
