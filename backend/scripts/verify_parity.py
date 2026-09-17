"""Verificación de paridad de las ocho verticales React — TASK-046 a TASK-053.

Origen: las fichas TASK-046..TASK-053 de `docs/refactor/TASKS.md`. Las tres
casillas que ninguna vertical podía marcar eran siempre las mismas:

    - Paridad funcional y visual demostrada contra la baseline de TASK-035.
    - Tests de permisos y de errores por rol.
    - Cero tráfico del frontend al contrato legacy, medido y registrado.

Este script las mide. No es un `capture_baseline.py` bis: aquel fotografió el
monolito Jinja *antes* de migrar; este levanta el **bundle React** contra la
**misma semilla sintética** y compara, mide y registra.

Que la semilla sea la misma no es un detalle: si los datos difieren, una
pantalla distinta puede serlo por los datos y no por la migración, y la
comparación no significa nada. Por eso el módulo importa `capture_baseline` en
vez de reimplementar el sembrado — hay una sola definición de «los datos de la
baseline».

Qué produce, en `docs/refactor/parity/`:

    screens/<pantalla>.<viewport>.png    el SPA bajo la semilla de la baseline
    sidebyside/<pantalla>.<viewport>.png legacy | React, para revisión humana
    report.json                          todo lo medido, en bruto
    REPORT.md                            lo mismo, legible, por vertical

Uso:

    cd backend && ../.venv/bin/python scripts/verify_parity.py
    cd backend && ../.venv/bin/python scripts/verify_parity.py --only V1-TASK-046

El bundle tiene que estar construido (`cd frontend && npm run build`): este
script sirve `frontend/dist`, no levanta Vite.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

# capture_baseline aplica el aislamiento y construye el engine en tiempo de
# import; tiene que entrar antes que cualquier módulo de `app`.
import scripts.capture_baseline as baseline  # noqa: E402

PARITY_DIR = REPO_ROOT / "docs" / "refactor" / "parity"
DIST_DIR = REPO_ROOT / "frontend" / "dist"
BASELINE_SCREENS = REPO_ROOT / "docs" / "refactor" / "baseline" / "screens"
ROUTE_TARGETS = REPO_ROOT / "docs" / "refactor" / "route_targets.csv"


# --- El espejo de Nginx ----------------------------------------------------

# El regex se **lee** de frontend/nginx.conf, no se copia.
#
# Antes estaba copiado literal, con un comentario explicando que copiarlo era
# mejor que aproximarlo. La intención era buena y el mecanismo no: en cuanto el
# pre-flight del cutover (TASK-058) cambió esa lista —`robots.txt` y
# `sitemap.xml` salieron porque ahora los sirve el bundle, `/auth/jwt/` entró
# para que su tráfico siga siendo medible— esta copia quedó describiendo un
# proxy que ya no existe, en silencio y justo en el fichero cuyo trabajo es
# decir qué origen sirve cada ruta.
#
# Lo que este espejo modela y lo que no, porque la diferencia importa al leer
# el informe: modela el reparto entre API y bundle, que es lo que se está
# midiendo. NO modela los 301 de las pantallas legacy, el 410 de `/static/`, ni
# el 404 por extensión. Ninguno de los tres afecta a lo que se mide —el SPA no
# pide esas rutas— y todos están comprobados en el smoke de `deploy.yml`, que
# corre contra el Nginx de verdad.
NGINX_CONF = REPO_ROOT / "frontend" / "nginx.conf"


def _proxy_regex_from_nginx() -> re.Pattern[str]:
    conf = NGINX_CONF.read_text(encoding="utf-8")
    # El regex de Nginx no lleva espacios, así que `\S+` lo captura entero, y
    # anclar en `^/(api/` lo distingue de las otras `location ~` del fichero.
    found = re.search(r"^\s*location\s+~\s+(\^/\(api/\S*)\s*\{", conf, re.MULTILINE)
    if found is None:
        raise SystemExit(
            f"No se encontró la location del proxy de API en {NGINX_CONF}. "
            "Si cambió de forma, actualizar esta extracción: un espejo que "
            "adivina el reparto de rutas no mide nada."
        )
    return re.compile(found.group(1))


PROXY_RE = _proxy_regex_from_nginx()


class SpaMirror:
    """Sirve el bundle y delega a la API, en un solo origen como hace Nginx.

    En producción son dos servicios de Cloud Run tras un dominio; aquí son dos
    ramas de un `if` dentro del mismo proceso. Lo que importa para lo que se
    mide —qué origen ve el navegador, qué ruta resuelve el SPA y cuál la API—
    es idéntico, y no hace falta construir dos imágenes para comprobarlo.
    """

    def __init__(self, api_app: Any, dist: Path) -> None:
        self.api = api_app
        self.dist = dist
        self.index = (dist / "index.html").read_bytes()

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or PROXY_RE.match(scope["path"]):
            await self.api(scope, receive, send)
            return

        candidate = (self.dist / scope["path"].lstrip("/")).resolve()
        if self.dist.resolve() in candidate.parents and candidate.is_file():
            body = candidate.read_bytes()
            content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        else:
            # `try_files $uri $uri/ /index.html`: cualquier ruta del SPA es
            # index.html y el router de React decide desde el cliente.
            body = self.index
            content_type = "text/html; charset=utf-8"

        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", content_type.encode()),
                (b"content-length", str(len(body)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": body})


# --- Qué pantalla de la baseline es qué ruta del SPA -----------------------

# La migración renombró rutas (§5.2 del plan 08): `/user-profile` es `/profile`,
# `/company-dashboard` es `/company`. Sin esta tabla la comparación mediría el
# 404 del SPA contra la pantalla legacy y llamaría a eso «sin paridad».
SCREEN_MAP: tuple[dict[str, Any], ...] = (
    {"baseline": "root", "spa": "/", "as": None, "vertical": "V1-TASK-046"},
    {"baseline": "home", "spa": "/", "as": None, "vertical": "V1-TASK-046"},
    {"baseline": "about", "spa": "/about", "as": None, "vertical": "V1-TASK-046"},
    {"baseline": "login", "spa": "/login", "as": None, "vertical": "V1-TASK-046"},
    {"baseline": "register", "spa": "/register", "as": None, "vertical": "V1-TASK-046"},
    {"baseline": "admin-login", "spa": "/admin/login", "as": None, "vertical": "V8-TASK-053"},
    {"baseline": "questionnaire", "spa": "/questionnaire", "as": "student", "vertical": "V2-TASK-047"},
    {"baseline": "user-profile", "spa": "/profile", "as": "student", "vertical": "V2-TASK-047"},
    {"baseline": "dashboard", "spa": "/dashboard", "as": "student", "vertical": "V3-TASK-048"},
    {"baseline": "resources", "spa": "/resources", "as": "student", "vertical": "V3-TASK-048"},
    {"baseline": "resource-detail", "spa": "/resources/{resource}", "as": "student", "vertical": "V3-TASK-048"},
    {"baseline": "roadmaps", "spa": "/roadmaps", "as": "student", "vertical": "V3-TASK-048"},
    {"baseline": "roadmap-detail", "spa": "/roadmaps/{slug}", "as": "student", "vertical": "V3-TASK-048"},
    {"baseline": "jobs", "spa": "/jobs", "as": "student", "vertical": "V4-TASK-049"},
    {"baseline": "company-dashboard", "spa": "/company", "as": "recruiter", "vertical": "V5-TASK-050"},
    {"baseline": "company-candidates", "spa": "/company/applicants", "as": "recruiter", "vertical": "V5-TASK-050"},
    {"baseline": "company-team", "spa": "/company/recruiters", "as": "recruiter", "vertical": "V5-TASK-050"},
    {"baseline": "community", "spa": "/community", "as": "student", "vertical": "V6-TASK-051"},
    {"baseline": "community-feed", "spa": "/community/{community}", "as": "student", "vertical": "V6-TASK-051"},
    {"baseline": "career-lab", "spa": "/career-lab", "as": "student", "vertical": "V7-TASK-052"},
    {"baseline": "admin", "spa": "/admin", "as": "admin", "vertical": "V8-TASK-053"},
)

# Pantallas que el SPA añade y que por definición no tienen baseline: nacieron
# con la migración. Se capturan igual —su captura es la evidencia de que la
# pantalla existe y renderiza— pero no se comparan contra nada.
SPA_ONLY: tuple[dict[str, Any], ...] = (
    {"baseline": None, "spa": "/jobs/applications", "as": "student", "vertical": "V4-TASK-049",
     "note": "listado de candidaturas; en el monolito vivía dentro de /jobs"},
    {"baseline": None, "spa": "/company/postings", "as": "recruiter", "vertical": "V5-TASK-050",
     "note": "gestión de ofertas; en el monolito vivía dentro de /company-dashboard"},
    {"baseline": None, "spa": "/messages", "as": "student", "vertical": "V6-TASK-051",
     "note": "mensajería; nunca tuvo pantalla legacy (TASK-024 la dejó solo como API)"},
)

# `/api/v1/auth/register` es un alias de API que la baseline fotografió como
# pantalla. No es una pantalla del SPA y no debe serlo.
SCREENS_WITHOUT_SPA = (
    {"baseline": "register-api-alias", "vertical": "V1-TASK-046",
     "reason": "alias de API, no pantalla; el SPA registra contra POST /api/v1/auth/register"},
)


# Diferencias contra la baseline que ya se han mirado y tienen explicación. Se
# listan aquí para que el informe las afirme en vez de dejar que quien revise
# las vuelva a descubrir cada vez, y para que una diferencia *nueva* destaque
# por no estar en esta lista.
PARITY_NOTES: dict[str, str] = {
    "questionnaire": (
        "El monolito pintaba las 16 preguntas en una página de 1788 px de alto; "
        "el SPA es un stepper de una pregunta por paso. La diferencia de altura "
        "y de tinta entre las dos capturas es esa, no contenido perdido: el "
        "contenido y el orden de las preguntas salen de `GET /api/v1/questionnaire`, "
        "que es el mismo endpoint y la misma definición versionada. Es un cambio "
        "de presentación, no de regla."
    ),
    "login": (
        "Mismo contenido y misma estructura de dos paneles (aside de marca + "
        "formulario, toggle de tipo de cuenta, ambos enlaces). Lo que sube el RMS "
        "es el shell: el monolito servía `/login` como página full-bleed sobre el "
        "degradado y sin navegación, y el SPA la sirve dentro de `PublicShell`, con "
        "nav, fondo claro y los dos paneles separados en vez de fundidos. Es una "
        "consecuencia de meter la pantalla en el shell público, no contenido "
        "perdido; cambiarlo sería rediseñar el shell, que ninguna ficha pide."
    ),
    "register": (
        "Igual que `login`: mismo contenido, misma estructura, el RMS es la "
        "diferencia de shell."
    ),
    "admin": (
        "Fondo oscuro en ambas: ADR-002 lo trata como un scope sobre los mismos "
        "tokens, no como una cuarta paleta, y el RMS bajo (13-22) lo confirma."
    ),
}

# Hallazgos que este arnés encontró y que no son suyos que arreglar: quedan
# escritos en el informe con su alcance exacto para que se decidan, en vez de
# desaparecer entre las tablas.
OPEN_FINDINGS: tuple[dict[str, str], ...] = (
    {
        "vertical": "V2-TASK-047",
        "title": "`GET /api/v1/questionnaire/profile` responde 500 ante una fila "
                 "de cuestionario que no sea una lista",
        "body": (
            "El endpoint legacy no tenía `response_model` y devolvía la fila tal cual, "
            "con 200. `QuestionnaireProfileRead` (TASK-047) declara "
            "`answers: List[AnswerCreate]` y `results: List[CareerScore]`, así que una "
            "fila con otra forma ya no valida y la pantalla de perfil recibe un 500.\n\n"
            "**Lo que está comprobado:** con la semilla archivada de TASK-035, que guarda "
            "`answers` como diccionario, el endpoint pasa de 200 (baseline) a 500 (hoy).\n\n"
            "**Lo que no:** si alguna fila real tiene esa forma. `questionnaireService."
            "submit_questionnaire` escribe una lista y el comentario del modelo documenta "
            "la lista, así que la forma del seed no es la que produce la aplicación hoy — "
            "pero el seed es evidencia archivada de TASK-035 y **no se ha retocado** para "
            "que el 500 desaparezca. Se resuelve con una consulta: si existen filas "
            "`user_questionnaires` cuyo `answers` no sea un array, tienen este 500 hoy.\n\n"
            "**Por qué no se arregla aquí:** la salida —degradar en vez de 500, migrar las "
            "filas, o confirmar que no las hay— es una decisión de producto sobre datos "
            "históricos, que es justo lo que TASK-030 acotó y lo que la Definition of Done "
            "global prohíbe resolver inventando historia."
        ),
    },
    {
        "vertical": "V8-TASK-053",
        "title": "El guard de `/admin` pasaba a cualquier estudiante — corregido en esta pasada",
        "body": (
            "`views.py` rebotaba `user is None or not user.is_superuser` a `/admin/login`. "
            "El router de React guardaba `/admin` con `RequireActor allow={[\"student\"]}`, "
            "que cualquier estudiante satisface, así que un no-administrador llegaba al "
            "shell de admin y lo veía llenarse de 403.\n\n"
            "Ningún dato se filtró —las nueve rutas `/api/v1/admin/*` responden 403 al "
            "estudiante, y la tabla de esta vertical lo enseña— pero «el acceso prohibido "
            "responde igual» no se cumplía.\n\n"
            "**Corregido:** `SessionActor.is_superuser` (aditivo en el contrato) y el guard "
            "`RequireAdmin`, con los cuatro casos cubiertos en `guards.test.tsx`."
        ),
    },
)


def resolve(path: str) -> str:
    return (
        path
        .replace("{resource}", str(baseline.IDS["resource"]))
        .replace("{community}", str(baseline.IDS["community"]))
        .replace("{slug}", baseline.ROADMAP_SLUG)
    )


# --- Qué cuenta como «contrato legacy» -------------------------------------

def load_legacy_contract() -> dict[str, list[dict[str, str]]]:
    """Las rutas marcadas `retire` en la matriz de TASK-034, por vertical.

    La lista no se escribe a mano aquí: se lee de `route_targets.csv`, que es
    donde TASK-034 decidió el destino de cada ruta. Si mañana una ruta cambia de
    destino, esta comprobación cambia con ella en vez de quedarse mintiendo.
    """
    import csv

    legacy: dict[str, list[dict[str, str]]] = {}
    with ROUTE_TARGETS.open() as handle:
        for row in csv.DictReader(handle):
            if row["destination"] != "retire":
                continue
            legacy.setdefault(row["vertical"], []).append(
                {"method": row["method"], "path": row["path"], "target": row["target"]}
            )
    return legacy


# De las 33 rutas `retire`, estas son las que son **contrato de datos**: un
# fetch del SPA a cualquiera de ellas es tráfico legacy sin matices. Las otras
# son rutas de vista Jinja cuyo path el SPA reclama como ruta de cliente, así
# que una navegación de documento a `/dashboard` es el SPA funcionando, no una
# recaída. La distinción la hace `resource_type`, no el path.
LEGACY_DATA_ENDPOINTS = re.compile(
    r"^/(?:"
    r"auth/jwt/(?:login|logout)"
    r"|api/v1/posts(?:/|$)"
    r"|api/v1/upload_post$"
    r"|api/v1/delete_post/"
    r")"
)

# El monolito servía su UI desde `/static/`. El bundle vive en `/assets/`. Una
# sola petición a `/static/js/*.js` significaría que una pantalla React está
# apoyándose en el JS que TASK-059 va a borrar.
LEGACY_ASSETS = re.compile(r"^/static/(?:js|css)/")


def classify_request(path: str, resource_type: str, method: str) -> str | None:
    """Devuelve el motivo por el que una petición es legacy, o None si no lo es."""
    if LEGACY_ASSETS.match(path):
        return "asset legacy del monolito"
    if LEGACY_DATA_ENDPOINTS.match(path):
        return "endpoint de datos marcado `retire` en la matriz de TASK-034"
    return None


# --- Sesiones --------------------------------------------------------------

ACTORS = {
    "student": ("/api/v1/auth/student/login", baseline.STUDENT_EMAIL, baseline.STUDENT_PASSWORD),
    "admin": ("/api/v1/auth/student/login", baseline.ADMIN_EMAIL, baseline.ADMIN_PASSWORD),
    "recruiter": ("/api/v1/auth/company/login", baseline.RECRUITER_EMAIL, baseline.RECRUITER_PASSWORD),
}


def login_all(base_url: str) -> dict[str, list[dict[str, str]]]:
    """Cookies completas por actor, no solo la de auth.

    `capture_baseline.login_cookies` devuelve únicamente la cookie de sesión
    porque sus capturas son de solo lectura. Aquí hace falta también la de CSRF:
    el barrido de permisos manda mutaciones, y sin ella el 403 que devolvería el
    middleware CSRF se confundiría con el 403 de autorización que se está
    midiendo.
    """
    import httpx

    jars: dict[str, list[dict[str, str]]] = {}
    for name, (url, email, password) in ACTORS.items():
        with httpx.Client(base_url=base_url) as client:
            client.get("/healthz")
            csrf = client.cookies.get("studentscompass_csrf")
            response = client.post(
                url,
                data={"username": email, "password": password},
                headers={"X-CSRF-Token": csrf},
            )
            if response.status_code not in (200, 204):
                raise SystemExit(f"login de {name} falló: {response.status_code} {response.text[:300]}")
            jars[name] = [
                {"name": key, "value": value, "domain": "127.0.0.1", "path": "/"}
                for key, value in client.cookies.items()
            ]
    return jars


# --- Captura del SPA -------------------------------------------------------

def capture_spa(base_url: str, jars: dict, targets: tuple, out_dir: Path) -> list[dict[str, Any]]:
    """Fotografía cada pantalla del SPA y anota todo lo que pidió al servidor.

    Las dos cosas salen de la misma visita a propósito. Medir el tráfico en una
    pasada aparte significaría medirlo sobre una interacción distinta de la que
    produjo la captura, y entonces ni la captura prueba lo que pidió la pantalla
    ni el tráfico corresponde a lo que se ve en la captura.
    """
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for viewport_name, viewport in baseline.VIEWPORTS:
                context = browser.new_context(
                    viewport=viewport,
                    device_scale_factor=1,
                    reduced_motion="reduce",
                    locale="en-US",
                    timezone_id="UTC",
                )
                context.set_default_timeout(20000)

                requests: list[dict[str, str]] = []
                blocked: set[str] = set()

                def on_request(request) -> None:  # noqa: ANN001
                    if request.url.startswith(base_url):
                        requests.append({
                            "method": request.method,
                            "path": request.url[len(base_url):].split("?")[0],
                            "resource_type": request.resource_type,
                        })

                def guard(route, request) -> None:  # noqa: ANN001
                    # Igual que la baseline: el navegador solo habla con este
                    # servidor, para que la captura dependa solo del repositorio.
                    if request.url.startswith(base_url):
                        route.continue_()
                        return
                    blocked.add(request.url)
                    route.abort()

                context.route("**/*", guard)
                context.on("request", on_request)
                page = context.new_page()

                console_errors: list[str] = []
                page.on("pageerror", lambda exc: console_errors.append(str(exc)))

                for target in targets:
                    actor = target["as"]
                    context.clear_cookies()
                    if actor:
                        context.add_cookies(jars[actor])

                    requests.clear()
                    blocked.clear()
                    console_errors.clear()

                    url = base_url + resolve(target["spa"])
                    response = page.goto(url, wait_until="load")
                    # El SPA pinta después de resolver su sesión y sus queries;
                    # `load` solo garantiza que llegó el bundle.
                    try:
                        page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    page.wait_for_timeout(600)
                    page.add_style_tag(content=baseline.FREEZE_CSS)

                    name = target["baseline"] or target["spa"].strip("/").replace("/", "-")
                    file_name = f"{name}.{viewport_name}.png"
                    page.screenshot(path=str(out_dir / file_name), full_page=True)

                    offenders = [
                        {**request, "reason": reason}
                        for request in requests
                        if (reason := classify_request(
                            request["path"], request["resource_type"], request["method"]
                        ))
                    ]

                    results.append({
                        "name": name,
                        "baseline": target["baseline"],
                        "spa_route": target["spa"],
                        "viewport": viewport_name,
                        "as": actor or "anonymous",
                        "vertical": target["vertical"],
                        "status": response.status if response else None,
                        "final_url": page.url[len(base_url):],
                        "file": f"screens/{file_name}",
                        "requests": sorted(
                            {f"{r['method']} {r['path']}" for r in requests}
                        ),
                        "legacy_requests": offenders,
                        "page_errors": console_errors[:],
                        "blocked_external_requests": sorted(blocked),
                        "note": target.get("note"),
                    })

                context.close()
        finally:
            browser.close()

    return results


# --- Barrido de permisos ---------------------------------------------------

# Qué actor tiene derecho a qué, según la columna `actor` del inventario de
# TASK-034. `:optional` significa que el endpoint atiende también a anónimos
# —la sesión cambia la respuesta, no el permiso— así que no se le exige 401.
ACTOR_RIGHTS = {
    "student": {"student", "admin"},
    "admin": {"admin"},
    "recruiter": {"recruiter"},
    "recruiter:job_manager": {"recruiter"},
    "recruiter:owner": {"recruiter"},
}

DENIED = {401, 403}

# Endpoints cuyo 5xx aquí es el entorno, no el código: sirven un objeto desde el
# bucket, y `S3Service.__init__` levanta `ValueError` cuando no hay bucket
# configurado. El aislamiento de la suite da credenciales falsas a propósito
# —docker-compose.yml documenta la misma condición como el caso normal en
# local— así que un 500 en estos dos es la respuesta correcta a «no hay
# almacenamiento», y llamarlo hallazgo sería ruido. Lo que sí mide el barrido
# en ellos es el permiso, que se resuelve antes de tocar el bucket: el 401 de
# los tres actores sin derecho es real.
NEEDS_OBJECT_STORAGE = (
    "/api/v1/companies/me/applications/{application_id}/resume/download",
    "/api/v1/companies/me/applications/{application_id}/resume/preview",
)

# Rutas del SPA cuyo guard de cliente se comprueba, y a dónde debe mandar a
# quien no corresponde. El backend es la autoridad —eso lo mide el barrido de
# API— pero un guard roto enseña la pantalla vacía antes de que el 403 llegue,
# y eso también es un fallo de permisos.
GUARDED_ROUTES = (
    {"route": "/dashboard", "owner": "student", "vertical": "V3-TASK-048"},
    {"route": "/profile", "owner": "student", "vertical": "V2-TASK-047"},
    {"route": "/questionnaire", "owner": "student", "vertical": "V2-TASK-047"},
    {"route": "/resources", "owner": "student", "vertical": "V3-TASK-048"},
    {"route": "/roadmaps", "owner": "student", "vertical": "V3-TASK-048"},
    {"route": "/jobs", "owner": "student", "vertical": "V4-TASK-049"},
    {"route": "/jobs/applications", "owner": "student", "vertical": "V4-TASK-049"},
    {"route": "/career-lab", "owner": "student", "vertical": "V7-TASK-052"},
    {"route": "/community", "owner": "student", "vertical": "V6-TASK-051"},
    {"route": "/messages", "owner": "student", "vertical": "V6-TASK-051"},
    {"route": "/company", "owner": "recruiter", "vertical": "V5-TASK-050"},
    {"route": "/company/postings", "owner": "recruiter", "vertical": "V5-TASK-050"},
    {"route": "/company/applicants", "owner": "recruiter", "vertical": "V5-TASK-050"},
    {"route": "/company/recruiters", "owner": "recruiter", "vertical": "V5-TASK-050"},
    {"route": "/admin", "owner": "admin", "vertical": "V8-TASK-053"},
)


def sweep_api_permissions(base_url: str, jars: dict) -> list[dict[str, Any]]:
    """Cada endpoint REST no público, contra cada actor y contra un anónimo."""
    import httpx

    handlers = json.loads(
        (REPO_ROOT / "docs" / "refactor" / "route_inventory.json").read_text()
    )["handlers"]
    params = baseline.path_params()

    sessions = {"anonymous": httpx.Client(base_url=base_url)}
    for actor, cookies in jars.items():
        client = httpx.Client(base_url=base_url)
        for cookie in cookies:
            client.cookies.set(cookie["name"], cookie["value"])
        sessions[actor] = client

    results: list[dict[str, Any]] = []
    try:
        for handler in handlers:
            if handler["kind"] != "api" or "GET" not in handler["methods"]:
                continue
            decision = handler.get("decisions", {}).get("GET", {})
            if decision.get("destination") != "rest":
                continue
            actor_spec = handler["actor"]
            if actor_spec == "public" or actor_spec.endswith(":optional"):
                continue

            url, skip_reason = baseline.fill_path(handler["path"], params)
            if not url:
                results.append({
                    "path": handler["path"], "actor_spec": actor_spec,
                    "vertical": decision.get("vertical"), "skipped": skip_reason,
                })
                continue

            entitled = ACTOR_RIGHTS.get(actor_spec, set())
            observed: dict[str, int] = {}
            for caller, client in sessions.items():
                try:
                    observed[caller] = client.get(url, timeout=30).status_code
                except Exception as exc:  # pragma: no cover
                    observed[caller] = -1
                    print(f"  ! {url} como {caller}: {exc}", file=sys.stderr)

            violations: list[str] = []
            scoped: list[str] = []
            errors: list[str] = []
            for caller, status in observed.items():
                allowed = caller in entitled
                if not allowed:
                    # La invariante fuerte, y la única que la columna `actor`
                    # del inventario respalda: quien no es de ese tipo de actor
                    # no pasa.
                    if status not in DENIED:
                        violations.append(
                            f"{caller} no es `{actor_spec}` y recibió {status} "
                            "en vez de 401/403"
                        )
                    continue
                # Para quien sí es del tipo correcto hay que separar dos cosas
                # que un 4xx mezcla. Un 401 es la sesión rechazada: el permiso
                # por rol está roto. Un 403 puede ser autorización *de recurso*
                # —no eres miembro de esa comunidad, no eres dueño de esa
                # oferta— que el inventario no modela y que es correcta. Tratar
                # las dos igual convertiría en «violación» el gateo por
                # membresía de communities, que es justamente lo que debe pasar.
                if status == 401:
                    violations.append(f"{caller} tiene derecho y recibió 401")
                elif status == 403:
                    scoped.append(f"{caller}: 403 (autorización de recurso, no de rol)")
                elif status >= 500:
                    if handler["path"] in NEEDS_OBJECT_STORAGE:
                        scoped.append(
                            f"{caller}: {status} por almacenamiento de objetos no "
                            "configurado en este arnés, no por el código"
                        )
                    else:
                        errors.append(f"{caller}: {status}")

            results.append({
                "path": handler["path"], "url": url, "actor_spec": actor_spec,
                "vertical": decision.get("vertical"),
                "entitled": sorted(entitled), "observed": observed,
                "violations": violations,
                "resource_scoped": scoped,
                "server_errors": errors,
            })
    finally:
        for client in sessions.values():
            client.close()

    return results


def sweep_ui_guards(base_url: str, jars: dict) -> list[dict[str, Any]]:
    """Adónde manda el guard del SPA a quien no es dueño de la ruta."""
    from playwright.sync_api import sync_playwright

    results: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            context.set_default_timeout(20000)
            context.route(
                "**/*",
                lambda route, request: (
                    route.continue_() if request.url.startswith(base_url) else route.abort()
                ),
            )
            page = context.new_page()

            for guarded in GUARDED_ROUTES:
                for caller in ("anonymous", "student", "recruiter", "admin"):
                    context.clear_cookies()
                    if caller != "anonymous":
                        context.add_cookies(jars[caller])
                    page.goto(base_url + guarded["route"], wait_until="load")
                    try:
                        page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        pass
                    page.wait_for_timeout(400)
                    landed = page.url[len(base_url):]
                    results.append({
                        "route": guarded["route"], "owner": guarded["owner"],
                        "vertical": guarded["vertical"], "caller": caller,
                        "landed": landed,
                        "stayed": landed.split("?")[0] == guarded["route"],
                    })
            context.close()
        finally:
            browser.close()
    return results


# --- Comparación visual ----------------------------------------------------

# Los tokens de marca que ADR-002 congela: «Los valores no se rediseñan. Se
# toman literales de style.css». Que aparezcan en la pantalla React es
# comprobable; que la pantalla «se vea igual» no lo es sin un ojo humano, y por
# eso esto produce además la tira comparativa.
BRAND = {"teal": (0x0F, 0x76, 0x6E), "teal_light": (0x5E, 0xEA, 0xD4), "ink": (0x0F, 0x17, 0x2A)}


def image_signature(path: Path) -> dict[str, Any]:
    from PIL import Image
    import numpy as np

    with Image.open(path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        thumb = np.asarray(rgb.convert("L").resize((64, 64), Image.BILINEAR), dtype=np.float32)
        pixels = np.asarray(rgb.resize((min(width, 480), min(height, 1600)), Image.BILINEAR), dtype=np.int16)

    palette, counts = {}, {}
    for name, target in BRAND.items():
        distance = np.abs(pixels - np.array(target, dtype=np.int16)).sum(axis=2)
        hit = distance < 60
        palette[name] = round(float(hit.mean()), 5)
        counts[name] = int(hit.sum())

    return {
        "width": width, "height": height,
        "thumb": thumb,
        "palette": palette,
        # La proporción sola miente en las pantallas de poco contenido: el
        # cuestionario tiene su teal en el logo, la barra de progreso y el botón
        # —presente y correcto— y aun así baja del 0,05 % porque la página es
        # alta y casi vacía. Lo que se quiere saber es si el color está, no qué
        # fracción ocupa, así que la comprobación va sobre el conteo.
        "palette_px": counts,
        "ink": round(float((np.asarray(thumb) < 200).mean()), 5),
    }


def compare(baseline_png: Path, parity_png: Path) -> dict[str, Any]:
    import numpy as np

    left = image_signature(baseline_png)
    right = image_signature(parity_png)
    rms = float(np.sqrt(((left["thumb"] - right["thumb"]) ** 2).mean()))

    return {
        "baseline_size": [left["width"], left["height"]],
        "parity_size": [right["width"], right["height"]],
        # 0 = estructuras de luz idénticas, 255 = opuestas. Es un indicador para
        # ordenar la revisión humana, no un umbral de aprobado: la migración
        # cambió el DOM y el motor de layout, así que un diff de píxel a cero
        # sería sospechoso, no bueno.
        "layout_rms": round(rms, 2),
        "ink_baseline": left["ink"],
        "ink_parity": right["ink"],
        "palette_baseline": left["palette"],
        "palette_parity": right["palette"],
        "palette_px_parity": right["palette_px"],
        # Lo que sí es exigible por ADR-002: el teal de marca sigue presente.
        "brand_preserved": (
            right["palette_px"]["teal"] + right["palette_px"]["teal_light"]
        ) > 50,
    }


def side_by_side(baseline_png: Path, parity_png: Path, out: Path, title: str) -> None:
    from PIL import Image, ImageDraw

    gutter, header = 24, 28
    with Image.open(baseline_png) as a, Image.open(parity_png) as b:
        left, right = a.convert("RGB"), b.convert("RGB")
        height = max(left.height, right.height)
        canvas = Image.new("RGB", (left.width + right.width + gutter, height + header), "white")
        canvas.paste(left, (0, header))
        canvas.paste(right, (left.width + gutter, header))
        draw = ImageDraw.Draw(canvas)
        draw.text((4, 8), f"LEGACY · {title}", fill="black")
        draw.text((left.width + gutter + 4, 8), f"REACT · {title}", fill="black")
        out.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out)


class MirrorServer:
    """Uvicorn sobre el espejo de Nginx, en un hilo, como hace la baseline."""

    def __init__(self, asgi_app: Any, port: int) -> None:
        import threading

        import uvicorn

        self.port = port
        self._server = uvicorn.Server(
            uvicorn.Config(asgi_app, host="127.0.0.1", port=port, log_level="warning")
        )
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def __enter__(self) -> "MirrorServer":
        import time

        self._thread.start()
        deadline = time.time() + 30
        while time.time() < deadline:
            if self._server.started:
                return self
            time.sleep(0.05)
        raise SystemExit("el servidor de paridad no arrancó en 30s")

    def __exit__(self, *exc: object) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=30)


# --- Informe ---------------------------------------------------------------

VERTICAL_TASKS = {
    "V1-TASK-046": "Vertical 1 — Shell público y autenticación",
    "V2-TASK-047": "Vertical 2 — Perfil, cuestionario y CV",
    "V3-TASK-048": "Vertical 3 — Dashboard, recursos y roadmaps",
    "V4-TASK-049": "Vertical 4 — Jobs, análisis de CV y candidaturas",
    "V5-TASK-050": "Vertical 5 — Company",
    "V6-TASK-051": "Vertical 6 — Community, friendships y messages",
    "V7-TASK-052": "Vertical 7 — Career Lab / Capstone",
    "V8-TASK-053": "Vertical 8 — Admin",
}


def build_report(data: dict[str, Any]) -> str:
    lines: list[str] = []
    add = lines.append

    add("# Paridad de las ocho verticales — TASK-046 a TASK-053")
    add("")
    add("Generado por `backend/scripts/verify_parity.py`. No editar a mano.")
    add("")
    add("El SPA corre contra **la misma semilla sintética que la baseline de "
        "TASK-035**, servido en un solo origen por el espejo en proceso de "
        "`frontend/nginx.conf`. Cada pantalla se fotografía y, en la misma "
        "visita, se anota todo lo que pidió al servidor.")
    add("")

    screens = data["screens"]
    api = data["api_permissions"]
    guards = data["ui_guards"]

    total_legacy = sum(len(s["legacy_requests"]) for s in screens)
    total_violations = sum(len(entry.get("violations", [])) for entry in api)
    total_errors = sum(len(entry.get("server_errors", [])) for entry in api)
    add("## Resumen")
    add("")
    add(f"- Pantallas capturadas: **{len(screens)}** "
        f"({len({s['name'] for s in screens})} pantallas × 2 viewports)")
    add(f"- Comparadas contra la baseline: **{len([s for s in screens if s.get('comparison')])}**")
    add(f"- Endpoints REST barridos por rol: **{len([e for e in api if not e.get('skipped')])}** "
        f"× 4 actores")
    add(f"- Rutas del SPA con guard verificado: **{len({g['route'] for g in guards})}** × 4 actores")
    add(f"- **Peticiones al contrato legacy: {total_legacy}**")
    add(f"- **Violaciones de permisos: {total_violations}**")
    add(f"- **Endpoints que devuelven 5xx a quien tiene derecho: {total_errors}**")
    add("")

    for vertical, title in VERTICAL_TASKS.items():
        v_screens = [s for s in screens if s["vertical"] == vertical]
        v_api = [e for e in api if e.get("vertical") == vertical]
        v_guards = [g for g in guards if g["vertical"] == vertical]
        if not (v_screens or v_api or v_guards):
            continue

        add(f"## {vertical} — {title}")
        add("")

        if v_screens:
            add("### Pantallas")
            add("")
            add("| Pantalla | Ruta SPA | Actor | HTTP | Baseline | RMS layout | Marca | Errores JS |")
            add("| --- | --- | --- | --- | --- | --- | --- | --- |")
            for screen in sorted(v_screens, key=lambda s: (s["name"], s["viewport"])):
                comparison = screen.get("comparison")
                if comparison:
                    rms = f"{comparison['layout_rms']}"
                    brand = "sí" if comparison["brand_preserved"] else "**NO**"
                    ref = screen["baseline"]
                else:
                    rms = "—"
                    brand = "—"
                    ref = "_sin baseline_"
                errors = len(screen["page_errors"])
                add(f"| {screen['name']}.{screen['viewport']} | `{screen['spa_route']}` | "
                    f"{screen['as']} | {screen['status']} | {ref} | {rms} | {brand} | "
                    f"{errors if errors else '0'} |")
            add("")

            notes = {s["note"] for s in v_screens if s.get("note")}
            for note in sorted(notes):
                add(f"- Pantalla sin baseline: {note}")
            if notes:
                add("")

            explained = {s["name"] for s in v_screens if s["name"] in PARITY_NOTES}
            for name in sorted(explained):
                add(f"- **{name}** — {PARITY_NOTES[name]}")
            if explained:
                add("")

        add("### Tráfico al contrato legacy")
        add("")
        offenders = [s for s in v_screens if s["legacy_requests"]]
        if not v_screens:
            add("Sin pantallas propias en esta vertical.")
        elif not offenders:
            add("**Cero.** Ninguna de las pantallas de esta vertical pidió un endpoint "
                "marcado `retire` en la matriz de TASK-034 ni un asset de "
                "`/static/`. Medido sobre "
                f"{sum(len(s['requests']) for s in v_screens)} peticiones distintas.")
        else:
            for screen in offenders:
                for offender in screen["legacy_requests"]:
                    add(f"- `{screen['name']}.{screen['viewport']}` → "
                        f"`{offender['method']} {offender['path']}` "
                        f"({offender['resource_type']}) — {offender['reason']}")
        add("")

        if v_api or v_guards:
            add("### Permisos por rol")
            add("")
            if v_api:
                add("| Endpoint | Derecho | anon | student | recruiter | admin | |")
                add("| --- | --- | --- | --- | --- | --- | --- |")
                for entry in sorted(v_api, key=lambda e: e["path"]):
                    if entry.get("skipped"):
                        add(f"| `{entry['path']}` | {entry['actor_spec']} | — | — | — | — | "
                            f"omitido: {entry['skipped']} |")
                        continue
                    observed = entry["observed"]
                    mark = "✗" if entry["violations"] else "✓"
                    add(f"| `{entry['path']}` | {entry['actor_spec']} | "
                        f"{observed['anonymous']} | {observed['student']} | "
                        f"{observed['recruiter']} | {observed['admin']} | {mark} |")
                add("")
                for entry in v_api:
                    for violation in entry.get("violations", []):
                        add(f"- ✗ **`{entry['path']}`**: {violation}")
                for entry in v_api:
                    for error in entry.get("server_errors", []):
                        add(f"- ⚠ **`{entry['path']}`**: {error} — un actor con "
                            "derecho recibe un error de servidor. No es un fallo de "
                            "permisos, pero rompe la pantalla que lo consume.")
                scoped_any = [e for e in v_api if e.get("resource_scoped")]
                if scoped_any:
                    add("")
                    add("Denegaciones por recurso (correctas: el actor es del tipo "
                        "adecuado pero no tiene acceso a *esa* fila):")
                    for entry in scoped_any:
                        for note in entry["resource_scoped"]:
                            add(f"- `{entry['path']}` — {note}")
                add("")
            if v_guards:
                add("Guards del SPA (a dónde aterriza quien no es dueño de la ruta):")
                add("")
                add("| Ruta | Dueño | anon | student | recruiter | admin |")
                add("| --- | --- | --- | --- | --- | --- |")
                for route in sorted({g["route"] for g in v_guards}):
                    row = {g["caller"]: g["landed"] for g in v_guards if g["route"] == route}
                    owner = next(g["owner"] for g in v_guards if g["route"] == route)
                    add(f"| `{route}` | {owner} | `{row['anonymous']}` | `{row['student']}` | "
                        f"`{row['recruiter']}` | `{row['admin']}` |")
                add("")

    findings = [f for f in OPEN_FINDINGS]
    if findings:
        add("## Hallazgos")
        add("")
        for finding in findings:
            add(f"### {finding['vertical']} — {finding['title']}")
            add("")
            add(finding["body"])
            add("")

    add("## Lo que esto no demuestra")
    add("")
    add("- **Que ningún otro consumidor use el contrato legacy.** Esto mide lo que "
        "pide el SPA, que es lo que dice el criterio («cero tráfico *del "
        "frontend*»). Que nadie más lo llame solo se sabe con el servicio "
        "desplegado y sus logs: TASK-056/057, y es la condición de TASK-059.")
    add("- **Paridad visual pixel a pixel.** La migración cambió el DOM y el motor "
        "de layout; `layout_rms` ordena la revisión humana sobre "
        "`sidebyside/`, no la sustituye. Lo exigible de ADR-002 —que la paleta "
        "de marca no se rediseñó— sí se comprueba, en la columna «Marca».")
    add("- **Que los datos reales se vean bien.** La semilla es sintética y tiene "
        "una fila por forma; un fallo que solo aparece con mil filas no está aquí.")
    add("")
    return "\n".join(lines)


def main() -> int:
    import asyncio

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="limitar a una vertical, p. ej. V1-TASK-046")
    parser.add_argument("--skip-screens", action="store_true",
                        help="solo el barrido de permisos, sin navegador")
    args = parser.parse_args()

    if not (DIST_DIR / "index.html").is_file():
        raise SystemExit(
            f"no hay bundle en {DIST_DIR}. Constrúyelo antes:\n"
            "  cd frontend && npm run build"
        )

    targets = tuple(SCREEN_MAP) + tuple(SPA_ONLY)
    if args.only:
        targets = tuple(t for t in targets if t["vertical"] == args.only)
        if not targets:
            raise SystemExit(f"--only {args.only} no casa con ninguna vertical")

    print("Sembrando la base sintética de la baseline…")
    asyncio.run(baseline.create_schema())
    asyncio.run(baseline.seed())

    port = baseline.free_port()
    base_url = f"http://127.0.0.1:{port}"
    baseline.allow_test_service(base_url)
    mirror = SpaMirror(baseline.app, DIST_DIR)

    PARITY_DIR.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {"screens": [], "api_permissions": [], "ui_guards": []}

    with MirrorServer(mirror, port):
        print(f"Espejo de Nginx en {base_url} (bundle + API, un solo origen)")
        jars = login_all(base_url)
        print(f"Sesiones: {', '.join(sorted(jars))}")

        print("Barriendo permisos de la API por rol…")
        data["api_permissions"] = sweep_api_permissions(base_url, jars)
        if args.only:
            data["api_permissions"] = [
                e for e in data["api_permissions"] if e.get("vertical") == args.only
            ]

        if not args.skip_screens:
            print(f"Capturando {len(targets)} pantallas × {len(baseline.VIEWPORTS)} viewports…")
            data["screens"] = capture_spa(base_url, jars, targets, PARITY_DIR / "screens")

            print("Comprobando guards del SPA por rol…")
            guards = sweep_ui_guards(base_url, jars)
            if args.only:
                guards = [g for g in guards if g["vertical"] == args.only]
            data["ui_guards"] = guards

    # La comparación no necesita el servidor: son dos PNG en disco.
    if data["screens"]:
        print("Comparando contra la baseline…")
        for screen in data["screens"]:
            if not screen["baseline"]:
                continue
            reference = BASELINE_SCREENS / f"{screen['baseline']}.{screen['viewport']}.png"
            produced = PARITY_DIR / "screens" / f"{screen['name']}.{screen['viewport']}.png"
            if not reference.is_file():
                screen["comparison"] = None
                screen["comparison_note"] = (
                    f"falta {reference.relative_to(REPO_ROOT)}; los PNG de la baseline "
                    "no se versionan (ver su README): regenérala con capture_baseline.py"
                )
                continue
            screen["comparison"] = compare(reference, produced)
            side_by_side(
                reference, produced,
                PARITY_DIR / "sidebyside" / f"{screen['name']}.{screen['viewport']}.png",
                f"{screen['name']} · {screen['viewport']}",
            )

    data["screens_without_spa"] = list(SCREENS_WITHOUT_SPA)
    (PARITY_DIR / "report.json").write_text(json.dumps(data, indent=2, default=str) + "\n")
    (PARITY_DIR / "REPORT.md").write_text(build_report(data))

    legacy = sum(len(s["legacy_requests"]) for s in data["screens"])
    violations = sum(len(e.get("violations", [])) for e in data["api_permissions"])
    print()
    print(f"  peticiones al contrato legacy : {legacy}")
    print(f"  violaciones de permisos       : {violations}")
    print(f"  informe                       : {(PARITY_DIR / 'REPORT.md').relative_to(REPO_ROOT)}")
    return 0 if (legacy == 0 and violations == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
