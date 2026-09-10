"""El OpenAPI como contrato verificable (TASK-043).

El plan 08 §5.1 declara el OpenAPI fuente de verdad y §14 pone «el contrato
cambia sin detectar» como riesgo. Esta suite es la parte del control que corre en
la lane rápida:

* el documento versionado en `contract/openapi.json` es el de *este* commit —si
  alguien cambia una ruta y no lo regenera, falla aquí y no tres jobs después,
  cuando los tipos del frontend ya se generaron de un contrato viejo;
* exportarlo dos veces da exactamente los mismos bytes;
* los `operationId` son únicos y no dependen de la URL;
* el error model de TASK-040 está publicado, con su catálogo entero.

La comparación entre ramas —qué cambió y si rompe— la hace
`scripts/check_openapi_compat.py`, cuyas reglas se ejercitan al final del
fichero con documentos mínimos escritos a mano: sobre el OpenAPI real no se
puede provocar un cambio incompatible sin romper la aplicación.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.utils import generate_unique_id

from app.app import app
from app.core.errors import ErrorCode
from app.core.openapi import (
    ERROR_SCHEMA_NAME,
    assert_unique_operation_ids,
    stable_operation_id,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
CONTRACT = REPO_ROOT / "contract" / "openapi.json"
EXPORT_SCRIPT = BACKEND_ROOT / "scripts" / "export_openapi.py"


def _load_compat_module() -> Any:
    """Importa el comparador, que vive en `scripts/` y no es un paquete."""
    path = BACKEND_ROOT / "scripts" / "check_openapi_compat.py"
    spec = importlib.util.spec_from_file_location("check_openapi_compat", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Registrado antes de ejecutarlo: `@dataclass` resuelve anotaciones contra
    # `sys.modules[cls.__module__]` y sin esto no encuentra su propio módulo.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


compat = _load_compat_module()


# --- el documento versionado -----------------------------------------------


def test_versioned_contract_is_the_one_this_commit_serves():
    """`contract/openapi.json` describe la app de este commit, no la de ayer.

    De este fichero salen los tipos TypeScript del frontend. Si se queda atrás,
    el frontend compila contra un contrato que la API ya no sirve y el error
    aparece en el navegador, que es exactamente lo que esta tarea evita.
    """
    assert CONTRACT.exists(), (
        f"falta {CONTRACT.relative_to(REPO_ROOT)}: regenerarlo con "
        "`cd backend && python scripts/export_openapi.py -o ../contract/openapi.json`"
    )
    expected = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert app.openapi() == expected, (
        "el contrato versionado no coincide con el que sirve la app. Regenerar "
        "con `cd backend && python scripts/export_openapi.py -o ../contract/openapi.json` "
        "y los tipos con `cd frontend && npm run api:types`."
    )


def test_export_is_byte_identical_across_runs(tmp_path):
    """Dos exports seguidos dan el mismo fichero: el artefacto es reproducible."""
    first, second = tmp_path / "one.json", tmp_path / "two.json"
    for target in (first, second):
        subprocess.run(
            [sys.executable, str(EXPORT_SCRIPT), "-o", str(target)],
            cwd=BACKEND_ROOT,
            check=True,
            capture_output=True,
        )
    assert first.read_bytes() == second.read_bytes()


# --- operationId ------------------------------------------------------------


def test_operation_ids_are_unique():
    assert_unique_operation_ids(app)


def test_every_operation_id_comes_from_the_stable_scheme():
    """El documento no tiene ni un `operationId` heredado del default de FastAPI.

    El default es ``{handler}{path}_{método}``, con la URL dentro del nombre. Se
    comprueba contra la función de FastAPI, no contra una heurística sobre el
    texto: `posts_get_all_posts` contiene «posts» porque ese es su tag, no
    porque lleve la URL pegada.
    """
    ids = {
        operation["operationId"]
        for item in app.openapi()["paths"].values()
        for method, operation in item.items()
        if method in {"get", "put", "post", "delete", "patch"}
    }
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.include_in_schema:
            continue
        assert stable_operation_id(route) in ids
        assert generate_unique_id(route) not in ids


def test_renaming_a_path_does_not_rename_the_operation():
    """La propiedad que sostiene todo lo demás: el id no mira el path.

    §5.2 mueve URLs vertical por vertical. Cada uno de esos movimientos habría
    renombrado un tipo del frontend y habría aparecido en el check de
    compatibilidad como «operación retirada + operación nueva».
    """
    before, after = FastAPI(), FastAPI()

    @before.get("/students_dashboard", tags=["dashboard"])
    def read_student_dashboard():  # pragma: no cover - nunca se llama
        return {}

    @after.get("/dashboard/student", tags=["dashboard"])
    def read_student_dashboard():  # noqa: F811 - el mismo handler en otra URL
        return {}  # pragma: no cover - nunca se llama

    def only_id(application: FastAPI) -> str:
        route = next(r for r in application.routes if isinstance(r, APIRoute))
        return stable_operation_id(route)

    assert only_id(before) == only_id(after) == "dashboard_read_student_dashboard"
    # Y el default de FastAPI sí habría cambiado, que es de lo que se huye.
    routes = [next(r for r in a.routes if isinstance(r, APIRoute)) for a in (before, after)]
    assert generate_unique_id(routes[0]) != generate_unique_id(routes[1])


def test_operation_id_namespaces_by_tag():
    class _Route:
        def __init__(self, tags, name):
            self.tags = tags
            self.name = name

    assert stable_operation_id(_Route(["admin"], "list_users")) == "admin_list_users"
    assert stable_operation_id(_Route(["jobs"], "toggle-active")) == "jobs_toggle_active"
    # Los routers de fastapi-users traen su propio namespace en el nombre.
    assert stable_operation_id(_Route(["auth"], "auth:jwt.login")) == "auth_jwt_login"
    # Sin tag hay namespace igualmente: un `operationId` feo se ve, un choque no.
    assert stable_operation_id(_Route([], "whatever")) == "default_whatever"


def test_duplicate_operation_ids_are_refused():
    """Dos operaciones con el mismo id colapsarían en un solo tipo generado."""
    colliding = FastAPI()

    @colliding.get("/one", tags=["thing"], name="read")
    def _one():  # pragma: no cover - nunca se llama
        return {}

    @colliding.get("/two", tags=["thing"], name="read")
    def _two():  # pragma: no cover - nunca se llama
        return {}

    with pytest.raises(RuntimeError, match="operationId duplicado"):
        assert_unique_operation_ids(colliding)


# --- el error model de TASK-040, publicado ----------------------------------


def test_every_api_operation_documents_the_error_envelope():
    document = app.openapi()
    reference = f"#/components/schemas/{ERROR_SCHEMA_NAME}"
    checked = 0
    for path, item in document["paths"].items():
        if not path.startswith("/api/v1"):
            continue
        for method, operation in item.items():
            if method not in {"get", "put", "post", "delete", "patch"}:
                continue
            error = operation["responses"]["default"]
            assert error["content"]["application/json"]["schema"]["$ref"] == reference
            checked += 1
    assert checked > 100, "se documentaron muy pocas operaciones: revisar el filtro"


def test_the_published_catalogue_is_the_whole_catalogue():
    """Cada `ErrorCode` viaja al cliente; ninguno se queda sin publicar.

    Es lo que convierte quitar un código en un diff incompatible detectable: sin
    el enum en el documento, borrar un miembro del `StrEnum` no dejaba rastro en
    el contrato.
    """
    published = app.openapi()["components"]["schemas"]["ErrorCode"]["enum"]
    assert set(published) == {code.value for code in ErrorCode}


def test_views_are_not_given_an_api_error_response():
    """Las páginas Jinja devuelven HTML; el envelope es de `/api/v1`."""
    document = app.openapi()
    assert "default" not in document["paths"]["/about"]["get"]["responses"]


# --- el comparador de contratos ---------------------------------------------
#
# Documentos mínimos escritos a mano: la Validation de la ficha pide provocar un
# cambio incompatible y uno aditivo y comprobar el veredicto de cada uno. Sobre
# el OpenAPI real eso significaría romper la aplicación para ver fallar el check.


def _document(operation: dict[str, Any], path: str = "/api/v1/things") -> dict[str, Any]:
    return {"openapi": "3.1.0", "paths": {path: {"get": operation}}}


def _reading(schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "operationId": "things_read",
        "responses": {"200": {"content": {"application/json": {"schema": schema}}}},
    }


def _writing(schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "operationId": "things_write",
        "requestBody": {"content": {"application/json": {"schema": schema}}},
        "responses": {"200": {"description": "ok"}},
    }


def _verdict(base: dict[str, Any], head: dict[str, Any]):
    return compat.compare_documents(base, head)


def test_identical_documents_are_compatible():
    document = app.openapi()
    assert _verdict(document, json.loads(json.dumps(document))).breaking == []


def test_removing_a_required_response_field_breaks():
    base = _document(_reading({"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}}))
    head = _document(_reading({"type": "object", "properties": {}}))
    report = _verdict(base, head)
    assert report.breaking
    assert "desapareció de la respuesta" in " ".join(report.breaking)


def test_reducing_an_enum_breaks():
    base = _document(_reading({"type": "string", "enum": ["draft", "sent", "closed"]}))
    head = _document(_reading({"type": "string", "enum": ["draft", "sent"]}))
    report = _verdict(base, head)
    assert report.breaking
    assert "closed" in " ".join(report.breaking)


def test_adding_an_enum_value_is_additive():
    base = _document(_reading({"type": "string", "enum": ["draft"]}))
    head = _document(_reading({"type": "string", "enum": ["draft", "sent"]}))
    report = _verdict(base, head)
    assert report.breaking == []
    assert report.compatible


def test_a_new_required_request_field_breaks():
    body = {"type": "object", "properties": {"title": {"type": "string"}}}
    base = _document(_writing(body))
    head = _document(_writing({**body, "required": ["title"]}))
    report = _verdict(base, head)
    assert any("obligatoria" in line for line in report.breaking)


def test_a_new_optional_request_field_is_additive():
    base = _document(_writing({"type": "object", "properties": {"title": {"type": "string"}}}))
    head = _document(
        _writing(
            {
                "type": "object",
                "properties": {"title": {"type": "string"}, "note": {"type": "string"}},
            }
        )
    )
    assert _verdict(base, head).breaking == []


def test_a_new_operation_is_additive():
    base = _document(_reading({"type": "object"}))
    head = _document(_reading({"type": "object"}))
    head["paths"]["/api/v1/others"] = {"get": _reading({"type": "object"})}
    assert _verdict(base, head).breaking == []


def test_removing_an_operation_breaks_unless_it_was_deprecated():
    base = _document(_reading({"type": "object"}))
    head: dict[str, Any] = {"openapi": "3.1.0", "paths": {}}
    assert _verdict(base, head).breaking

    # §5.3: se marca deprecated, se mide un ciclo de release y luego se retira.
    deprecated = _document({**_reading({"type": "object"}), "deprecated": True})
    report = _verdict(deprecated, head)
    assert report.breaking == []
    assert any("deprecated" in line for line in report.compatible)


def test_renaming_an_operation_id_breaks():
    base = _document(_reading({"type": "object"}))
    head = _document({**_reading({"type": "object"}), "operationId": "things_read_v2"})
    assert any("operationId" in line for line in _verdict(base, head).breaking)


def test_a_new_required_query_parameter_breaks():
    base = _document(_reading({"type": "object"}))
    head = _document(_reading({"type": "object"}))
    head["paths"]["/api/v1/things"]["get"]["parameters"] = [
        {"in": "query", "name": "since", "required": True, "schema": {"type": "string"}}
    ]
    assert any("obligatorio nuevo" in line for line in _verdict(base, head).breaking)


def test_recursive_schemas_terminate():
    """Un modelo que se referencia a sí mismo no puede colgar el comparador."""
    node = {
        "openapi": "3.1.0",
        "components": {
            "schemas": {
                "Node": {
                    "type": "object",
                    "required": ["children"],
                    "properties": {
                        "children": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/Node"},
                        }
                    },
                }
            }
        },
        "paths": {
            "/api/v1/tree": {
                "get": _reading({"$ref": "#/components/schemas/Node"}),
            }
        },
    }
    other = json.loads(json.dumps(node))
    assert _verdict(node, other).breaking == []
