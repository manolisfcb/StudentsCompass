from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import MAX_UPLOAD_BYTES
from app.core.idempotency import actor_key, begin_idempotent_request
from app.core.uploads import ensure_allowed_upload, read_upload_within_limit
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
    ResumeDeleteRead,
    ResumeReadSchema,
    ResumeUploadRead,
)
from app.db import get_session
from app.services.accounts.userService import current_active_user, current_ai_user
from app.services.storage.storageService import get_resume_storage_location_id
from app.models.userModel import User
from uuid import UUID
import logging

from app.core.errors import (
    CODE_RESUME_STORAGE_UNCONFIGURED,
    CODE_RESUME_UPLOAD,
    new_error_reference,
    server_failure,
)

LOGGER = logging.getLogger(__name__)


LOGGER.setLevel(logging.DEBUG)

router = APIRouter()
# TASK-047 (plan 08 §5.2): `/resumes` and `/resume-course-audits` are the
# renamed contract React consumes. `legacy_router` keeps the `/profile/cv/*`
# paths the Jinja pages and their JS still call, mounted with
# `include_in_schema=False` — the same two-mounts-of-one-router pattern the
# auth routes already use in `app.py`, so a stable `operationId` (`{tag}_{name}`,
# `app/core/openapi.py`) never has two paths fighting for it. The route
# functions below are registered on `legacy_router` again at the bottom of this
# file, unmodified: same dependencies, same behaviour, same response shape.
legacy_router = APIRouter()


async def _read_upload_within_limit(cv: UploadFile, request: Request) -> bytes:
    """Read an upload while enforcing a hard size cap.

    The raw body was already bounded by ``RequestBodySizeLimitMiddleware``
    before the multipart parser ran — that is what stops a chunked flood, which
    sends no ``Content-Length`` to pre-check. This second pass is about the
    *file* rather than the request: it reads incrementally and stops one chunk
    past the budget, so the route never materialises more than that.
    """
    return await read_upload_within_limit(cv, MAX_UPLOAD_BYTES)


def _require_resume_storage_location_id() -> str:
    storage_location_id = get_resume_storage_location_id()
    if not storage_location_id:
        # The reason is for the log; the caller only learns the feature is down.
        reference = new_error_reference()
        LOGGER.error(
            "request failed code=%s ref=%s: resume storage location is not configured",
            CODE_RESUME_STORAGE_UNCONFIGURED,
            reference,
        )
        raise HTTPException(
            status_code=503,
            detail=f"CV uploads are temporarily unavailable. (ref: {reference})",
            headers={"X-Error-Code": CODE_RESUME_STORAGE_UNCONFIGURED, "X-Error-Id": reference},
        )
    return storage_location_id


@router.post("/resumes", response_model=ResumeUploadRead)
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
    # The declared type is the client's word for it; the leading bytes are not.
    ensure_allowed_upload(
        data=file_bytes,
        content_type=cv.content_type,
        allowed_content_types=RESUME_UPLOAD_CONTENT_TYPES,
        what="CV",
    )
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
    except Exception as exc:
        raise await server_failure(
            exc,
            logger=LOGGER,
            code=CODE_RESUME_UPLOAD,
            message="The CV could not be uploaded. Please try again.",
            session=session,
            context=f"user_id={user.id}",
        )


@router.post("/resume-course-audits", response_model=ResumeCourseAuditRead)
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
    ensure_allowed_upload(
        data=file_bytes,
        content_type=cv.content_type,
        allowed_content_types=RESUME_AUDIT_CONTENT_TYPES,
        what="CV",
    )
    storage_location_id = _require_resume_storage_location_id()

    # The upload that spends AI credit, so plan 08 §5.1 names it for
    # ``Idempotency-Key``. The fingerprint is the file itself: a client that
    # retries the same upload after a lost response gets the first evaluation
    # back, and the same key over a *different* CV is a 409 rather than someone
    # else's audit.
    guard = await begin_idempotent_request(
        session,
        request=request,
        actor=actor_key("user", user.id),
        endpoint="POST /resume-course-audits",
        payload=file_bytes,
    )
    if guard.is_replay:
        return guard.replay

    audit_service = ResumeCourseAuditService(session)
    try:
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
    except Exception:
        await guard.release()
        raise
    return await guard.store(ResumeCourseAuditRead(**payload))


@router.get("/resume-course-audits/attempts", response_model=ResumeCourseAuditAttemptsRead)
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


@router.get("/resumes", response_model=list[ResumeReadSchema])
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


@router.delete("/resumes/{resume_id}", response_model=ResumeDeleteRead)
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


# --- Legacy adapter (TASK-047, plan 08 §13) -----------------------------------
#
# Same functions, old paths, hidden from the OpenAPI document. The Jinja CV
# screen and its JS (`userProfile.js`, `resource_detail.js`) keep calling these
# until TASK-059 confirms zero traffic and retires them; nothing here may change
# behaviour, so no `response_model` is added where the original route did not
# have one.
legacy_router.add_api_route("/profile/cv/upload", upload_resume, methods=["POST"], include_in_schema=False)
legacy_router.add_api_route(
    "/profile/cv/course-audit-upload",
    upload_resume_for_course_audit,
    methods=["POST"],
    response_model=ResumeCourseAuditRead,
    include_in_schema=False,
)
legacy_router.add_api_route(
    "/profile/cv/course-audit-attempts",
    get_course_audit_attempts,
    methods=["GET"],
    response_model=ResumeCourseAuditAttemptsRead,
    include_in_schema=False,
)
legacy_router.add_api_route(
    "/profile/cv",
    list_resumes,
    methods=["GET"],
    response_model=list[ResumeReadSchema],
    include_in_schema=False,
)
legacy_router.add_api_route(
    "/profile/cv/{resume_id}", delete_resume, methods=["DELETE"], include_in_schema=False
)
