"""
Admin API routes – JSON endpoints consumed by the admin panel frontend.

Every route depends on `current_admin_user` which returns 403 for
non-superusers and 401 for unauthenticated requests.
"""

from __future__ import annotations

import os
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.userModel import User
from app.services.adminService import AdminService, current_admin_user
from app.services.resourceService import ResourceService
from app.schemas.resourceSchema import ResourceCreate

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


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/stats")
async def admin_stats(
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    return await svc.get_dashboard_stats()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@router.get("/users")
async def list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    users = await svc.list_users(skip=skip, limit=limit)
    total = await svc.count_users()
    return {"users": [_user_to_dict(u) for u in users], "total": total}


@router.patch("/users/{user_id}/toggle-active")
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


@router.patch("/users/{user_id}/toggle-superuser")
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


@router.delete("/users/{user_id}")
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

@router.get("/communities")
async def list_communities(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    communities = await svc.list_communities(skip=skip, limit=limit)
    return {
        "communities": [
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
    }


@router.delete("/communities/{community_id}")
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

@router.get("/resources")
async def list_resources(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    resources = await svc.list_resources(skip=skip, limit=limit)
    return {
        "resources": [
            {
                "id": str(r.id),
                "title": r.title,
                "description": r.description,
                "category": r.category,
                "icon": r.icon,
                "level": r.level,
                "tags": r.tags or [],
                "estimated_duration_minutes": r.estimated_duration_minutes,
                "external_url": r.external_url,
                "is_published": r.is_published,
                "is_locked": r.is_locked,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in resources
        ]
    }


@router.get("/resources/{resource_id}")
async def get_resource_detail(
    resource_id: uuid.UUID,
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    resource = await svc.get_resource_with_outline(resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return svc.build_resource_detail_payload(resource)


@router.post("/resources")
async def create_resource(
    payload: ResourceCreate,
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    try:
        resource = await svc.create_resource(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "id": str(resource.id),
        "title": resource.title,
        "is_published": resource.is_published,
        "is_locked": resource.is_locked,
    }


@router.put("/resources/{resource_id}")
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
        raise HTTPException(status_code=400, detail=str(exc))
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return {
        "id": str(resource.id),
        "title": resource.title,
        "is_published": resource.is_published,
        "is_locked": resource.is_locked,
    }


@router.post("/resources/upload-file")
async def upload_resource_file(
    file: UploadFile = File(...),
    _write_guard: None = Depends(require_same_origin_for_write),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        return await svc.upload_resource_file(
            file_bytes=file_bytes,
            file_name=file.filename or "resource_file",
            content_type=file.content_type or "application/octet-stream",
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.patch("/resources/{resource_id}/toggle-published")
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


@router.patch("/resources/{resource_id}/toggle-locked")
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


@router.delete("/resources/{resource_id}")
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

@router.get("/jobs")
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


@router.patch("/jobs/{job_id}/toggle-active")
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


@router.delete("/jobs/{job_id}")
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

@router.get("/companies")
async def list_companies(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    companies = await svc.list_companies(skip=skip, limit=limit)
    return {
        "companies": [
            {
                "id": str(c.id),
                "company_name": c.company_name,
                "industry": c.industry,
                "location": c.location,
                "website": c.website,
                "email": c.email,
            }
            for c in companies
        ]
    }


@router.delete("/companies/{company_id}")
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

@router.get("/applications")
async def list_applications(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    apps = await svc.list_applications(skip=skip, limit=limit)
    return {
        "applications": [
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
    }
