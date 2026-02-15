from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env early so routes can read them
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=ROOT / ".env")

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.db import create_db_and_tables

from contextlib import asynccontextmanager
from app.routes.postRoute import router as post_router
from app.services.userService import fastapi_users, current_active_user, auth_backend
from app.schemas.userSchema import UserCreate, UserRead, UserUpdate
from app.views.views import router as views_router
from app.routes.questionnaireRoute import router as questionnaire_router
from app.routes.resumeRoute import router as resume_router
from app.routes.jobRoute import router as job_router
from app.routes.companyRoute import router as company_router
from app.routes.dashboardRoute import router as dashboard_router
from app.routes.communityRoute import router as community_router
from app.routes.resourceRoute import router as resource_router

# Import models to ensure they're registered with SQLAlchemy
from app.models.userModel import User
from app.models.companyModel import Company
from app.models.postModel import PostModel
from app.models.resumeModel import ResumeModel
from app.models.jobAnalysisModel import JobAnalysisModel
from app.models.questionnaireModel import UserQuestionnaire
from app.models.applicationModel import ApplicationModel
from app.models.jobPostingModel import JobPosting
from app.models.communityModel import CommunityModel, CommunityMemberModel
from app.models.communityPostModel import CommunityPostModel, CommunityPostLikeModel, CommunityPostCommentModel
from app.models.resourceModel import ResourceModel, ResourceModuleModel, ResourceLessonModel


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Avoid running Base.metadata.create_all on startup in production.
    # Controlled via ENV/AUTO_CREATE_TABLES in app/db.py
    await create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, cambia esto a tu dominio específico
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(post_router, prefix="/api/v1")
app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/api/v1/auth", tags=["auth"])
app.include_router(fastapi_users.get_reset_password_router(), prefix="/api/v1/auth", tags=["auth"])
app.include_router(fastapi_users.get_verify_router(UserRead), prefix="/api/v1/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/api/v1/users", tags=["users"])
app.include_router(company_router, prefix="/api/v1", tags=["companies"])
app.include_router(views_router, tags=["views"])
app.include_router(questionnaire_router, prefix="/api/v1", tags=["questionnaire"])
app.include_router(resume_router, prefix="/api/v1", tags=["resume"])
app.include_router(job_router, prefix="/api/v1", tags=["jobs"])
app.include_router(dashboard_router, prefix="/api/v1", tags=["dashboard"])
app.include_router(community_router, prefix="/api/v1", tags=["communities"])
app.include_router(resource_router, prefix="/api/v1", tags=["resources"])