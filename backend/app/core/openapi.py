"""Nombres estables para las operaciones del OpenAPI.

Origen: TASK-043 del tablero de refactor (docs/refactor/TASKS.md). El plan 08
§5.1 declara el OpenAPI fuente de verdad del contrato y de él salen los tipos
TypeScript del frontend (`frontend/src/api/generated/`). El nombre de cada tipo
generado es el `operationId` de su operación, así que el `operationId` deja de
ser un detalle del documento y pasa a ser una identidad pública.

El default de FastAPI es ``f"{route.name}{path}"`` con el método pegado al
final: ``list_applications_api_v1_admin_applications_get``. Es determinista, pero
lleva la URL dentro del nombre, y §5.2 renombra URLs vertical por vertical
siguiendo la matriz de TASK-034. Con el default, mover
``/students_dashboard`` a ``/dashboard/student`` renombraría el tipo del
frontend sin que el contrato de esa operación hubiera cambiado en nada, y el
check de compatibilidad lo leería como «operación retirada + operación nueva».

Aquí el nombre se construye con lo que no cambia al renombrar una URL: el tag
que agrupa la operación y el nombre del handler.

    ``{tag}_{handler}``   →   ``admin_list_applications``, ``jobs_search_jobs``

Con una sola excepción, para los routers de ``fastapi-users``, cuyos handlers ya
traen su propio namespace (``auth:jwt.login``): si el nombre ya empieza por el
tag, no se repite, y ``auth`` + ``auth:jwt.login`` da ``auth_jwt_login`` en vez
de ``auth_auth_jwt_login``.

Dos operaciones distintas nunca pueden compartir `operationId`: los generadores
de tipos colapsarían una sobre otra en silencio. `assert_unique_operation_ids`
lo comprueba sobre la app ya montada y falla con las rutas implicadas; lo
ejercita `tests/test_openapi_contract.py`.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field, TypeAdapter

from app.core.error_handlers import API_PREFIX
from app.core.errors import ERROR_CATALOG_VERSION, ErrorCode

# Cualquier cosa que no sea alfanumérica separa palabras: ``auth:jwt.login`` y
# ``toggle-active`` tienen que caer en el mismo alfabeto que un nombre de
# función de Python, porque el resultado acaba siendo un identificador
# TypeScript.
_NON_ALNUM = re.compile(r"[^0-9a-zA-Z]+")

# Routers montados sin tag: el tag es el namespace del nombre, y sin él dos
# handlers homónimos de dominios distintos colisionarían. Se usa este valor para
# que el fallo sea un `operationId` feo y visible en vez de un IndexError.
_UNTAGGED = "default"


def _slug(value: str) -> str:
    return _NON_ALNUM.sub("_", str(value)).strip("_").lower()


def stable_operation_id(route: APIRoute) -> str:
    """Devuelve el `operationId` de una ruta: ``{tag}_{handler}``.

    No depende del path ni del método, así que renombrar una URL no renombra el
    tipo generado y el diff de contrato dice lo que de verdad cambió.
    """
    tag = _slug(route.tags[0]) if route.tags else _UNTAGGED
    name = _slug(route.name)
    if name == tag or name.startswith(f"{tag}_"):
        return name
    return f"{tag}_{name}"


def assert_unique_operation_ids(app: FastAPI) -> None:
    """Falla si dos operaciones del documento comparten `operationId`.

    Solo mira las rutas que entran en el schema: un router montado dos veces con
    ``include_in_schema=False`` en el segundo montaje —el caso de ``/auth/jwt``,
    que sostiene las páginas Jinja hasta TASK-059— aporta una sola operación al
    contrato y no es una colisión.
    """
    seen: dict[str, list[str]] = defaultdict(list)
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.include_in_schema:
            continue
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            seen[route.operation_id or stable_operation_id(route)].append(
                f"{method} {route.path}"
            )

    collisions = {name: paths for name, paths in seen.items() if len(paths) > 1}
    if collisions:
        detail = "; ".join(
            f"{name} <- {', '.join(paths)}" for name, paths in sorted(collisions.items())
        )
        raise RuntimeError(
            "operationId duplicado en el OpenAPI: los tipos generados de estas "
            f"operaciones se pisarían entre sí. {detail}"
        )


# --- el error model de TASK-040, publicado en el contrato ---------------------
#
# Los handlers de `app/core/error_handlers.py` responden por fuera de los
# `response_model` de las rutas, así que FastAPI no documenta ni una sola de sus
# respuestas: hoy el cliente ve `unknown` donde el plan 08 §5.1 define una forma
# fija. TASK-040 dejó el encargo escrito en `ErrorCode` —«the catalogue can be
# enumerated for the OpenAPI contract that TASK-043 pins»— y es este el sitio.
#
# Publicarlo tiene un segundo efecto, buscado: el catálogo de códigos entra en el
# documento como un enum, y retirar un código pasa a ser un diff incompatible que
# `scripts/check_openapi_compat.py` detiene. Antes era una línea borrada en un
# StrEnum.


class ApiErrorDetail(BaseModel):
    """El contenido de `error`. Las cuatro claves viajan siempre."""

    code: ErrorCode = Field(description="Código estable del catálogo. Nunca se reescribe.")
    message: str = Field(description="Texto seguro para enseñar. Puede reescribirse o traducirse.")
    #: Sin default a propósito: la clave viaja siempre, con `null` dentro cuando
    #: no hay nada que contar. Un default la sacaría de `required` y el cliente
    #: tendría que distinguir «ausente» de «vacía», que es justo lo que
    #: `app/core/errors.py` evita.
    details: Any = Field(
        description=(
            "Específico legible por máquina: qué campo falló, qué límite se "
            "superó. `null` cuando no hay ninguno, para que «sin detalles» y "
            "«detalles vacíos» no se confundan."
        )
    )
    request_id: str = Field(
        description="Referencia con la que este fallo aparece en los logs del servidor."
    )


class ApiErrorResponse(BaseModel):
    """La única forma de cuerpo de error bajo `/api/v1` (plan 08 §5.1)."""

    error: ApiErrorDetail


#: Nombre del componente en `components/schemas`, y por tanto del tipo generado.
ERROR_SCHEMA_NAME = "ApiErrorResponse"

_ERROR_RESPONSE_KEY = "default"


def document_error_contract(app: FastAPI) -> None:
    """Añade la respuesta de error a toda operación bajo `/api/v1`.

    Se hace envolviendo `app.openapi()` en vez de repetir un `responses={...}`
    en 175 decoradores: la forma es una, se decide en un sitio, y una ruta nueva
    la hereda sin acordarse de nada. Se declara como respuesta ``default`` —«el
    resto de códigos»— porque los handlers responden con el status que traiga el
    fallo y enumerarlos operación por operación sería inventar cuáles puede dar
    cada una.
    """
    build_schema = app.openapi

    def openapi() -> dict[str, Any]:
        schema = build_schema()
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        if ERROR_SCHEMA_NAME in components:
            # `build_schema` cachea en `app.openapi_schema` y devuelve el mismo
            # objeto: sin esta guarda, la segunda llamada inyectaría encima.
            return schema

        for name, model in (
            (ERROR_SCHEMA_NAME, ApiErrorResponse),
            ("ApiErrorDetail", ApiErrorDetail),
            ("ErrorCode", ErrorCode),
        ):
            components[name] = _model_schema(model, name)
        # El docstring de `ErrorCode` habla de por qué existe el enum, que le
        # importa a quien lee el backend. Al cliente le importa qué puede hacer
        # con un código que no conoce, y eso es lo que se publica.
        components["ErrorCode"]["description"] = (
            f"Catálogo de códigos de error, versión {ERROR_CATALOG_VERSION}. Un "
            "código no se reescribe nunca; añadir uno es compatible, y un cliente "
            "que reciba uno que no conoce debe recurrir a la familia del status."
        )

        reference = f"#/components/schemas/{ERROR_SCHEMA_NAME}"
        description = (
            "Fallo. El cuerpo es siempre el error model de `/api/v1`: `code` del "
            f"catálogo (versión {ERROR_CATALOG_VERSION}), `message` seguro, "
            "`details` opcional y `request_id` correlacionable con el log."
        )
        for path, item in (schema.get("paths") or {}).items():
            if not path.startswith(API_PREFIX):
                continue
            for method, operation in item.items():
                if method in {"get", "put", "post", "delete", "patch"}:
                    operation.setdefault("responses", {})[_ERROR_RESPONSE_KEY] = {
                        "description": description,
                        # Un dict nuevo por operación: compartir el mismo objeto
                        # entre 175 respuestas convierte cualquier retoque
                        # posterior en un cambio global silencioso.
                        "content": {"application/json": {"schema": {"$ref": reference}}},
                    }
        return schema

    app.openapi = openapi  # type: ignore[method-assign]


def _model_schema(model: Any, name: str) -> dict[str, Any]:
    """Schema del modelo con las referencias apuntando a `components/schemas`.

    `TypeAdapter` en vez de `model_json_schema` porque uno de los tres no es un
    modelo sino el `StrEnum` del catálogo, y aquí interesa exactamente el mismo
    tratamiento para los tres.
    """
    schema = TypeAdapter(model).json_schema(ref_template="#/components/schemas/{model}")
    # Los tipos anidados salen en `$defs`; en un documento OpenAPI viven en
    # `components/schemas`, que es donde ya los hemos puesto.
    schema.pop("$defs", None)
    schema.setdefault("title", name)
    return schema
