"""
Admin API routes – JSON endpoints consumed by the admin panel frontend.

Every route depends on `current_admin_user` which returns 403 for
non-superusers and 401 for unauthenticated requests.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.userModel import User
from app.services.adminService import AdminService, current_admin_user
from app.schemas.resourceSchema import ResourceCreate

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_service(session: AsyncSession = Depends(get_session)) -> AdminService:
    return AdminService(session)


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
    skip: int = 0,
    limit: int = 50,
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    users = await svc.list_users(skip=skip, limit=limit)
    total = await svc.count_users()
    return {"users": [_user_to_dict(u) for u in users], "total": total}


@router.patch("/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: uuid.UUID,
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


# ---------------------------------------------------------------------------
# Communities
# ---------------------------------------------------------------------------

@router.get("/communities")
async def list_communities(
    skip: int = 0,
    limit: int = 50,
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
    skip: int = 0,
    limit: int = 50,
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    resources = await svc.list_resources(skip=skip, limit=limit)
    return {
        "resources": [
            {
                "id": str(r.id),
                "title": r.title,
                "category": r.category,
                "level": r.level,
                "is_published": r.is_published,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in resources
        ]
    }


@router.post("/resources")
async def create_resource(
    payload: ResourceCreate,
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    resource = await svc.create_resource(payload)
    return {
        "id": str(resource.id),
        "title": resource.title,
        "is_published": resource.is_published,
    }


@router.patch("/resources/{resource_id}/toggle-published")
async def toggle_resource_published(
    resource_id: uuid.UUID,
    admin: User = Depends(current_admin_user),
    svc: AdminService = Depends(_get_service),
):
    resource = await svc.toggle_resource_published(resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return {"id": str(resource.id), "is_published": resource.is_published}


@router.delete("/resources/{resource_id}")
async def delete_resource(
    resource_id: uuid.UUID,
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
    skip: int = 0,
    limit: int = 50,
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
    skip: int = 0,
    limit: int = 50,
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
    skip: int = 0,
    limit: int = 50,
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
