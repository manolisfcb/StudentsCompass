"""
Admin API routes – JSON endpoints consumed by the admin panel frontend.

Every route depends on `current_admin_user` which returns 403 for
non-superusers and 401 for unauthenticated requests.
"""

from __future__ import annotations

import logging
import os
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import MAX_COLLECTION_ROWS, clamp_page_number, clamp_page_size
from app.core.errors import (
    CODE_ADMIN_RESOURCE_INVALID,
    CODE_ADMIN_RESOURCE_UPLOAD,
    client_failure,
    server_failure,
)
from app.db import get_session
from app.models.applicationModel import ApplicationModel
from app.models.communityModel import CommunityModel
from app.models.companyModel import Company
from app.models.jobPostingModel import JobPosting
from app.models.resourceModel import ResourceModel
from app.models.userModel import User
from app.schemas.adminSchema import (
    AdminApplicationsPage,
    AdminCommunitiesPage,
    AdminCompaniesPage,
    AdminDeleteRead,
    AdminJobPostingPatch,
    AdminJobPostingRead,
    AdminJobPostingsPage,
    AdminResourceDetailRead,
    AdminResourceFileRead,
    AdminResourceMutationRead,
    AdminResourcesPage,
    AdminResourceStatePatch,
    AdminStatsRead,
    AdminUserPatch,
    AdminUserRead,
    AdminUsersPage,
)
from app.schemas.resourceSchema import ResourceCreate
from app.services.admin.adminService import AdminService, current_admin_user
from app.services.resources.resourceService import ResourceService

LOGGER = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_service(session: AsyncSession = Depends(get_session)) -> AdminService:
    return AdminService(session)


def _normalize_origin(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _build_expected_origins(request: Request) -> set[str]:
    origins: set[str] = set()

    base_origin = _normalize_origin(str(request.base_url))
    if base_origin:
        origins.add(base_origin)

    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    forwarded_host = (request.headers.get("x-forwarded-host") or "").split(",")[0].strip().lower()
    if forwarded_proto and forwarded_host:
        forwarded_origin = _normalize_origin(f"{forwarded_proto}://{forwarded_host}")
        if forwarded_origin:
            origins.add(forwarded_origin)

    host = (request.headers.get("host") or "").split(",")[0].strip().lower()
    if host:
        scheme = forwarded_proto or request.url.scheme
        host_origin = _normalize_origin(f"{scheme}://{host}")
        if host_origin:
            origins.add(host_origin)

    public_origin = _normalize_origin(os.getenv("APP_BASE_URL") or os.getenv("PUBLIC_APP_ORIGIN"))
    if public_origin:
        origins.add(public_origin)

    configured_cors = os.getenv("CORS_ORIGINS", "")
    if configured_cors.strip():
        for raw_origin in configured_cors.split(","):
            normalized = _normalize_origin(raw_origin.strip())
            if normalized:
                origins.add(normalized)

    return origins


async def require_same_origin_for_write(
    request: Request,
    origin: str | None = Header(default=None),
    referer: str | None = Header(default=None),
) -> None:
    """
    Basic CSRF mitigation for cookie-authenticated admin write endpoints.
    Requires same-origin Origin/Referer on state-changing requests.
    """
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return

    source_origin = origin
    if not source_origin and referer:
        parsed_referer = urlparse(referer)
        if parsed_referer.scheme and parsed_referer.netloc:
            source_origin = f"{parsed_referer.scheme}://{parsed_referer.netloc}"

    if not source_origin:
        # Some deployments strip Origin/Referer in same-origin requests.
        # Keep CSRF guard by allowing only explicit same-origin fetch context.
        if (request.headers.get("sec-fetch-site") or "").lower() == "same-origin":
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing request origin headers.",
        )

    normalized_source_origin = _normalize_origin(source_origin)
    if not normalized_source_origin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Malformed request origin.",
        )

    expected_origins = _build_expected_origins(request)
    if normalized_source_origin not in expected_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-origin admin write request blocked.",
        )


def _user_to_dict(u: User) -> dict:
    return {
        "id": str(u.id),
        "email": u.email,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "nickname": u.nickname,
        "is_active": u.is_active,
        "is_superuser": u.is_superuser,
        "is_verified": u.is_verified,
    }


def _page_args(
    *,
    page: int | None,
    page_size: int | None,
    skip: int | None,
    limit: int | None,
) -> tuple[int, int, int]:
    """Resolve both the REST page contract and the temporary offset adapter."""
    if skip is not None or limit is not None:
        size = clamp_page_size(limit, default=50, maximum=MAX_COLLECTION_ROWS)
        offset = max(0, skip or 0)
        return (offset // size) + 1, size, offset
    resolved_page = clamp_page_number(page)
    size = clamp_page_size(page_size)
    return resolved_page, size, (resolved_page - 1) * size


def _resource_to_dict(resource: ResourceModel) -> dict:
    return {
        "id": str(resource.id),
        "title": resource.title,
        "description": resource.description,
        "category": resource.category,
        "icon": resource.icon,
        "level": resource.level,
        "tags": resource.tags or [],
        "estimated_duration_minutes": resource.estimated_duration_minutes,
        "external_url": resource.external_url,
        "is_published": resource.is_published,
        "is_locked": resource.is_locked,
        "created_at": resource.created_at.isoformat() if resource.created_at else None,
        "updated_at": resource.updated_at.isoformat() if resource.updated_at else None,
    }


def _job_to_dict(job: JobPosting) -> dict:
    return {
        "id": str(job.id),
        "title": job.title,
        "company_name": job.company.company_name if job.company else "—",
        "location": job.location,
        "job_type": job.job_type,
        "is_active": job.is_active,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=AdminStatsRead)
async def admin_stats(
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    return await svc.get_dashboard_stats()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@router.get("/users", response_model=AdminUsersPage)
async def list_users(
    page: int | None = Query(default=None),
    page_size: int | None = Query(default=None),
    skip: int | None = Query(default=None, ge=0, deprecated=True),
    limit: int | None = Query(default=None, ge=1, deprecated=True),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    resolved_page, size, offset = _page_args(page=page, page_size=page_size, skip=skip, limit=limit)
    users = await svc.list_users(skip=offset, limit=size)
    total = await svc.count_users()
    items = [_user_to_dict(u) for u in users]
    return {"items": items, "page": resolved_page, "page_size": size, "total": total, "users": items}


@router.patch("/users/{user_id}", response_model=AdminUserRead)
async def update_user(
    user_id: uuid.UUID,
    payload: AdminUserPatch,
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    changes = payload.model_dump(exclude_unset=True)
    if user_id == admin.id and changes.get("is_superuser") is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove your own admin privileges.",
        )
    user = await svc.update_user_flags(user_id, **changes)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_to_dict(user)


@router.patch("/users/{user_id}/toggle-active", deprecated=True)
async def toggle_user_active(
    user_id: uuid.UUID,
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    user = await svc.toggle_user_active(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_to_dict(user)


@router.patch("/users/{user_id}/toggle-superuser", deprecated=True)
async def toggle_user_superuser(
    user_id: uuid.UUID,
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove your own admin privileges.",
        )
    user = await svc.toggle_user_superuser(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_to_dict(user)


@router.delete("/users/{user_id}", response_model=AdminDeleteRead)
async def delete_user(
    user_id: uuid.UUID,
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account from the admin panel.",
        )
    ok = await svc.delete_user(user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


@router.get("/users/{user_id}/resource-progress")
async def user_resource_progress(
    user_id: uuid.UUID,
    admin: User = Depends(current_admin_user),
    session: AsyncSession = Depends(get_session),
):
    service = ResourceService(session)
    progress = await service.list_user_enrollment_progress(user_id)
    return {"user_id": str(user_id), "resources": progress}


# ---------------------------------------------------------------------------
# Communities
# ---------------------------------------------------------------------------

@router.get("/communities", response_model=AdminCommunitiesPage)
async def list_communities(
    page: int | None = Query(default=None),
    page_size: int | None = Query(default=None),
    skip: int | None = Query(default=None, ge=0, deprecated=True),
    limit: int | None = Query(default=None, ge=1, deprecated=True),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    resolved_page, size, offset = _page_args(page=page, page_size=page_size, skip=skip, limit=limit)
    communities = await svc.list_communities(skip=offset, limit=size)
    items = [
            {
                "id": str(c.id),
                "name": c.name,
                "description": c.description,
                "icon": c.icon,
                "member_count": c.member_count,
                "activity_status": c.activity_status,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "creator_email": c.creator.email if c.creator else None,
            }
            for c in communities
        ]
    return {
        "items": items,
        "page": resolved_page,
        "page_size": size,
        "total": await svc.count_rows(CommunityModel),
        "communities": items,
    }


@router.delete("/communities/{community_id}", response_model=AdminDeleteRead)
async def delete_community(
    community_id: uuid.UUID,
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    ok = await svc.delete_community(community_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Community not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@router.get("/resources", response_model=AdminResourcesPage)
async def list_resources(
    page: int | None = Query(default=None),
    page_size: int | None = Query(default=None),
    skip: int | None = Query(default=None, ge=0, deprecated=True),
    limit: int | None = Query(default=None, ge=1, deprecated=True),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    resolved_page, size, offset = _page_args(page=page, page_size=page_size, skip=skip, limit=limit)
    resources = await svc.list_resources(skip=offset, limit=size)
    items = [_resource_to_dict(resource) for resource in resources]
    return {
        "items": items,
        "page": resolved_page,
        "page_size": size,
        "total": await svc.count_rows(ResourceModel),
        "resources": items,
    }


@router.get("/resources/{resource_id}", response_model=AdminResourceDetailRead)
async def get_resource_detail(
    resource_id: uuid.UUID,
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    resource = await svc.get_resource_with_outline(resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return svc.build_resource_detail_payload(resource)


@router.post("/resources", response_model=AdminResourceMutationRead, status_code=status.HTTP_201_CREATED)
async def create_resource(
    payload: ResourceCreate,
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    try:
        resource = await svc.create_resource(payload)
    except ValueError as exc:
        # The outline is validated after rows are already flushed, so the
        # session has pending work that must not survive the failed request.
        raise await client_failure(
            exc,
            logger=LOGGER,
            code=CODE_ADMIN_RESOURCE_INVALID,
            fallback_message="The resource could not be saved as submitted.",
            session=svc.session,
        )
    except Exception as exc:
        raise await server_failure(
            exc,
            logger=LOGGER,
            code=CODE_ADMIN_RESOURCE_INVALID,
            message="The resource could not be created.",
            session=svc.session,
        )
    return {
        "id": str(resource.id),
        "title": resource.title,
        "is_published": resource.is_published,
        "is_locked": resource.is_locked,
    }


@router.put("/resources/{resource_id}", response_model=AdminResourceMutationRead)
async def update_resource(
    resource_id: uuid.UUID,
    payload: ResourceCreate,
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    try:
        resource = await svc.update_resource(resource_id, payload)
    except ValueError as exc:
        raise await client_failure(
            exc,
            logger=LOGGER,
            code=CODE_ADMIN_RESOURCE_INVALID,
            fallback_message="The resource could not be saved as submitted.",
            session=svc.session,
        )
    except Exception as exc:
        raise await server_failure(
            exc,
            logger=LOGGER,
            code=CODE_ADMIN_RESOURCE_INVALID,
            message="The resource could not be updated.",
            session=svc.session,
        )
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return {
        "id": str(resource.id),
        "title": resource.title,
        "is_published": resource.is_published,
        "is_locked": resource.is_locked,
    }


async def _store_resource_file(file: UploadFile, svc: AdminService) -> dict:
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        return await svc.upload_resource_file(
            file_bytes=file_bytes,
            file_name=file.filename or "resource_file",
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as exc:
        raise await server_failure(
            exc,
            logger=LOGGER,
            code=CODE_ADMIN_RESOURCE_UPLOAD,
            message="The file could not be uploaded.",
            session=svc.session,
        )


@router.post("/resource-files", response_model=AdminResourceFileRead, status_code=status.HTTP_201_CREATED)
async def create_resource_file(
    file: UploadFile = File(...),
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    return await _store_resource_file(file, svc)


@router.post("/resources/upload-file", response_model=AdminResourceFileRead, deprecated=True)
async def upload_resource_file(
    file: UploadFile = File(...),
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    return await _store_resource_file(file, svc)


@router.patch("/resources/{resource_id}", response_model=AdminResourceMutationRead)
async def update_resource_state(
    resource_id: uuid.UUID,
    payload: AdminResourceStatePatch,
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    resource = await svc.update_resource_state(
        resource_id,
        **payload.model_dump(exclude_unset=True),
    )
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return {
        "id": str(resource.id),
        "title": resource.title,
        "is_published": resource.is_published,
        "is_locked": resource.is_locked,
    }


@router.patch("/resources/{resource_id}/toggle-published", deprecated=True)
async def toggle_resource_published(
    resource_id: uuid.UUID,
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    resource = await svc.toggle_resource_published(resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return {"id": str(resource.id), "is_published": resource.is_published}


@router.patch("/resources/{resource_id}/toggle-locked", deprecated=True)
async def toggle_resource_locked(
    resource_id: uuid.UUID,
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    resource = await svc.toggle_resource_locked(resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return {"id": str(resource.id), "is_locked": resource.is_locked}


@router.delete("/resources/{resource_id}", response_model=AdminDeleteRead)
async def delete_resource(
    resource_id: uuid.UUID,
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    ok = await svc.delete_resource(resource_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Resource not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@router.get("/job-postings", response_model=AdminJobPostingsPage)
async def list_job_postings(
    page: int | None = Query(default=None),
    page_size: int | None = Query(default=None),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    resolved_page, size, offset = _page_args(page=page, page_size=page_size, skip=None, limit=None)
    jobs = await svc.list_jobs(skip=offset, limit=size)
    return {
        "items": [_job_to_dict(job) for job in jobs],
        "page": resolved_page,
        "page_size": size,
        "total": await svc.count_rows(JobPosting),
    }


@router.patch("/job-postings/{job_id}", response_model=AdminJobPostingRead)
async def update_job_posting(
    job_id: uuid.UUID,
    payload: AdminJobPostingPatch,
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    job = await svc.update_job_state(job_id, is_active=payload.is_active)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_dict(job)


@router.delete("/job-postings/{job_id}", response_model=AdminDeleteRead)
async def delete_job_posting(
    job_id: uuid.UUID,
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    ok = await svc.delete_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True}


@router.get("/jobs", deprecated=True)
async def list_jobs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    jobs = await svc.list_jobs(skip=skip, limit=limit)
    return {
        "jobs": [
            {
                "id": str(j.id),
                "title": j.title,
                "company_name": j.company.company_name if j.company else "—",
                "location": j.location,
                "job_type": j.job_type,
                "is_active": j.is_active,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in jobs
        ]
    }


@router.patch("/jobs/{job_id}/toggle-active", deprecated=True)
async def toggle_job_active(
    job_id: uuid.UUID,
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    job = await svc.toggle_job_active(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"id": str(job.id), "is_active": job.is_active}


@router.delete("/jobs/{job_id}", deprecated=True)
async def delete_job(
    job_id: uuid.UUID,
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    ok = await svc.delete_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------

@router.get("/companies", response_model=AdminCompaniesPage)
async def list_companies(
    page: int | None = Query(default=None),
    page_size: int | None = Query(default=None),
    skip: int | None = Query(default=None, ge=0, deprecated=True),
    limit: int | None = Query(default=None, ge=1, deprecated=True),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    resolved_page, size, offset = _page_args(page=page, page_size=page_size, skip=skip, limit=limit)
    companies = await svc.list_companies(skip=offset, limit=size)
    items = [
            {
                "id": str(c.id),
                "company_name": c.company_name,
                "industry": c.industry,
                "location": c.location,
                "website": c.website,
                # Company has no email column. The legacy route attempted to
                # read it and returned 500; null is the honest contract.
                "email": None,
            }
            for c in companies
        ]
    return {
        "items": items,
        "page": resolved_page,
        "page_size": size,
        "total": await svc.count_rows(Company),
        "companies": items,
    }


@router.delete("/companies/{company_id}", response_model=AdminDeleteRead)
async def delete_company(
    company_id: uuid.UUID,
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    ok = await svc.delete_company(company_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Company not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

@router.get("/applications", response_model=AdminApplicationsPage)
async def list_applications(
    page: int | None = Query(default=None),
    page_size: int | None = Query(default=None),
    skip: int | None = Query(default=None, ge=0, deprecated=True),
    limit: int | None = Query(default=None, ge=1, deprecated=True),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    resolved_page, size, offset = _page_args(page=page, page_size=page_size, skip=skip, limit=limit)
    apps = await svc.list_applications(skip=offset, limit=size)
    items = [
            {
                "id": str(a.id),
                "job_title": a.job_title,
                "status": a.status.value if a.status else None,
                "user_email": a.user.email if a.user else None,
                "company_name": a.company.company_name if a.company else None,
                "application_date": a.application_date.isoformat() if a.application_date else None,
            }
            for a in apps
        ]
    return {
        "items": items,
        "page": resolved_page,
        "page_size": size,
        "total": await svc.count_rows(ApplicationModel),
        "applications": items,
    }
