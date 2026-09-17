from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env early so routes can read them
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=ROOT / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.db import create_db_and_tables
import os

from contextlib import asynccontextmanager
from app.routes.postRoute import router as post_router
from app.services.accounts.userService import fastapi_users, auth_backend
from app.middleware.csrf import CSRFMiddleware
from app.core.error_handlers import install_error_handlers
from app.core.openapi import (
    assert_unique_operation_ids,
    document_error_contract,
    stable_operation_id,
)
from app.middleware.request_context import RequestContextMiddleware
from app.routes.authRoute import router as auth_router
from app.schemas.userSchema import UserCreate, UserRead, UserUpdate
from app.routes.questionnaireRoute import router as questionnaire_router
from app.routes.resumeRoute import legacy_router as resume_legacy_router, router as resume_router
from app.routes.jobRoute import legacy_router as job_legacy_router, router as job_router
from app.routes.companyRoute import router as company_router
from app.routes.dashboardRoute import legacy_router as dashboard_legacy_router, router as dashboard_router
from app.routes.communityRoute import legacy_router as community_legacy_router, router as community_router
from app.routes.friendshipRoute import legacy_router as friendship_legacy_router, router as friendship_router
from app.routes.profileRoute import router as profile_router
from app.routes.messageRoute import router as message_router
from app.routes.resourceRoute import router as resource_router
from app.routes.roadmapRoute import legacy_router as roadmap_legacy_router, router as roadmap_router
from app.routes.adminRoute import router as admin_router
import logging

from app.routes.capstoneAnalyticsRoute import router as capstone_analytics_router
from app.routes.internalTasksRoute import router as internal_tasks_router
from app.routes.healthRoute import router as health_router
from app.core.resume_analyzer.resume_text_extractor import shutdown_resume_text_extractors
from app.services.ai.cvAnalysisRunner import start_runner, stop_runner
from app.services.roadmaps.roadmapSeedService import seed_roadmaps_on_startup_if_dev
from app.config import (
    CV_ANALYSIS_INLINE_RUNNER,
    MAX_POST_UPLOAD_BYTES,
    MAX_REQUEST_BODY_BYTES,
    MAX_UPLOAD_BYTES,
)
from app.middleware.body_size import (
    MULTIPART_OVERHEAD_BYTES,
    RequestBodySizeLimitMiddleware,
)
from app.middleware.rate_limit import RequestRateLimiter


LOGGER_APP = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Avoid running Base.metadata.create_all on startup in production.
    # Controlled via ENV/AUTO_CREATE_TABLES in app/db.py
    await create_db_and_tables()
    await seed_roadmaps_on_startup_if_dev()
    # No CV-analysis polling loop here any more (TASK-054, plan 08 §6.3).
    #
    # A loop inside the web process is wrong in both directions on Cloud Run: a
    # replica scaled to zero runs no loop, so queued analyses simply do not
    # happen, and N replicas run N loops competing for the same rows. The
    # durable path is now the outbox plus a task queue calling
    # /internal/tasks/cv-analyses/{id}, and the local worker consumes the same
    # outbox.
    #
    # CV_ANALYSIS_INLINE_RUNNER re-enables the loop for a single-process
    # deployment with no queue in front of it. It is off by default so the safe
    # topology is the one you get without deciding anything.
    if CV_ANALYSIS_INLINE_RUNNER:
        LOGGER_APP.info("CV_ANALYSIS_INLINE_RUNNER is on: starting the in-process runner")
        await start_runner()
    try:
        yield
    finally:
        if CV_ANALYSIS_INLINE_RUNNER:
            await stop_runner()
        shutdown_resume_text_extractors()


# Hide interactive API docs / schema in production to avoid exposing the full
# endpoint map. Still available in dev for convenience.
from app.config import IS_PRODUCTION

app = FastAPI(
    lifespan=lifespan,
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
    # TASK-043: el `operationId` es el nombre del tipo TypeScript generado, no
    # un detalle interno del documento. Ver app/core/openapi.py.
    generate_unique_id_function=stable_operation_id,
)
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


ALLOWED_ORIGINS = _load_cors_origins()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The origin list is shared with CORS so the two cannot disagree about what "our
# frontend" means. They are not redundant: CORS is a browser-side courtesy that
# only governs what script may *read* back, while this refuses the write.
app.add_middleware(
    CSRFMiddleware,
    allowed_origins=ALLOWED_ORIGINS,
    # Logging in or out changes which identity the cookie carries, so the token
    # bound to the previous one must not survive it.
    rotate_paths=("/login", "/logout"),
)

# Added last so it wraps everything else: the body has to be bounded before the
# multipart parser spools it, not after a route handler gets a chance to look.
# The per-route budgets carry multipart slack on top of the file budget, so the
# route's own check is the one that decides the exact boundary.
# Outermost of the three: it has to see the request before anything can reject
# it, so a 413 or a CSRF refusal is logged with the same id as a 200.
app.add_middleware(RequestContextMiddleware)

# Registered after the middleware that mints the request id, because every
# envelope these handlers write quotes it. Scoped to /api/v1 inside, which since
# TASK-059 is the whole application: the Jinja views that kept the framework's
# HTML error pages are gone.
install_error_handlers(app)

app.add_middleware(
    RequestBodySizeLimitMiddleware,
    default_max_bytes=MAX_REQUEST_BODY_BYTES,
    budgets={
        "/api/v1/profile/cv/": MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES,
        "/api/v1/upload_post": MAX_POST_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES,
    },
)


@app.middleware("http")
async def apply_rate_limits(request, call_next):
    allowed, retry_after = await rate_limiter.check(request)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."},
            headers={"Retry-After": str(retry_after)},
        )
    return await call_next(request)


app.include_router(post_router, prefix="/api/v1", tags=["posts"])
# Two mounts of the same router, on purpose. ``/api/v1/auth/student`` is the
# contract: it matches ``/api/v1/auth/company`` so a client addresses either
# actor the same way. ``/auth/jwt`` is the path the Jinja pages called, and it
# outlives them on purpose (TASK-059, runbook §4 B4): the ficha may only retire
# an endpoint against measured zero traffic, and the window that measures it
# opened with the cutover on 2026-09-17. Dropping the mount now would zero its
# counter *by construction* — "nobody can call it" is not "nobody calls it" —
# and the last pre-cutover sample still had 10 real POSTs to it. It comes out
# when the window says it may, together with its proxy entry in nginx.conf.
app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/api/v1/auth/student", tags=["auth"])
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
    include_in_schema=False,
)
app.include_router(auth_router, prefix="/api/v1", tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/api/v1/auth", tags=["auth"])
app.include_router(fastapi_users.get_reset_password_router(), prefix="/api/v1/auth", tags=["auth"])
app.include_router(fastapi_users.get_verify_router(UserRead), prefix="/api/v1/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/api/v1/users", tags=["users"])
app.include_router(company_router, prefix="/api/v1", tags=["companies"])
app.include_router(questionnaire_router, prefix="/api/v1", tags=["questionnaire"])
app.include_router(resume_router, prefix="/api/v1", tags=["resume"])
app.include_router(resume_legacy_router, prefix="/api/v1", tags=["resume"])
app.include_router(job_router, prefix="/api/v1", tags=["jobs"])
app.include_router(job_legacy_router, prefix="/api/v1", tags=["jobs"])
app.include_router(dashboard_router, prefix="/api/v1", tags=["dashboard"])
app.include_router(dashboard_legacy_router, prefix="/api/v1", tags=["dashboard"])
app.include_router(community_router, prefix="/api/v1", tags=["communities"])
app.include_router(community_legacy_router, prefix="/api/v1", tags=["communities"])
app.include_router(friendship_router, prefix="/api/v1", tags=["friendships"])
app.include_router(friendship_legacy_router, prefix="/api/v1", tags=["friendships"])
app.include_router(message_router, prefix="/api/v1", tags=["messages"])
app.include_router(profile_router, prefix="/api/v1", tags=["profile"])
app.include_router(resource_router, prefix="/api/v1", tags=["resources"])
app.include_router(roadmap_router, prefix="/api/v1", tags=["roadmaps"])
app.include_router(roadmap_legacy_router, prefix="/api/v1", tags=["roadmaps"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(capstone_analytics_router, prefix="/api/v1", tags=["capstone"])
# Deliberately *not* under /api/v1: these are not part of the public contract
# and are reachable only with a task credential (app/core/internalAuth.py).
app.include_router(internal_tasks_router, tags=["internal"])
# Same reasoning, different reader: /healthz and /readyz are addressed by Cloud
# Run, not by a client, so they stay off the contract (TASK-045).
app.include_router(health_router, tags=["health"])

# Se comprueba al montar, no al exportar: una colisión de `operationId` haría que
# dos operaciones compartieran tipo generado, y eso tiene que fallar en el
# arranque de quien la introduce, no dos jobs más tarde.
assert_unique_operation_ids(app)
# Después de montar todos los routers: envuelve `app.openapi()` y añade a cada
# operación de `/api/v1` la respuesta de error de TASK-040 (plan 08 §5.1).
document_error_contract(app)
