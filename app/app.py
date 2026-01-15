from fastapi import FastAPI, File, UploadFile, Form, Depends, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.db import create_db_and_tables, get_session
from app.models.postModel import PostModel
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from app.routes.postRoute import router as post_router
from app.models.userModel import User
from app.services.userService import fastapi_users, current_active_user, auth_backend
from app.schemas.userSchema import UserCreate, UserRead, UserUpdate
from app.views.views import router as views_router
from app.routes.questionnaireRoute import router as questionnaire_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(post_router, prefix="/api/v1")
app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/api/v1/auth", tags=["auth"])
app.include_router(fastapi_users.get_reset_password_router(), prefix="/api/v1/auth", tags=["auth"])
app.include_router(fastapi_users.get_verify_router(UserRead), prefix="/api/v1/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/api/v1/users", tags=["users"])
app.include_router(views_router, tags=["views"])
app.include_router(questionnaire_router, prefix="/api/v1", tags=["questionnaire"])
