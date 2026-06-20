from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import MAX_UPLOAD_BYTES
from app.services.resumes.resumeService import (
    RESUME_AUDIT_CONTENT_TYPES,
    RESUME_UPLOAD_CONTENT_TYPES,
    ResumeService,
    is_allowed_resume_content_type,
)
from app.services.resumes.resumeCourseAuditService import ResumeCourseAuditService
from app.services.analytics.embeddingService import ResumeEmbeddingService
from app.schemas.resumeSchema import (
    ResumeCourseAuditAttemptsRead,
    ResumeCourseAuditRead,
    ResumeReadSchema,
)
from app.db import get_session
from app.services.accounts.userService import current_active_user, current_ai_user
from app.services.storage.storageService import get_resume_storage_location_id
from app.models.userModel import User
from uuid import UUID
import logging
LOGGER = logging.getLogger(__name__)


LOGGER.setLevel(logging.DEBUG)

router = APIRouter()


async def _read_upload_within_limit(cv: UploadFile, request: Request) -> bytes:
    """Read an upload while enforcing a hard size cap.

    Rejects early via Content-Length (so an oversized body is not buffered into
    memory) and re-checks the actual bytes. Prevents memory exhaustion and
    storage abuse from very large files.
    """
    too_large = HTTPException(
        status_code=413,
        detail=f"File is too large. Maximum allowed size is {MAX_UPLOAD_BYTES // 1_000_000} MB.",
    )
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_UPLOAD_BYTES:
        raise too_large
    data = await cv.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise too_large
    return data


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
    request: Request,
    cv: UploadFile = File(..., alias="cv"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    LOGGER.debug(f"Received file: {cv.filename}, content type: {cv.content_type}")
    if not is_allowed_resume_content_type(cv.content_type, RESUME_UPLOAD_CONTENT_TYPES):
        raise HTTPException(status_code=400, detail="Only PDF or DOC/DOCX files are allowed.")

    # Size cap is the first gate: reject oversized uploads before any other work.
    file_bytes = await _read_upload_within_limit(cv, request)
    storage_location_id = _require_resume_storage_location_id()

    try:
        LOGGER.debug("Initializing ResumeService")
        resume_service = ResumeService(session)
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
    request: Request,
    cv: UploadFile = File(..., alias="cv"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_ai_user),
):
    LOGGER.debug(f"Course audit upload received: {cv.filename}, type={cv.content_type}")
    if not is_allowed_resume_content_type(cv.content_type, RESUME_AUDIT_CONTENT_TYPES):
        raise HTTPException(status_code=400, detail="Only PDF or DOCX files are allowed for AI audit.")

    # Size cap is the first gate: reject oversized uploads before any other work.
    file_bytes = await _read_upload_within_limit(cv, request)
    storage_location_id = _require_resume_storage_location_id()

    audit_service = ResumeCourseAuditService(session)
    # Cheap pre-check for fast rejection; the atomic reservation happens inside
    # upload_and_evaluate_resume before any LLM spend.
    await audit_service.ensure_daily_limit(user.id)
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


@router.get("/profile/cv/{resume_id}/similar")
async def find_similar_resumes(
    resume_id: UUID,
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    """Return resumes whose stored embedding is closest to this resume's.

    Demonstrable consumer of the pgvector ``<=>`` engine. It only verifies that
    the caller owns the source resume and returns opaque resume IDs + scores;
    the product decision on whether/how to surface other users' resumes (and the
    associated PII/authorization policy) is intentionally left to the owner.
    Requires a PostgreSQL backend with the ``vector`` extension.
    """
    resume_service = ResumeService(session)
    resume = await resume_service.get_user_resume(resume_id=resume_id, user_id=user.id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    k = max(1, min(limit, 50))
    embedding_service = ResumeEmbeddingService(session)
    results = await embedding_service.find_similar_resumes(resume_id=resume_id, k=k)
    return {"resume_id": resume_id, "results": results}


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
