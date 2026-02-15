import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from app.db import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.userService import current_active_user_optional
from app.services.resourceService import ResourceService
from app.models.userModel import User
from typing import Optional


router = APIRouter()

templates = Jinja2Templates(directory="app/templates")

@router.get("/")
async def root(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@router.get("/home")
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


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
async def company_dashboard(request: Request, user: Optional[User] = Depends(current_active_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("company-dashboard.html", {"request": request})

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
    return templates.TemplateResponse("resources.html", {"request": request, "resources": resources})


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

    service = ResourceService(session)
    resource = await service.get_resource_with_outline(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    payload = service.to_detail_payload(resource)

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
async def roadmap(request: Request, user: Optional[User] = Depends(current_active_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("roadmap.html", {"request": request})


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
    return templates.TemplateResponse("jobs.html", {"request": request})