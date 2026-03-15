import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services.companyService import (
    current_active_company_optional,
    current_active_company_recruiter_optional,
)
from app.services.resourceService import ResourceService
from app.services.roadmapService import RoadmapService
from app.services.userService import current_active_user_optional
from app.models.userModel import User
from app.models.companyModel import Company
from app.models.companyRecruiterModel import CompanyRecruiter
from app.template_utils import configure_template_helpers
from typing import Optional

_ROADMAP_TABLES = (
    "roadmaps", "user_roadmaps", "roadmap_stages", "stage_tasks",
    "stage_projects", "user_task_progress", "user_stage_progress",
    "user_project_submissions",
)


def _is_missing_roadmap_tables_error(exc: Exception) -> bool:
    message = str(exc).lower()
    if "does not exist" not in message and "undefinedtableerror" not in message:
        return False
    return any(t in message for t in _ROADMAP_TABLES)


router = APIRouter()

templates = configure_template_helpers(Jinja2Templates(directory="app/templates"))
RESOURCE_DETAIL_ACCESS_ENABLED = True

@router.get("/")
async def root(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@router.get("/home")
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@router.get("/about")
async def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})


@router.get("/login")
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.get("/api/v1/auth/register")
async def register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.get("/dashboard")
async def dashboard(request: Request, user: Optional[User] = Depends(current_active_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("dashboard.html", {"request": request})

@router.get("/company-dashboard")
async def company_dashboard(
    request: Request,
    company: Optional[Company] = Depends(current_active_company_optional),
    company_recruiter: Optional[CompanyRecruiter] = Depends(current_active_company_recruiter_optional),
):
    if company is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        "company-dashboard.html",
        {
            "request": request,
            "company_recruiter": company_recruiter,
        },
    )


@router.get("/company-candidates")
async def company_candidates_page(
    request: Request,
    company: Optional[Company] = Depends(current_active_company_optional),
    company_recruiter: Optional[CompanyRecruiter] = Depends(current_active_company_recruiter_optional),
):
    if company is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        "company-candidates.html",
        {
            "request": request,
            "company_recruiter": company_recruiter,
        },
    )


@router.get("/company-team")
async def company_team_page(
    request: Request,
    company: Optional[Company] = Depends(current_active_company_optional),
    company_recruiter: Optional[CompanyRecruiter] = Depends(current_active_company_recruiter_optional),
):
    if company is None or company_recruiter is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    if company_recruiter.role != "owner":
        return RedirectResponse(url="/company-dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        "company-team.html",
        {
            "request": request,
            "company_recruiter": company_recruiter,
        },
    )

@router.get("/questionnaire")
async def questionnaire(request: Request, user: Optional[User] = Depends(current_active_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("questionnaire.html", {"request": request})

@router.get("/user-profile")
async def user_profile(request: Request, user: Optional[User] = Depends(current_active_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("userProfile.html", {"request": request})


@router.get("/resources")
async def resources(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: Optional[User] = Depends(current_active_user_optional),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    service = ResourceService(session)
    resources = await service.list_published_resources()
    return templates.TemplateResponse(
        "resources.html",
        {
            "request": request,
            "resources": resources,
            "resource_detail_access_enabled": RESOURCE_DETAIL_ACCESS_ENABLED,
            "mandatory_course_titles": list(ResourceService.MANDATORY_RESOURCE_TITLES),
        },
    )


@router.get("/resources/{resource_id}")
async def resource_detail(
    request: Request,
    resource_id: UUID,
    lesson: str | None = None,
    session: AsyncSession = Depends(get_session),
    user: Optional[User] = Depends(current_active_user_optional),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    if not RESOURCE_DETAIL_ACCESS_ENABLED:
        return RedirectResponse(url="/resources?locked=1", status_code=status.HTTP_303_SEE_OTHER)

    service = ResourceService(session)
    resource = await service.get_published_resource(resource_id, include_locked=True)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    if resource.is_locked:
        return RedirectResponse(url="/resources?locked=1", status_code=status.HTTP_303_SEE_OTHER)

    completed_lesson_ids = await service.get_completed_lesson_ids_for_resource(
        resource_id=resource.id,
        user_id=user.id,
    )
    payload = service.to_detail_payload(resource, completed_lesson_ids=completed_lesson_ids)

    selected_lesson_id = lesson
    if not selected_lesson_id:
        for module in payload["modules"]:
            if module["lessons"]:
                selected_lesson_id = module["lessons"][0]["id"]
                break

    payload["selected_lesson_id"] = selected_lesson_id

    return templates.TemplateResponse(
        "resource_detail.html",
        {
            "request": request,
            "resource": resource,
            "resource_payload_json": json.dumps(payload),
            "selected_lesson_id": selected_lesson_id,
            "module_count": payload["module_count"],
            "lesson_count": payload["lesson_count"],
        },
    )


@router.get("/roadmap")
async def roadmap_redirect(request: Request, user: Optional[User] = Depends(current_active_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/roadmaps", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/roadmaps")
async def roadmaps_page(
    request: Request,
    search: str | None = Query(default=None),
    sort: str = Query(default="most_saved"),
    session: AsyncSession = Depends(get_session),
    current_user: Optional[User] = Depends(current_active_user_optional),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    service = RoadmapService(session)
    schema_not_ready = request.query_params.get("schema_not_ready") == "1"

    try:
        saved_roadmaps = await service.list_saved_roadmaps(user_id=current_user.id)
        roadmaps = await service.list_public_roadmaps(user_id=current_user.id, search=search, sort=sort)
    except ProgrammingError as exc:
        if not _is_missing_roadmap_tables_error(exc):
            raise
        saved_roadmaps = []
        roadmaps = []
        schema_not_ready = True

    return templates.TemplateResponse(
        "roadmaps_list.html",
        {
            "request": request,
            "saved_roadmaps": saved_roadmaps,
            "roadmaps": roadmaps,
            "search": search or "",
            "sort": sort,
            "schema_not_ready": schema_not_ready,
        },
    )


@router.get("/roadmaps/{slug}")
async def roadmap_detail_page(
    request: Request,
    slug: str,
    session: AsyncSession = Depends(get_session),
    current_user: Optional[User] = Depends(current_active_user_optional),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    service = RoadmapService(session)
    try:
        detail = await service.get_roadmap_detail(user_id=current_user.id, slug=slug)
    except ProgrammingError as exc:
        if _is_missing_roadmap_tables_error(exc):
            return RedirectResponse(
                url="/roadmaps?schema_not_ready=1",
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            )
        raise
    if not detail:
        raise HTTPException(status_code=404, detail="Roadmap not found")

    grouped_tasks = service.build_stage_grouped_tasks(detail)
    detail_items: dict[str, dict] = {}
    first_item_id: str | None = None

    for stage in detail.stages:
        for task in stage.tasks:
            key = str(task.id)
            detail_items[key] = {
                "kind": "task",
                "stage_title": stage.title,
                "title": task.title,
                "description": task.description,
                "estimated_hours": task.estimated_hours,
                "task_type": task.task_type.value,
                "resource_url": task.resource_url,
                "resource_title": task.resource_title,
            }
            if first_item_id is None:
                first_item_id = key

        for project in stage.projects:
            key = str(project.id)
            detail_items[key] = {
                "kind": "project",
                "stage_title": stage.title,
                "title": project.title,
                "description": project.brief,
                "estimated_hours": project.estimated_hours,
                "acceptance_criteria": project.acceptance_criteria,
                "rubric": project.rubric,
                "submission": project.submission.model_dump() if project.submission else None,
            }
            if first_item_id is None:
                first_item_id = key

    return templates.TemplateResponse(
        "roadmap_detail.html",
        {
            "request": request,
            "roadmap": detail,
            "grouped_tasks": grouped_tasks,
            "detail_items_json": json.dumps(detail_items, default=str),
            "first_item_id": first_item_id,
        },
    )


@router.get("/community")
async def community(request: Request, user: Optional[User] = Depends(current_active_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("community.html", {"request": request})


@router.get("/community/{community_id}")
async def community_feed(request: Request, community_id: str, user: Optional[User] = Depends(current_active_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("community_feed.html", {"request": request})


@router.get("/jobs")
async def jobs_board(request: Request, user: Optional[User] = Depends(current_active_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("jobs.html", {"request": request, "user": user})


@router.get("/admin/login")
async def admin_login_page(request: Request, user: Optional[User] = Depends(current_active_user_optional)):
    if user and user.is_superuser:
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("admin_login.html", {"request": request, "page_title": "Admin Login"})


@router.get("/admin")
async def admin_panel_page(request: Request, user: Optional[User] = Depends(current_active_user_optional)):
    if user is None or not user.is_superuser:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "page_title": "Admin Panel",
            "body_class": "admin-body",
        },
    )
