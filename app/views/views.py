from fastapi import APIRouter, Depends, HTTPException
from fastapi import Request
from fastapi.templating import Jinja2Templates
from app.db import get_session
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter()

templates = Jinja2Templates(directory="app/templates")

@router.get("/")
async def root(request: Request):
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
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@router.get("/questionnaire")
async def questionnaire(request: Request):
    return templates.TemplateResponse("questionnaire.html", {"request": request})

@router.get("/user-profile")
async def user_profile(request: Request):
    return templates.TemplateResponse("userProfile.html", {"request": request})


@router.get("/resources")
async def resources(request: Request):
    return templates.TemplateResponse("resources.html", {"request": request})


@router.get("/roadmap")
async def roadmap(request: Request):
    return templates.TemplateResponse("roadmap.html", {"request": request})


@router.get("/community")
async def community(request: Request):
    return templates.TemplateResponse("community.html", {"request": request})


@router.get("/jobs")
async def jobs_board(request: Request):
    return templates.TemplateResponse("jobs.html", {"request": request})