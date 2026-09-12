"""Baseline de paridad: OpenAPI, fixtures JSON y capturas de las pantallas.

Origen: TASK-035 del tablero de refactor (docs/refactor/TASKS.md). El plan 08 §9
exige «paridad funcional y visual» por vertical y §13 pide comparación visual de
cada pantalla migrada; sin baseline archivada, «se ve igual» es una opinión.

El script no toca `app/`. Levanta la aplicación real contra una base SQLite
desechable sembrada con datos sintéticos y archiva lo que produce:

    docs/refactor/baseline/openapi.json        schema OpenAPI actual
    docs/refactor/baseline/fixtures/<actor>/   payload real por endpoint GET
    docs/refactor/baseline/screens/            capturas desktop y mobile
    docs/refactor/baseline/manifest.json       qué se capturó, con sha256
    docs/refactor/baseline/MANIFEST.md         lo mismo, legible, por vertical

Corre con el mismo aislamiento que la suite (`tests/isolation.py`): no se lee
`.env`, cada credencial tiene un valor falso explícito y las conexiones fuera de
loopback están bloqueadas. Ningún dato de producción puede entrar en el
artefacto porque el proceso no puede alcanzar producción.

Uso:

    cd backend && ../.venv/bin/python scripts/capture_baseline.py
    cd backend && ../.venv/bin/python scripts/capture_baseline.py --skip-screens

Las capturas necesitan Playwright con Chromium:

    cd backend && ../.venv/bin/python -m playwright install chromium
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# Dos raíces desde TASK-037: el código Python vive bajo `backend/` y la baseline
# se archiva en `docs/` en la raíz del repositorio, que es de todo el monorepo.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

# El aislamiento debe correr antes de importar cualquier módulo de `app`: app.db
# y app.app llaman load_dotenv() y construyen el engine en tiempo de import.
from tests.isolation import allow_test_service, apply_isolation  # noqa: E402

apply_isolation()

# La base de la baseline es un fichero SQLite, no `:memory:`: el servidor de las
# capturas corre en otro hilo con su propio event loop, y una única conexión
# aiosqlite compartida entre loops no es segura. Un fichero permite que cada
# loop abra las suyas y vea los mismos datos.
_TMP_DIR = Path(tempfile.mkdtemp(prefix="baseline-"))
_DB_PATH = _TMP_DIR / "baseline.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB_PATH}"

from sqlalchemy import event, select  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

import app.db as app_db  # noqa: E402
from app.db import Base, get_session  # noqa: E402

BASELINE_DIR = REPO_ROOT / "docs" / "refactor" / "baseline"
INVENTORY_PATH = REPO_ROOT / "docs" / "refactor" / "route_inventory.json"

# Reloj y namespace fijos: los ids y las fechas del artefacto son función del
# código, no del momento en que se ejecuta. Sin esto, «reejecutar y comparar»
# no distingue un cambio de comportamiento de un cambio de hora.
FIXED_NOW = datetime(2026, 1, 5, 12, 0, 0)
NAMESPACE = uuid.UUID("6f1f5a2e-0f7f-4c2b-9a5b-2f0f0a5f3c11")

# Contraseñas sintéticas. Son de esta base desechable y de nada más; aparecen
# aquí y no en los artefactos, que se revisan para que no las contengan.
STUDENT_PASSWORD = "baseline-student-pw"
ADMIN_PASSWORD = "baseline-admin-pw"
RECRUITER_PASSWORD = "baseline-recruiter-pw"

STUDENT_EMAIL = "baseline-student@example.com"
FRIEND_EMAIL = "baseline-friend@example.com"
ADMIN_EMAIL = "baseline-admin@example.com"
RECRUITER_EMAIL = "baseline-recruiter@example.com"


def sid(name: str) -> uuid.UUID:
    """Id estable derivada del nombre lógico de la fila sembrada.

    Se le fuerzan los bits de versión 4 porque varios schemas de respuesta
    declaran `UUID4`: con un uuid5 puro la fixture mediría la semilla, no el
    endpoint. Sigue siendo función determinista del nombre.
    """
    raw = bytearray(uuid.uuid5(NAMESPACE, name).bytes)
    raw[6] = (raw[6] & 0x0F) | 0x40
    raw[8] = (raw[8] & 0x3F) | 0x80
    return uuid.UUID(bytes=bytes(raw))


IDS = {
    name: sid(name)
    for name in (
        "student", "friend", "admin", "company", "recruiter", "job", "application",
        "resume", "questionnaire", "community", "community_post",
        "community_comment", "resource", "resource_module", "resource_lesson",
        "roadmap", "roadmap_stage", "stage_task", "stage_project", "post",
        "conversation", "message", "friendship", "friend_request", "stats",
        "enrollment", "lesson_progress", "user_roadmap",
    )
}
ROADMAP_SLUG = "baseline-backend-engineer"


# --- Base de datos ---------------------------------------------------------


def build_engine():
    engine = create_async_engine(
        os.environ["DATABASE_URL"],
        poolclass=NullPool,
        future=True,
    )

    # Mismas funciones que registra tests/conftest.py: hay SQL que las usa y
    # SQLite no las trae.
    @event.listens_for(engine.sync_engine, "connect")
    def _register_sqlite_functions(dbapi_connection, connection_record):  # noqa: ANN001
        dbapi_connection.create_function("btrim", 1, lambda value: (value or "").strip())
        dbapi_connection.create_function("char_length", 1, lambda value: len(value or ""))

    return engine


ENGINE = build_engine()
SessionLocal = async_sessionmaker(ENGINE, class_=AsyncSession, expire_on_commit=False)

# `app.db.get_session` resuelve `async_session` en tiempo de llamada, así que
# reapuntar el atributo del módulo basta para el runner de CV, que lo importa
# tarde. El override de dependencia lo deja explícito para las rutas.
app_db.engine = ENGINE
app_db.async_session = SessionLocal

from app.app import app  # noqa: E402
from app.models.registry import import_all_models  # noqa: E402


async def override_get_session():
    async with SessionLocal() as session:
        yield session


app.dependency_overrides[get_session] = override_get_session


async def create_schema() -> None:
    import_all_models()
    async with ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# --- Semilla sintética -----------------------------------------------------


async def seed() -> None:
    """Una fila por cada forma que alguna pantalla necesita mostrar.

    Datos inventados de principio a fin: dominios `.invalid`, nombres genéricos
    y ninguna referencia a personas, empresas o ficheros reales.
    """
    from fastapi_users.password import PasswordHelper

    from app.models.applicationModel import (
        ApplicationMatchStrength,
        ApplicationModel,
        ApplicationStatus,
    )
    from app.models.communityModel import CommunityMemberModel, CommunityModel
    from app.models.communityPostModel import (
        CommunityPostCommentModel,
        CommunityPostLikeModel,
        CommunityPostModel,
    )
    from app.models.companyModel import Company
    from app.models.companyRecruiterModel import CompanyRecruiter
    from app.models.friendshipModel import FriendRequestModel, FriendshipModel
    from app.models.jobPostingModel import JobPosting
    from app.models.messageModel import (
        ConversationModel,
        ConversationParticipantModel,
        MessageModel,
    )
    from app.models.postModel import PostModel
    from app.models.questionnaireModel import UserQuestionnaire
    from app.models.resourceModel import (
        ResourceEnrollmentModel,
        ResourceLessonModel,
        ResourceLessonProgressModel,
        ResourceModel,
        ResourceModuleModel,
    )
    from app.models.resumeModel import ResumeModel
    from app.models.roadmapModel import (
        RoadmapModel,
        RoadmapStageModel,
        StageProjectModel,
        StageTaskModel,
        TaskType,
        UserRoadmapModel,
    )
    from app.models.userModel import User
    from app.models.userStatsModel import UserStatsModel

    helper = PasswordHelper()
    now = FIXED_NOW
    rows: list[Any] = []

    def account(model, key, email, password, **extra):
        return model(
            id=IDS[key],
            email=email,
            hashed_password=helper.hash(password),
            is_active=True,
            is_verified=True,
            created_at=now,
            updated_at=now,
            **extra,
        )

    rows += [
        account(
            User, "student", STUDENT_EMAIL, STUDENT_PASSWORD,
            is_superuser=False, nickname="baseline_student",
            first_name="Baseline", last_name="Student",
        ),
        account(
            User, "friend", FRIEND_EMAIL, STUDENT_PASSWORD,
            is_superuser=False, nickname="baseline_friend",
            first_name="Baseline", last_name="Friend",
        ),
        account(
            User, "admin", ADMIN_EMAIL, ADMIN_PASSWORD,
            is_superuser=True, nickname="baseline_admin",
            first_name="Baseline", last_name="Admin",
        ),
        Company(
            id=IDS["company"], company_name="Baseline Company",
            industry="Technology", description="Empresa sintética de la baseline.",
            website="https://company.invalid", location="Remote",
            contact_person="Baseline Recruiter", phone="+1 555 0100",
            created_at=now, updated_at=now,
        ),
    ]
    rows.append(
        account(
            CompanyRecruiter, "recruiter", RECRUITER_EMAIL, RECRUITER_PASSWORD,
            is_superuser=False, company_id=IDS["company"],
            first_name="Baseline", last_name="Recruiter", role="owner",
        )
    )

    rows += [
        UserStatsModel(
            id=IDS["stats"], user_id=IDS["student"], resume_progress=60,
            linkedin_progress=40, interview_progress=20,
            created_at=now, updated_at=now,
        ),
        JobPosting(
            id=IDS["job"], company_id=IDS["company"],
            title="Backend Engineer (Baseline)",
            description="Puesto sintético para la baseline visual.",
            requirements="Python, FastAPI, PostgreSQL",
            responsibilities="Construir y mantener servicios de la plataforma.",
            location="Remote", job_type="full-time", workplace_type="remote",
            seniority_level="junior", salary_range="CAD 60k-80k",
            benefits="Sintéticos", is_active=True,
            created_at=now, updated_at=now,
        ),
        ResumeModel(
            id=IDS["resume"], user_id=IDS["student"],
            view_url="https://storage.invalid/baseline/resume.pdf",
            storage_file_id="baseline-resume-object",
            original_filename="baseline-resume.pdf",
            folder_id="baseline-folder",
            ai_summary="Resumen sintético: perfil junior de backend.",
            created_at=now, updated_at=now,
        ),
        ApplicationModel(
            id=IDS["application"], user_id=IDS["student"],
            company_id=IDS["company"], assigned_recruiter_id=IDS["recruiter"],
            job_posting_id=IDS["job"], resume_id=IDS["resume"],
            job_title="Backend Engineer (Baseline)",
            status=ApplicationStatus.APPLIED,
            match_strength=ApplicationMatchStrength.MATCH,
            application_date=now, notes="Candidatura sintética.",
            created_at=now, updated_at=now,
        ),
        UserQuestionnaire(
            id=IDS["questionnaire"], user_id=IDS["student"], version="v1",
            answers={"goal": "backend", "experience": "junior"},
            results={"recommended_role": "Backend Engineer", "score": 72},
            created_at=now, updated_at=now,
        ),
        PostModel(
            id=IDS["post"], user_id=IDS["student"],
            caption="Publicación sintética de la baseline",
            url="https://storage.invalid/baseline/post.png",
            file_type="image/png", file_name="baseline-post.png",
            created_at=now, updated_at=now,
        ),
        CommunityModel(
            id=IDS["community"], name="Baseline Community",
            description="Comunidad sintética de la baseline.",
            icon="🧭", activity_status="active", tags=["baseline", "backend"],
            member_count_cache=2, created_by=IDS["student"],
            created_at=now, updated_at=now,
        ),
    ]
    rows += [
        CommunityMemberModel(
            id=sid("member-student"), community_id=IDS["community"],
            user_id=IDS["student"], joined_at=now, updated_at=now,
        ),
        CommunityMemberModel(
            id=sid("member-friend"), community_id=IDS["community"],
            user_id=IDS["friend"], joined_at=now, updated_at=now,
        ),
        CommunityPostModel(
            id=IDS["community_post"], community_id=IDS["community"],
            user_id=IDS["student"], title="Hilo sintético",
            content="Contenido sintético del hilo de la baseline.",
            post_type="discussion", created_at=now, updated_at=now,
        ),
        CommunityPostCommentModel(
            id=IDS["community_comment"], post_id=IDS["community_post"],
            user_id=IDS["friend"], content="Comentario sintético.",
            created_at=now, updated_at=now,
        ),
        CommunityPostLikeModel(
            id=sid("community_like"), post_id=IDS["community_post"],
            user_id=IDS["friend"], created_at=now, updated_at=now,
        ),
        FriendshipModel(
            id=IDS["friendship"], user_id=IDS["student"],
            friend_id=IDS["friend"], created_at=now,
        ),
        FriendshipModel(
            id=sid("friendship-reverse"), user_id=IDS["friend"],
            friend_id=IDS["student"], created_at=now,
        ),
        FriendRequestModel(
            id=IDS["friend_request"], sender_id=IDS["friend"],
            receiver_id=IDS["student"], status="pending",
            created_at=now, updated_at=now,
        ),
    ]

    direct_key = ":".join(sorted([str(IDS["student"]), str(IDS["friend"])]))
    rows += [
        ConversationModel(
            id=IDS["conversation"], kind="direct", direct_key=direct_key,
            created_at=now, updated_at=now, last_message_at=now,
        ),
        ConversationParticipantModel(
            id=sid("participant-student"), conversation_id=IDS["conversation"],
            user_id=IDS["student"], joined_at=now, last_read_at=now,
        ),
        ConversationParticipantModel(
            id=sid("participant-friend"), conversation_id=IDS["conversation"],
            user_id=IDS["friend"], joined_at=now, last_read_at=now,
        ),
        MessageModel(
            id=IDS["message"], conversation_id=IDS["conversation"],
            sender_id=IDS["friend"], content="Mensaje sintético.",
            created_at=now, updated_at=now,
        ),
    ]

    rows += [
        ResourceModel(
            id=IDS["resource"], title="Baseline Course",
            description="Curso sintético usado por la baseline visual.",
            icon="📘", category="career", tags=["baseline"], level="beginner",
            estimated_duration_minutes=45, is_published=True, is_locked=False,
            created_at=now, updated_at=now,
        ),
        ResourceModuleModel(
            id=IDS["resource_module"], resource_id=IDS["resource"],
            title="Módulo 1", position=1, description="Módulo sintético.",
            created_at=now, updated_at=now,
        ),
        ResourceLessonModel(
            id=IDS["resource_lesson"], module_id=IDS["resource_module"],
            title="Lección 1", position=1, content_type="text",
            content="Contenido sintético de la lección.",
            reading_time_minutes=5, created_at=now, updated_at=now,
        ),
        ResourceEnrollmentModel(
            id=IDS["enrollment"], user_id=IDS["student"],
            resource_id=IDS["resource"],
            last_opened_lesson_id=IDS["resource_lesson"],
            enrolled_at=now, updated_at=now,
        ),
        ResourceLessonProgressModel(
            id=IDS["lesson_progress"], user_id=IDS["student"],
            resource_id=IDS["resource"], lesson_id=IDS["resource_lesson"],
            completed_at=now, last_opened_at=now,
            created_at=now, updated_at=now,
        ),
        RoadmapModel(
            id=IDS["roadmap"], slug=ROADMAP_SLUG, title="Backend Engineer (Baseline)",
            description="Roadmap sintético de la baseline.",
            role_target="Backend Engineer", difficulty="beginner",
            duration_weeks_min=8, duration_weeks_max=12, is_public=True,
            created_at=now,
        ),
        RoadmapStageModel(
            id=IDS["roadmap_stage"], roadmap_id=IDS["roadmap"], order_index=1,
            title="Fundamentos", objective="Objetivo sintético de la etapa.",
            duration_weeks=4, created_at=now,
        ),
        StageTaskModel(
            id=IDS["stage_task"], stage_id=IDS["roadmap_stage"], order_index=1,
            title="Tarea sintética", description="Descripción sintética.",
            estimated_hours=6, task_type=TaskType.READ,
            resource_url="https://docs.invalid/baseline",
            resource_title="Documentación sintética",
        ),
        StageProjectModel(
            id=IDS["stage_project"], stage_id=IDS["roadmap_stage"],
            title="Proyecto sintético", brief="Brief sintético del proyecto.",
            acceptance_criteria=["Criterio A", "Criterio B"],
            rubric={"calidad": 5, "alcance": 5}, estimated_hours=10,
        ),
        UserRoadmapModel(
            id=IDS["user_roadmap"], user_id=IDS["student"],
            roadmap_id=IDS["roadmap"], saved_at=now,
        ),
    ]

    async with SessionLocal() as session:
        session.add_all(rows)
        await session.commit()

    # Comprobación de que la semilla es la que se cree: si un modelo cambia y
    # una fila deja de insertarse, el artefacto saldría vacío en silencio.
    async with SessionLocal() as session:
        found = (await session.execute(select(User).where(User.id == IDS["student"]))).scalar_one()
        assert found.email == STUDENT_EMAIL


# --- OpenAPI ---------------------------------------------------------------


def export_openapi(out_dir: Path) -> Path:
    schema = app.openapi()
    path = out_dir / "openapi.json"
    path.write_text(json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    return path


# --- Fixtures --------------------------------------------------------------

# Valores concretos para los parámetros de ruta y de query que los endpoints GET
# exigen. Lo que no está aquí se salta con una razón registrada, en vez de
# capturarse contra un id inventado que devolvería 404 y no diría nada.
def path_params() -> dict[str, dict[str, str]]:
    return {
        "resource_id": {"value": str(IDS["resource"])},
        "user_id": {"value": str(IDS["student"])},
        "resume_id": {"value": str(IDS["resume"])},
        "community_id": {"value": str(IDS["community"])},
        "post_id": {"value": str(IDS["community_post"])},
        "application_id": {"value": str(IDS["application"])},
        "conversation_id": {"value": str(IDS["conversation"])},
        "job_id": {"value": str(IDS["job"])},
        "slug": {"value": ROADMAP_SLUG},
        "id": {"value": str(IDS["student"])},
    }


# `/api/v1/posts/{post_id}` es el post de perfil (PostModel), no el de comunidad.
PATH_OVERRIDES = {
    "/api/v1/posts/{post_id}": {"post_id": "post"},
}

QUERY_PARAMS = {
    "/api/v1/friends/status": {"user_ids": lambda: str(IDS["friend"])},
    "/api/v1/resources/file": {"key": lambda: "baseline-resource-object"},
    "/api/v1/capstone/gap-analysis": {
        "resume_id": lambda: str(IDS["resume"]),
        "target_role": lambda: "Backend Engineer",
    },
}

# Endpoints GET que no describen ninguna pantalla y cuya captura no aporta a la
# paridad: assets estáticos y documentos generados que ya tienen su propio test.
FIXTURE_SKIP = {
    "/favicon.ico": "asset binario servido por FileResponse; no hay payload que comparar",
    "/robots.txt": "texto plano estático",
    "/sitemap.xml": "XML cubierto por tests/test_sitemap.py",
    # Estos dos bajan el fichero desde object storage. Bajo aislamiento la
    # salida está bloqueada, así que lo que se archivaría es el fallo del
    # entorno, no el contrato del endpoint. Su paridad se demuestra en TASK-050
    # contra un storage de prueba, no aquí.
    "/api/v1/companies/me/applications/{application_id}/resume/download": (
        "descarga desde object storage; el aislamiento bloquea la salida y la "
        "respuesta describiría el entorno, no el endpoint"
    ),
    "/api/v1/companies/me/applications/{application_id}/resume/preview": (
        "previsualización desde object storage; misma razón que /resume/download"
    ),
    # El propio handler lo declara: necesita PostgreSQL con la extensión
    # `vector`. Sobre SQLite el operador `<=>` es un error de sintaxis, así que
    # aquí no hay contrato que archivar, solo el límite del motor.
    "/api/v1/profile/cv/{resume_id}/similar": (
        "usa el operador pgvector `<=>`; la baseline corre sobre SQLite y el "
        "endpoint declara que exige PostgreSQL con la extensión vector"
    ),
}

ACTOR_CLIENTS = {
    "public": None,
    "student": "student",
    "student:optional": "student",
    "admin": "admin",
    "recruiter": "recruiter",
    "recruiter:owner": "recruiter",
    "recruiter:job_manager": "recruiter",
    "recruiter:optional": "recruiter",
    "company": "recruiter",
    "company:optional": "recruiter",
}


def load_inventory() -> list[dict[str, Any]]:
    data = json.loads(INVENTORY_PATH.read_text())
    return data["handlers"]


def fixture_slug(path: str) -> str:
    slug = path.strip("/").replace("api/v1/", "")
    slug = re.sub(r"[{}]", "", slug)
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", slug).strip("_")
    return slug or "root"


def fill_path(path: str, params: dict[str, dict[str, str]]) -> tuple[str | None, str | None]:
    """Sustituye `{param}` por su valor sembrado; None si falta alguno."""
    missing: list[str] = []
    overrides = PATH_OVERRIDES.get(path, {})

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in overrides:
            return str(IDS[overrides[name]])
        entry = params.get(name)
        if entry is None:
            missing.append(name)
            return match.group(0)
        return entry["value"]

    filled = re.sub(r"\{([^}]+)\}", replace, path)
    if missing:
        return None, f"sin valor sembrado para el parámetro {', '.join(missing)}"
    return filled, None


async def capture_fixtures(out_dir: Path) -> list[dict[str, Any]]:
    from httpx import ASGITransport, AsyncClient

    from app.services.ratelimit.counterStore import reset_counter_store

    await reset_counter_store()

    handlers = load_inventory()
    params = path_params()
    results: list[dict[str, Any]] = []

    # `raise_app_exceptions=False`: un endpoint que hoy revienta es parte de la
    # baseline. Se archiva su 500 en vez de abortar la captura y perder el resto.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://baseline.test") as anon:
        clients = {"public": anon}
        for name, url, data in (
            ("student", "/api/v1/auth/student/login", {"username": STUDENT_EMAIL, "password": STUDENT_PASSWORD}),
            ("admin", "/api/v1/auth/student/login", {"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD}),
            (
                "recruiter",
                "/api/v1/auth/company/login",
                {"username": RECRUITER_EMAIL, "password": RECRUITER_PASSWORD},
            ),
        ):
            client = AsyncClient(transport=transport, base_url="http://baseline.test")
            await client.get("/healthz")
            csrf_token = client.cookies.get("studentscompass_csrf")
            response = await client.post(url, data=data, headers={"X-CSRF-Token": csrf_token})
            if response.status_code not in (200, 204):
                raise SystemExit(f"login de {name} falló: {response.status_code} {response.text}")
            clients[name] = client

        try:
            for handler in sorted(handlers, key=lambda h: h["path"]):
                if handler["kind"] != "api" or "GET" not in handler["methods"]:
                    continue
                path = handler["path"]
                actor = handler["actor"]
                vertical = handler["decisions"].get("GET", {}).get("vertical")

                record: dict[str, Any] = {
                    "path": path, "actor": actor, "vertical": vertical,
                }

                if path in FIXTURE_SKIP:
                    record.update(captured=False, reason=FIXTURE_SKIP[path])
                    results.append(record)
                    continue

                client_name = ACTOR_CLIENTS.get(actor)
                if client_name is None and actor not in ACTOR_CLIENTS:
                    record.update(captured=False, reason=f"actor no mapeado: {actor}")
                    results.append(record)
                    continue

                url, reason = fill_path(path, params)
                if url is None:
                    record.update(captured=False, reason=reason)
                    results.append(record)
                    continue

                query = {name: build() for name, build in QUERY_PARAMS.get(path, {}).items()}
                client = clients[client_name or "public"]
                response = await client.get(url, params=query, follow_redirects=False)

                record["as"] = client_name or "anonymous"
                record["request"] = url + (("?" + "&".join(f"{k}={v}" for k, v in query.items())) if query else "")
                record["status"] = response.status_code
                record["content_type"] = response.headers.get("content-type", "")

                body: Any
                if record["content_type"].startswith("application/json"):
                    body = response.json()
                else:
                    # Binarios y HTML no se archivan: lo que la paridad necesita
                    # de ellos es el status y el tipo, no los bytes.
                    body = {
                        "__not_json__": True,
                        "bytes": len(response.content),
                    }
                    record["body_omitted"] = "respuesta no JSON"

                fixture_path = out_dir / (client_name or "anonymous") / f"{fixture_slug(path)}.json"
                fixture_path.parent.mkdir(parents=True, exist_ok=True)
                fixture_path.write_text(
                    json.dumps(
                        {
                            "request": {"method": "GET", "path": record["request"], "as": record["as"]},
                            "response": {
                                "status": response.status_code,
                                "content_type": record["content_type"],
                                "body": body,
                            },
                        },
                        indent=2, sort_keys=True, ensure_ascii=False,
                    )
                    + "\n"
                )
                record["captured"] = True
                record["file"] = str(fixture_path.relative_to(out_dir.parent))
                results.append(record)
        finally:
            for name, client in clients.items():
                if name != "public":
                    await client.aclose()

    return results


# --- Capturas de pantalla --------------------------------------------------

# 23 rutas de vista según docs/refactor/route_inventory.json. La vertical sale
# del mismo inventario (TASK-034), no de una lista escrita a mano aquí.
SCREENS: tuple[dict[str, Any], ...] = (
    {"name": "root", "path": "/", "as": None},
    {"name": "home", "path": "/home", "as": None},
    {"name": "about", "path": "/about", "as": None},
    {"name": "login", "path": "/login", "as": None},
    {"name": "register", "path": "/register", "as": None},
    {"name": "register-api-alias", "path": "/api/v1/auth/register", "as": None},
    {"name": "admin-login", "path": "/admin/login", "as": None},
    {"name": "dashboard", "path": "/dashboard", "as": "student"},
    {"name": "questionnaire", "path": "/questionnaire", "as": "student"},
    {"name": "user-profile", "path": "/user-profile", "as": "student"},
    {"name": "resources", "path": "/resources", "as": "student"},
    {"name": "resource-detail", "path": "/resources/{resource}", "as": "student"},
    {"name": "roadmaps", "path": "/roadmaps", "as": "student"},
    {"name": "roadmap-detail", "path": "/roadmaps/{slug}", "as": "student"},
    {"name": "jobs", "path": "/jobs", "as": "student"},
    {"name": "community", "path": "/community", "as": "student"},
    {"name": "community-feed", "path": "/community/{community}", "as": "student"},
    {"name": "career-lab", "path": "/career-lab", "as": "student"},
    {"name": "admin", "path": "/admin", "as": "admin"},
    {"name": "company-dashboard", "path": "/company-dashboard", "as": "recruiter"},
    {"name": "company-candidates", "path": "/company-candidates", "as": "recruiter"},
    {"name": "company-team", "path": "/company-team", "as": "recruiter"},
)

# La única ruta de vista sin captura, con su razón registrada.
SCREENS_SKIPPED = (
    {
        "name": "roadmap-redirect",
        "path": "/roadmap",
        "reason": "redirección 307 a /roadmaps; no renderiza pantalla propia",
    },
)

VIEWPORTS = (
    ("desktop", {"width": 1440, "height": 900}),
    ("mobile", {"width": 390, "height": 844}),
)

# Todo lo que no sea el propio servidor se aborta en el navegador: la captura
# tiene que depender solo de este repositorio. La consecuencia se registra en el
# manifiesto, no se esconde.
FREEZE_CSS = """
*, *::before, *::after {
  animation: none !important;
  transition: none !important;
  caret-color: transparent !important;
}
"""


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class LocalServer:
    """La app real sobre uvicorn en loopback, para que el JS de las páginas corra."""

    def __init__(self, port: int):
        import uvicorn

        self.port = port
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def __enter__(self) -> "LocalServer":
        self._thread.start()
        deadline = time.time() + 30
        while time.time() < deadline:
            if self._server.started:
                return self
            time.sleep(0.05)
        raise SystemExit("el servidor local no arrancó en 30s")

    def __exit__(self, *exc: object) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=30)


def login_cookies(base_url: str) -> dict[str, dict[str, str]]:
    import httpx

    logins = {
        "student": ("/api/v1/auth/student/login", STUDENT_EMAIL, STUDENT_PASSWORD, "studentscompass_auth"),
        "admin": ("/api/v1/auth/student/login", ADMIN_EMAIL, ADMIN_PASSWORD, "studentscompass_auth"),
        "recruiter": (
            "/api/v1/auth/company/login", RECRUITER_EMAIL, RECRUITER_PASSWORD,
            "studentscompass_company_auth",
        ),
    }
    cookies: dict[str, dict[str, str]] = {}
    with httpx.Client(base_url=base_url) as client:
        for name, (url, email, password, cookie_name) in logins.items():
            client.get("/healthz")
            csrf_token = client.cookies.get("studentscompass_csrf")
            response = client.post(
                url,
                data={"username": email, "password": password},
                headers={"X-CSRF-Token": csrf_token},
            )
            if response.status_code not in (200, 204):
                raise SystemExit(f"login de {name} falló: {response.status_code} {response.text}")
            value = response.cookies.get(cookie_name)
            if not value:
                raise SystemExit(f"login de {name} no devolvió la cookie {cookie_name}")
            cookies[name] = {"name": cookie_name, "value": value}
    return cookies


def resolve_screen_path(template: str) -> str:
    return (
        template
        .replace("{resource}", str(IDS["resource"]))
        .replace("{community}", str(IDS["community"]))
        .replace("{slug}", ROADMAP_SLUG)
    )


def capture_screens(out_dir: Path) -> list[dict[str, Any]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:  # pragma: no cover - depende del entorno
        raise SystemExit(
            "playwright no está instalado; instálalo o pasa --skip-screens:\n"
            "  cd backend && ../.venv/bin/python -m playwright install chromium"
        )

    handlers = load_inventory()
    vertical_by_path = {
        h["path"]: h["decisions"].get("GET", {}).get("vertical")
        for h in handlers
        if h["kind"] == "view"
    }

    port = free_port()
    allow_test_service(f"http://127.0.0.1:{port}")
    base_url = f"http://127.0.0.1:{port}"
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    with LocalServer(port):
        cookies = login_cookies(base_url)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                for viewport_name, viewport in VIEWPORTS:
                    context = browser.new_context(
                        viewport=viewport,
                        device_scale_factor=1,
                        reduced_motion="reduce",
                        locale="en-US",
                        timezone_id="UTC",
                    )
                    context.set_default_timeout(15000)
                    # Se anota por pantalla, no por viewport: saber que «algo»
                    # externo se bloqueó no sirve; saber que /questionnaire pierde
                    # su CSS entero sí.
                    blocked: set[str] = set()

                    def guard(route, request):  # noqa: ANN001
                        if request.url.startswith(base_url):
                            route.continue_()
                            return
                        blocked.add(request.url)
                        route.abort()

                    context.route("**/*", guard)
                    page = context.new_page()

                    for screen in SCREENS:
                        actor = screen["as"]
                        context.clear_cookies()
                        if actor:
                            cookie = cookies[actor]
                            context.add_cookies([
                                {
                                    "name": cookie["name"], "value": cookie["value"],
                                    "domain": "127.0.0.1", "path": "/",
                                }
                            ])
                        url = base_url + resolve_screen_path(screen["path"])
                        blocked.clear()
                        response = page.goto(url, wait_until="load")
                        page.wait_for_timeout(600)
                        page.add_style_tag(content=FREEZE_CSS)
                        file_name = f"{screen['name']}.{viewport_name}.png"
                        page.screenshot(path=str(out_dir / file_name), full_page=True)
                        results.append({
                            "name": screen["name"],
                            "route": screen["path"],
                            "viewport": viewport_name,
                            "as": actor or "anonymous",
                            "status": response.status if response else None,
                            "final_url": page.url.replace(base_url, ""),
                            "vertical": vertical_by_path.get(
                                screen["path"]
                                .replace("{resource}", "{resource_id}")
                                .replace("{community}", "{community_id}")
                            ),
                            "file": f"screens/{file_name}",
                            "blocked_external_requests": sorted(blocked),
                        })

                    context.close()
            finally:
                browser.close()

    return results


# --- Revisión del artefacto ------------------------------------------------

# Cualquier cosa con esta forma en una fixture significa que la captura tocó algo
# que no era la base sintética. La revisión es parte del comando, no un paso
# manual que alguien pueda olvidar.
FORBIDDEN_PATTERNS = (
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.")),
    ("bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._-]{16,}")),
    ("hash_argon2_bcrypt", re.compile(r"\$(2[aby]|argon2)[a-z0-9$]")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{20,}")),
    ("set_cookie", re.compile(r"(?i)\bset-cookie\b")),
    ("password_literal", re.compile(re.escape(STUDENT_PASSWORD))),
    ("password_literal", re.compile(re.escape(ADMIN_PASSWORD))),
    ("password_literal", re.compile(re.escape(RECRUITER_PASSWORD))),
)

ALLOWED_EMAIL_DOMAINS = {"example.com"}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def audit_fixtures(fixtures_dir: Path) -> list[str]:
    problems: list[str] = []
    for path in sorted(fixtures_dir.rglob("*.json")):
        text = path.read_text()
        rel = path.relative_to(fixtures_dir.parent)
        for label, pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                problems.append(f"{rel}: coincide con el patrón prohibido «{label}»")
        for email in set(EMAIL_RE.findall(text)):
            domain = email.split("@", 1)[1].lower()
            if domain not in ALLOWED_EMAIL_DOMAINS:
                problems.append(f"{rel}: email fuera de la semilla sintética ({email})")
    return problems


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- Manifiesto ------------------------------------------------------------


def write_manifest(
    out_dir: Path,
    fixtures: list[dict[str, Any]],
    screens: list[dict[str, Any]],
    openapi_path: Path,
    screens_captured: bool,
) -> None:
    # `files` cubre solo lo versionado. Los sha256 de los PNG viven en
    # `screens/index.json`, junto a los PNG y dentro del artefacto de CI: son
    # dependientes de la máquina que renderiza y no deben ensuciar el diff de un
    # fichero versionado en cada captura.
    files = {}
    screens_dir = out_dir / "screens"
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name in {"manifest.json", "MANIFEST.md", "README.md"}:
            continue
        if screens_dir in path.parents:
            continue
        files[str(path.relative_to(out_dir))] = {
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }

    if screens_captured and screens_dir.is_dir():
        index = {
            str(path.relative_to(screens_dir)): {
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in sorted(screens_dir.glob("*.png"))
        }
        (screens_dir / "index.json").write_text(
            json.dumps(
                {
                    "generated_by": "backend/scripts/capture_baseline.py",
                    "note": (
                        "Los PNG no se versionan (ver docs/refactor/baseline/README.md). "
                        "Este índice viaja con ellos en el artefacto de CI."
                    ),
                    "files": index,
                },
                indent=2, sort_keys=True, ensure_ascii=False,
            )
            + "\n"
        )

    screen_entries = screens
    blocked_by_screen: dict[str, list[str]] = {}
    for entry in screen_entries:
        for url in entry.get("blocked_external_requests", []):
            blocked_by_screen.setdefault(entry["name"], [])
            if url not in blocked_by_screen[entry["name"]]:
                blocked_by_screen[entry["name"]].append(url)
    blocked = sorted({url for urls in blocked_by_screen.values() for url in urls})

    manifest = {
        "generated_by": "backend/scripts/capture_baseline.py",
        "task": "TASK-035",
        "seed": {
            "clock": FIXED_NOW.isoformat(),
            "uuid_namespace": str(NAMESPACE),
            "database": "sqlite (desechable, sembrada por el propio script)",
        },
        "openapi": {
            "file": openapi_path.name,
            "paths": len(json.loads(openapi_path.read_text())["paths"]),
        },
        "fixtures": fixtures,
        "screens": {
            "captured": screens_captured,
            "viewports": {name: dict(size) for name, size in VIEWPORTS},
            "entries": screen_entries,
            "skipped": list(SCREENS_SKIPPED),
            "blocked_external_requests": blocked,
            "blocked_by_screen": {k: sorted(v) for k, v in sorted(blocked_by_screen.items())},
        },
        "files": files,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )

    captured = [f for f in fixtures if f.get("captured")]
    skipped = [f for f in fixtures if not f.get("captured")]

    lines: list[str] = []
    lines.append("# Baseline de paridad — TASK-035")
    lines.append("")
    lines.append(
        "Generado por `backend/scripts/capture_baseline.py`. No editar a mano: se reescribe "
        "entero en cada ejecución."
    )
    lines.append("")
    lines.append(f"- OpenAPI: `{openapi_path.name}` ({manifest['openapi']['paths']} paths)")
    lines.append(f"- Fixtures capturadas: {len(captured)} · sin capturar: {len(skipped)}")
    if screens_captured:
        lines.append(
            f"- Capturas: {len(screen_entries)} "
            f"({len(SCREENS)} pantallas × {len(VIEWPORTS)} viewports)"
        )
    else:
        lines.append("- Capturas: no ejecutadas en esta pasada (`--skip-screens`)")
    lines.append("")

    if screens_captured:
        lines.append("## Pantallas por vertical")
        lines.append("")
        lines.append("| Pantalla | Ruta | Actor | Vertical | Status | Desktop | Mobile |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        by_name: dict[str, dict[str, Any]] = {}
        for entry in screen_entries:
            by_name.setdefault(entry["name"], {})[entry["viewport"]] = entry
        for screen in SCREENS:
            group = by_name.get(screen["name"], {})
            desktop = group.get("desktop")
            mobile = group.get("mobile")
            reference = desktop or mobile
            if reference is None:
                continue
            lines.append(
                f"| {screen['name']} | `{screen['path']}` | {reference['as']} | "
                f"{reference['vertical'] or '—'} | {reference['status']} | "
                f"`{desktop['file'] if desktop else '—'}` | "
                f"`{mobile['file'] if mobile else '—'}` |"
            )
        lines.append("")
        lines.append("### Rutas de vista sin captura")
        lines.append("")
        for entry in SCREENS_SKIPPED:
            lines.append(f"- `{entry['path']}` — {entry['reason']}")
        lines.append("")
        if blocked_by_screen:
            lines.append("### Peticiones externas bloqueadas durante la captura")
            lines.append("")
            lines.append(
                "El navegador solo puede hablar con el servidor local. Estas pantallas "
                "pidieron algo de fuera y no lo recibieron; su captura muestra la página "
                "sin ese recurso."
            )
            lines.append("")
            for name, urls in sorted(blocked_by_screen.items()):
                lines.append(f"- `{name}` — {', '.join(urls)}")
            lines.append("")

    lines.append("## Fixtures por vertical")
    lines.append("")
    lines.append("| Endpoint | Actor | Vertical | Status | Fichero |")
    lines.append("| --- | --- | --- | --- | --- |")
    for entry in captured:
        lines.append(
            f"| `GET {entry['path']}` | {entry['as']} | {entry['vertical'] or '—'} | "
            f"{entry['status']} | `{entry['file']}` |"
        )
    lines.append("")
    if skipped:
        lines.append("### Endpoints GET sin fixture, con razón")
        lines.append("")
        for entry in skipped:
            lines.append(f"- `GET {entry['path']}` — {entry['reason']}")
        lines.append("")

    (out_dir / "MANIFEST.md").write_text("\n".join(lines) + "\n")


# --- Entrada ---------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Captura la baseline de TASK-035.")
    parser.add_argument(
        "--skip-screens",
        action="store_true",
        help="no abrir el navegador; solo OpenAPI y fixtures",
    )
    parser.add_argument(
        "--out",
        default=str(BASELINE_DIR),
        help="directorio de salida (por defecto docs/refactor/baseline)",
    )
    args = parser.parse_args()
    out_dir = Path(args.out).resolve()

    def display_path(path: Path) -> str:
        """Keep the default output concise while allowing --out anywhere."""
        try:
            return str(path.relative_to(REPO_ROOT))
        except ValueError:
            return str(path)

    try:
        for stale in ("fixtures", "screens"):
            shutil.rmtree(out_dir / stale, ignore_errors=True)
        out_dir.mkdir(parents=True, exist_ok=True)

        asyncio.run(create_schema())
        asyncio.run(seed())

        openapi_path = export_openapi(out_dir)
        print(f"openapi: {display_path(openapi_path)}")

        fixtures = asyncio.run(capture_fixtures(out_dir / "fixtures"))
        captured = sum(1 for f in fixtures if f.get("captured"))
        print(f"fixtures: {captured} capturadas, {len(fixtures) - captured} con razón registrada")

        screens: list[dict[str, Any]] = []
        if not args.skip_screens:
            screens = capture_screens(out_dir / "screens")
            print(f"screens: {len(screens)} capturas")

        problems = audit_fixtures(out_dir / "fixtures")
        if problems:
            print("\nEl artefacto no pasa la revisión de secretos/PII:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 1
        print("revisión de secretos/PII: sin hallazgos")

        write_manifest(out_dir, fixtures, screens, openapi_path, not args.skip_screens)
        print(f"manifiesto: {display_path(out_dir / 'MANIFEST.md')}")
        return 0
    finally:
        asyncio.run(ENGINE.dispose())
        shutil.rmtree(_TMP_DIR, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
