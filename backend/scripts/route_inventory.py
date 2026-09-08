"""Inventario de handlers HTTP generado desde la app FastAPI.

Origen: TASK-034 del tablero de refactor (docs/refactor/TASKS.md). El plan 08
cuenta 150 handlers pero solo tabula 19 correspondencias con el contrato REST
objetivo; sin el mapa completo, "cero tráfico legacy" no es verificable.

El inventario se lee de las rutas realmente registradas en `app.app.app`, no de
un grep sobre los decoradores: lo que importa es el prefijo efectivo con el que
queda montado cada router y las dependencias que FastAPI resuelve de verdad,
incluidas las heredadas del router. El actor sale del árbol `route.dependant`
recorrido en profundidad, así que una dependencia de auth anidada dentro de otra
también cuenta.

Uso:

    cd backend && ../.venv/bin/python scripts/route_inventory.py

Escribe docs/refactor/route_inventory.json y docs/refactor/route_inventory.csv.
Es reejecutable y determinista: mismo código, mismo artefacto.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable

# Dos raíces desde TASK-037: el código Python vive bajo `backend/` y los
# documentos de la migración siguen en la raíz del repositorio, que es de todo
# el monorepo y no solo del backend.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

# El aislamiento debe correr antes de importar cualquier módulo de `app`: app.db
# y app.app llaman load_dotenv() y construyen el engine en tiempo de import.
# Reusamos el de los tests para que este script no lea credenciales reales ni
# abra sockets, igual que la lane rápida.
from tests.isolation import apply_isolation  # noqa: E402

apply_isolation()

from fastapi.responses import HTMLResponse, RedirectResponse  # noqa: E402
from fastapi.routing import APIRoute  # noqa: E402
from starlette.routing import Mount, Route as StarletteRoute  # noqa: E402

from app.app import app  # noqa: E402


# --- Actores ---------------------------------------------------------------
# Las dependencias de auth no se pueden identificar por `__name__`: las que crea
# `fastapi_users.current_user(...)` son closures llamados todos
# `current_user_dependency`. Se mapean por identidad del objeto, tomándolas del
# módulo donde están declaradas, que es el mismo objeto que las rutas reciben.
from app.services.accounts import userService as _user_service  # noqa: E402
from app.services.admin import adminService as _admin_service  # noqa: E402
from app.services.companies import companyService as _company_service  # noqa: E402

_ACTOR_SOURCES: tuple[tuple[Any, str, str], ...] = (
    (_user_service, "current_active_user", "student"),
    (_user_service, "current_ai_user", "student"),
    (_user_service, "current_active_user_optional", "student:optional"),
    (_admin_service, "current_admin_user", "admin"),
    (_company_service, "current_active_company", "company"),
    (_company_service, "current_active_company_optional", "company:optional"),
    (_company_service, "current_active_company_recruiter", "recruiter"),
    (_company_service, "current_active_company_recruiter_optional", "recruiter:optional"),
    (_company_service, "current_company_job_manager_recruiter", "recruiter:job_manager"),
    (_company_service, "current_company_owner_recruiter", "recruiter:owner"),
)

ACTOR_BY_ID: dict[int, tuple[str, str]] = {}
for _module, _attr, _actor in _ACTOR_SOURCES:
    _dep = getattr(_module, _attr)
    ACTOR_BY_ID[id(_dep)] = (_attr, _actor)

# Dependencias que no dicen nada sobre el actor: infraestructura, no identidad.
NON_ACTOR_DEPENDENCY_NAMES = {
    "get_session",
    "_get_service",
    "require_same_origin_for_write",
    # Cuerpo/parámetros de fastapi-users, no identidad.
    "get_user_manager",
    "get_company_recruiter_manager",
}

# Rutas generadas por fastapi-users. Sus dependencias de auth son closures
# creados dentro de `get_logout_router` / `get_users_router`, sin ningún objeto
# alcanzable desde un módulo con el que compararlas por identidad. Se declaran
# aquí una a una, con el actor leído del propio paquete instalado
# (fastapi_users/router/users.py: `/me` usa `current_user(active=True)`;
# `/{id}` añade `superuser=True`, que en este dominio es `is_superuser`, la
# misma condición que exige `current_admin_user`).
GENERATED_ROUTER_ACTOR_OVERRIDES = {
    ("POST", "/auth/jwt/logout"): ("current_user_token_dependency", "student"),
    # Mismo router generado, montado tambien bajo /api/v1 por TASK-042.
    ("POST", "/api/v1/auth/student/logout"): ("current_user_token_dependency", "student"),
    ("POST", "/api/v1/auth/company/logout"): ("current_user_token_dependency", "recruiter"),
    ("GET", "/api/v1/users/me"): ("fastapi_users:current_active_user", "student"),
    ("PATCH", "/api/v1/users/me"): ("fastapi_users:current_active_user", "student"),
    ("GET", "/api/v1/users/{id}"): ("fastapi_users:current_superuser", "admin"),
    ("PATCH", "/api/v1/users/{id}"): ("fastapi_users:current_superuser", "admin"),
    ("DELETE", "/api/v1/users/{id}"): ("fastapi_users:current_superuser", "admin"),
}

ACTOR_PRECEDENCE = [
    "admin",
    "recruiter:owner",
    "recruiter:job_manager",
    "recruiter",
    "company",
    "student",
    "recruiter:optional",
    "company:optional",
    "student:optional",
]


def _walk_dependants(dependant: Any) -> Iterable[Any]:
    """Recorre el árbol de dependencias resuelto por FastAPI, en profundidad."""
    for sub in dependant.dependencies:
        yield sub
        yield from _walk_dependants(sub)


def _classify_actor(route: APIRoute) -> tuple[str, list[str]]:
    """Devuelve (actor requerido, dependencias de auth encontradas).

    Cuando un handler exige varias identidades se queda la más restrictiva por
    ACTOR_PRECEDENCE: es la que decide de verdad quién puede entrar. Una
    dependencia desconocida sale como UNKNOWN y hace fallar el script, en vez de
    colarse silenciosamente como pública.
    """
    found: set[tuple[str, str]] = set()
    unknown: set[str] = set()

    overridden = False
    for method in route.methods or []:
        override = GENERATED_ROUTER_ACTOR_OVERRIDES.get((method, route.path))
        if override:
            found.add(override)
            overridden = True

    for sub in _walk_dependants(route.dependant):
        call = getattr(sub, "call", None)
        if call is None:
            continue
        mapped = ACTOR_BY_ID.get(id(call))
        if mapped:
            found.add(mapped)
            continue
        name = getattr(call, "__name__", "") or ""
        if name in NON_ACTOR_DEPENDENCY_NAMES:
            continue
        if overridden:
            # La tabla ya declaró el actor de esta ruta generada; sus closures
            # internos no aportan nada y no deben contarse como desconocidos.
            continue
        if name.startswith("current_") or name.startswith("require_"):
            unknown.add(name)

    auth_deps = sorted({name for name, _ in found})
    if unknown:
        return f"UNKNOWN:{','.join(sorted(unknown))}", auth_deps
    if not found:
        return "public", auth_deps
    actors = {actor for _, actor in found}
    for candidate in ACTOR_PRECEDENCE:
        if candidate in actors:
            return candidate, auth_deps
    return "public", auth_deps


def _kind(route: APIRoute) -> str:
    """Vista HTML/redirect frente a endpoint de API JSON."""
    response_class = getattr(route, "response_class", None)
    klass = getattr(response_class, "value", response_class)
    if isinstance(klass, type) and issubclass(klass, (HTMLResponse, RedirectResponse)):
        return "view"
    module = getattr(route.endpoint, "__module__", "") or ""
    if module.startswith("app.views"):
        return "view"
    return "api"


# --- Consumidores ----------------------------------------------------------

CONSUMER_GLOBS = (
    ("template", "app/templates", "*.html"),
    ("js", "app/static", "*.js"),
)


def _load_consumer_sources() -> list[tuple[str, str, str]]:
    sources: list[tuple[str, str, str]] = []
    for kind, root, pattern in CONSUMER_GLOBS:
        for path in sorted((BACKEND_ROOT / root).rglob(pattern)):
            sources.append((kind, str(path.relative_to(BACKEND_ROOT)), path.read_text(errors="replace")))
    return sources


def _search_fragments(path: str) -> list[str]:
    """Fragmentos buscables de una ruta, del más específico al más genérico.

    Un JS que hace `fetch(`${API}/users/${id}/toggle-active`)` sobre
    `const API = '/api/v1/admin'` no contiene ninguna ruta completa literal; sí
    contiene `/api/v1/admin`. Buscar solo el path entero da falsos «sin
    consumidor». Se prueba el path completo, luego el prefijo anterior al primer
    parámetro, y después se va recortando por segmentos hasta
    `/api/v1/<recurso>`, que es el suelo: por debajo el fragmento deja de
    identificar al handler.
    """
    fragments: list[str] = [path]
    head = path.split("{", 1)[0].rstrip("/")
    if head and head != path:
        fragments.append(head)

    segments = [seg for seg in head.split("/") if seg]
    # El suelo es prefijo de API más un segmento de recurso, o la raíz de la
    # vista si no está bajo /api/v1.
    floor = 3 if segments[:2] == ["api", "v1"] else 1
    for cut in range(len(segments) - 1, floor - 1, -1):
        candidate = "/" + "/".join(segments[:cut])
        if candidate not in fragments:
            fragments.append(candidate)
    return fragments


def _find_consumers(path: str, sources: list[tuple[str, str, str]]) -> tuple[list[str], str, str]:
    """(consumidores, tipo de coincidencia, fragmento que coincidió).

    Devolver el fragmento hace auditable el resultado: una coincidencia por
    prefijo se puede verificar a mano sin releer el script.
    """
    for index, fragment in enumerate(_search_fragments(path)):
        hits = sorted({rel for _, rel, text in sources if fragment in text})
        if hits:
            return hits, ("exact" if index == 0 else "prefix"), fragment
    return [], "none", ""


# --- Destinos --------------------------------------------------------------
# El destino de cada handler no es derivable del código: es una decisión de
# diseño. Vive en docs/refactor/route_targets.csv, versionado y revisable, y el
# script solo lo cruza. La comprobación es en las dos direcciones —ningún
# handler sin decisión, ninguna decisión huérfana— para que "ningún handler
# queda sin clasificar" sea un check y no una afirmación.

TARGETS_CSV = REPO_ROOT / "docs" / "refactor" / "route_targets.csv"

VALID_DESTINATIONS = {
    "rest",      # queda en el contrato REST público que consume React
    "internal",  # endpoint interno autenticado; ninguna pantalla lo llama
    "retire",    # se retira en el cutover (TASK-059)
    "platform",  # lo genera el framework; no es contrato de dominio
}


def _load_targets() -> dict[tuple[str, str], dict[str, str]]:
    with TARGETS_CSV.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    targets: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = (row["method"].strip(), row["path"].strip())
        if key in targets:
            raise SystemExit(f"route_targets.csv: fila duplicada para {key[0]} {key[1]}")
        if row["destination"] not in VALID_DESTINATIONS:
            raise SystemExit(
                f"route_targets.csv: destino '{row['destination']}' no válido en {key[0]} {key[1]}"
            )
        targets[key] = row
    return targets


# --- Recolección -----------------------------------------------------------


def collect() -> list[dict[str, Any]]:
    sources = _load_consumer_sources()
    targets = _load_targets()
    rows: list[dict[str, Any]] = []
    for route in app.routes:
        if isinstance(route, Mount):
            continue
        if not isinstance(route, APIRoute):
            # Rutas Starlette planas (StaticFiles, favicon) no son handlers de
            # dominio; se listan aparte para que el total cuadre.
            if isinstance(route, StarletteRoute):
                rows.append(
                    {
                        "methods": sorted(route.methods or []),
                        "path": route.path,
                        "name": route.name,
                        "module": getattr(route.endpoint, "__module__", ""),
                        "kind": "asset",
                        "actor": "public",
                        "auth_dependencies": [],
                        "response_model": None,
                        "tags": [],
                        "consumers": [],
                        "consumer_match": "none",
                        "consumer_match_fragment": "",
                    }
                )
            continue

        actor, auth_deps = _classify_actor(route)
        consumers, match, fragment = _find_consumers(route.path, sources)
        response_model = getattr(route, "response_model", None)
        rows.append(
            {
                "methods": sorted(m for m in (route.methods or []) if m != "HEAD"),
                "path": route.path,
                "name": route.name,
                "module": getattr(route.endpoint, "__module__", ""),
                "kind": _kind(route),
                "actor": actor,
                "auth_dependencies": auth_deps,
                "response_model": getattr(response_model, "__name__", None)
                or (str(response_model) if response_model is not None else None),
                "tags": list(route.tags or []),
                "consumers": consumers,
                "consumer_match": match,
                "consumer_match_fragment": fragment,
            }
        )
    # Cruce con la tabla de decisión. HEAD no se decide: FastAPI lo deriva del GET.
    missing: list[str] = []
    for r in rows:
        decisions = {}
        for method in r["methods"]:
            if method == "HEAD":
                continue
            row = targets.pop((method, r["path"]), None)
            if row is None:
                missing.append(f"{method} {r['path']}")
                continue
            decisions[method] = {
                "destination": row["destination"],
                "target": row["target"],
                "vertical": row["vertical"],
                "note": row["note"],
            }
        r["decisions"] = decisions

    if missing:
        raise SystemExit(
            "route_targets.csv no cubre estos handlers:\n  " + "\n  ".join(sorted(missing))
        )
    if targets:
        raise SystemExit(
            "route_targets.csv decide sobre handlers que ya no existen:\n  "
            + "\n  ".join(f"{m} {p}" for m, p in sorted(targets))
        )

    rows.sort(key=lambda r: (r["path"], ",".join(r["methods"])))
    return rows


def main() -> int:
    rows = collect()
    out_dir = REPO_ROOT / "docs" / "refactor"

    payload = {
        "generated_by": "backend/scripts/route_inventory.py",
        "task": "TASK-034",
        "handler_count": len(rows),
        "handlers": rows,
    }
    (out_dir / "route_inventory.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    with (out_dir / "route_inventory.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "method", "path", "name", "kind", "actor", "auth_dependencies", "response_model",
                "module", "consumer_match", "consumer_match_fragment", "consumers",
                "destination", "target", "vertical", "note",
            ]
        )
        for r in rows:
            for method, decision in sorted(r["decisions"].items()):
                writer.writerow(
                    [
                        method,
                        r["path"],
                        r["name"],
                        r["kind"],
                        r["actor"],
                        "|".join(r["auth_dependencies"]),
                        r["response_model"] or "",
                        r["module"],
                        r["consumer_match"],
                        r["consumer_match_fragment"],
                        "|".join(r["consumers"]),
                        decision["destination"],
                        decision["target"],
                        decision["vertical"],
                        decision["note"],
                    ]
                )

    by_kind: dict[str, int] = {}
    by_actor: dict[str, int] = {}
    for r in rows:
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1
        by_actor[r["actor"]] = by_actor.get(r["actor"], 0) + 1
    by_destination: dict[str, int] = {}
    for r in rows:
        for decision in r["decisions"].values():
            by_destination[decision["destination"]] = by_destination.get(decision["destination"], 0) + 1
    print(f"handlers: {len(rows)}")
    print("por destino: " + ", ".join(f"{k}={v}" for k, v in sorted(by_destination.items())))
    print("por tipo:  " + ", ".join(f"{k}={v}" for k, v in sorted(by_kind.items())))
    print("por actor: " + ", ".join(f"{k}={v}" for k, v in sorted(by_actor.items())))
    unknown = [r for r in rows if r["actor"].startswith("UNKNOWN")]
    if unknown:
        print(f"SIN CLASIFICAR: {len(unknown)}", file=sys.stderr)
        for r in unknown:
            print(f"  {','.join(r['methods'])} {r['path']} -> {r['actor']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
