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

@router.get("/api/v1/auth/register")
async def register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.get("/dashboard")
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})