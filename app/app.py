from dataclasses import dataclass
from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path
from urllib.parse import urljoin
from xml.etree.ElementTree import Element, SubElement, tostring, register_namespace

# Load environment variables from .env early so routes can read them
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=ROOT / ".env")

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.db import create_db_and_tables
from app.template_utils import configure_template_helpers
import os

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
from app.routes.friendshipRoute import router as friendship_router
from app.routes.profileRoute import router as profile_router
from app.routes.messageRoute import router as message_router
from app.routes.resourceRoute import router as resource_router
from app.routes.roadmapRoute import router as roadmap_router
from app.routes.adminRoute import router as admin_router
from app.services.roadmapSeedService import seed_roadmaps_on_startup_if_dev
from app.middleware.rate_limit import RequestRateLimiter
from fastapi import Response
from fastapi.responses import FileResponse


SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"
register_namespace("", SITEMAP_NAMESPACE)


@dataclass(frozen=True)
class SitemapEntry:
    path: str
    priority: str
    changefreq: str
    source_file: Path | None = None


_PUBLIC_SITEMAP_ENTRIES: tuple[SitemapEntry, ...] = (
    SitemapEntry(path="/", priority="1.0", changefreq="weekly", source_file=ROOT / "app/templates/home.html"),
    SitemapEntry(path="/about", priority="0.8", changefreq="monthly", source_file=ROOT / "app/templates/about.html"),
    SitemapEntry(path="/login", priority="0.6", changefreq="monthly", source_file=ROOT / "app/templates/login.html"),
    SitemapEntry(path="/register", priority="0.7", changefreq="monthly", source_file=ROOT / "app/templates/register.html"),
)


def _get_public_base_url() -> str:
    configured = (
        os.getenv("PUBLIC_BASE_URL")
        or os.getenv("APP_BASE_URL")
        or os.getenv("SITE_URL")
        or "https://studentscompass.ca"
    ).strip()
    return configured.rstrip("/")


def _build_public_url(path: str) -> str:
    base_url = _get_public_base_url()
    relative_path = path.lstrip("/")
    if not relative_path:
        return f"{base_url}/"
    return urljoin(f"{base_url}/", relative_path)


def _get_last_modified_date(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return modified_at.date().isoformat()


def _build_sitemap_xml() -> bytes:
    urlset = Element(f"{{{SITEMAP_NAMESPACE}}}urlset")

    for entry in _PUBLIC_SITEMAP_ENTRIES:
        url_node = SubElement(urlset, f"{{{SITEMAP_NAMESPACE}}}url")
        SubElement(url_node, f"{{{SITEMAP_NAMESPACE}}}loc").text = _build_public_url(entry.path)
        last_modified = _get_last_modified_date(entry.source_file)
        if last_modified:
            SubElement(url_node, f"{{{SITEMAP_NAMESPACE}}}lastmod").text = last_modified
        SubElement(url_node, f"{{{SITEMAP_NAMESPACE}}}changefreq").text = entry.changefreq
        SubElement(url_node, f"{{{SITEMAP_NAMESPACE}}}priority").text = entry.priority

    return tostring(urlset, encoding="utf-8", xml_declaration=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Avoid running Base.metadata.create_all on startup in production.
    # Controlled via ENV/AUTO_CREATE_TABLES in app/db.py
    await create_db_and_tables()
    await seed_roadmaps_on_startup_if_dev()
    yield


app = FastAPI(lifespan=lifespan)
rate_limiter = RequestRateLimiter.from_env()

# Configure CORS origins from environment.
def _load_cors_origins() -> list[str]:
    configured = os.getenv("CORS_ORIGINS", "")
    if configured.strip():
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://studentscompass.ca",
        "https://www.studentscompass.ca",
    ]


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=_load_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def apply_rate_limits(request, call_next):
    allowed, retry_after = rate_limiter.check(request)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."},
            headers={"Retry-After": str(retry_after)},
        )
    return await call_next(request)


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap():
    return Response(content=_build_sitemap_xml(), media_type="application/xml")

@app.get("/robots.txt", include_in_schema=False)
async def robots():
    public_base_url = _get_public_base_url()
    return Response(
        content=f"User-agent: *\nAllow: /\nSitemap: {public_base_url}/sitemap.xml",
        media_type="text/plain"
    )

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("app/static/images/favicon.ico", media_type="image/x-icon")


app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = configure_template_helpers(Jinja2Templates(directory="app/templates"))

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
app.include_router(friendship_router, prefix="/api/v1", tags=["friendships"])
app.include_router(message_router, prefix="/api/v1", tags=["messages"])
app.include_router(profile_router, prefix="/api/v1", tags=["profile"])
app.include_router(resource_router, prefix="/api/v1", tags=["resources"])
app.include_router(roadmap_router, prefix="/api/v1", tags=["roadmaps"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])
