"""Compara dos documentos OpenAPI y separa lo aditivo de lo que rompe clientes.

Origen: TASK-043 del tablero de refactor (docs/refactor/TASKS.md). El plan 08
§5.1 pide que «un diff incompatible falla salvo cambio versionado», y §14 pone
«el contrato cambia sin detectar» como riesgo explícito. Sin esto, un campo que
desaparece de una respuesta se descubre en la SPA en producción; con esto se
descubre en el PR que lo quitó.

Uso:

    python scripts/check_openapi_compat.py BASE.json HEAD.json

Sale 1 si encuentra algún cambio incompatible y 0 si todo lo que cambió es
aditivo. Imprime las dos listas: un cambio aditivo también merece leerse.

Qué se considera incompatible
-----------------------------

La regla es de quién es el problema, y depende de la dirección del dato:

* **Respuestas (el servidor da, el cliente lee).** Quitar una operación, un
  código de estado, una propiedad, o dejar de garantizar una que era `required`,
  deja al cliente leyendo `undefined`. Reducir un enum le entrega un valor que
  su `switch` no cubre. Todo eso rompe.
* **Peticiones (el cliente da, el servidor valida).** Exigir una propiedad o un
  parámetro nuevo —o volver `required` uno opcional— rompe a todo cliente que
  hoy no lo manda. Reducir un enum rechaza valores que antes se aceptaban.
  Quitar una propiedad opcional no rompe: el servidor la ignora.

La vía de escape es la de §5.3, no un flag: una operación marcada
``deprecated: true`` en el documento base puede retirarse sin que esto falle.
Ese es el paso 6 antes del 7 —marcar deprecated, medir, y retirar después—, y
deja constancia en el propio contrato en vez de en un fichero de excepciones que
nadie revisa. Un cambio versionado (`/api/v2`) aparece como paths nuevos, que
son aditivos por definición.

Lo que no se mira: `description`, `summary`, `example`, `title` y el orden de las
claves. Cambiar la prosa de un contrato no rompe a nadie y bloquear PRs por eso
enseña a ignorar el check.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

HTTP_METHODS = ("get", "put", "post", "delete", "patch")

Direction = Literal["request", "response"]


@dataclass
class Report:
    """Los dos veredictos, cada uno con su lista de motivos."""

    breaking: list[str] = field(default_factory=list)
    compatible: list[str] = field(default_factory=list)

    def break_(self, where: str, what: str) -> None:
        self.breaking.append(f"{where}: {what}")

    def ok(self, where: str, what: str) -> None:
        self.compatible.append(f"{where}: {what}")


class Document:
    """Un OpenAPI con resolución de `$ref` dentro del propio documento."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw

    def resolve(self, schema: Any) -> dict[str, Any]:
        """Sigue `$ref` hasta el primer schema real. Cadenas rotas → ``{}``."""
        seen: set[str] = set()
        while isinstance(schema, dict) and "$ref" in schema:
            ref = schema["$ref"]
            if not isinstance(ref, str) or not ref.startswith("#/") or ref in seen:
                return {}
            seen.add(ref)
            node: Any = self.raw
            for part in ref[2:].split("/"):
                if not isinstance(node, dict) or part not in node:
                    return {}
                node = node[part]
            schema = node
        return schema if isinstance(schema, dict) else {}

    def operations(self) -> dict[tuple[str, str], dict[str, Any]]:
        found: dict[tuple[str, str], dict[str, Any]] = {}
        for path, item in (self.raw.get("paths") or {}).items():
            if not isinstance(item, dict):
                continue
            for method in HTTP_METHODS:
                operation = item.get(method)
                if isinstance(operation, dict):
                    found[(path, method)] = operation
        return found


def _enum_of(schema: dict[str, Any]) -> list[Any] | None:
    values = schema.get("enum")
    return values if isinstance(values, list) else None


def _members(schema: dict[str, Any]) -> tuple[str, list[Any]] | None:
    for keyword in ("anyOf", "oneOf", "allOf"):
        value = schema.get(keyword)
        if isinstance(value, list):
            return keyword, value
    return None


def _describe(values: list[Any]) -> str:
    return ", ".join(sorted(json.dumps(v, sort_keys=True) for v in values))


class SchemaComparer:
    """Recorre dos schemas en paralelo y anota cada diferencia en el `Report`."""

    def __init__(self, base: Document, head: Document, report: Report) -> None:
        self.base = base
        self.head = head
        self.report = report
        # Los modelos se referencian entre sí (una comunidad tiene posts que
        # tienen una comunidad). Sin esta memoria de pares ya visitados, el
        # recorrido no termina.
        self._visited: set[tuple[int, int, Direction]] = set()

    def compare(
        self,
        base_schema: Any,
        head_schema: Any,
        direction: Direction,
        where: str,
    ) -> None:
        base_ref = base_schema.get("$ref") if isinstance(base_schema, dict) else None
        head_ref = head_schema.get("$ref") if isinstance(head_schema, dict) else None

        old = self.base.resolve(base_schema)
        new = self.head.resolve(head_schema)
        if not old or not new:
            return

        if base_ref and head_ref:
            key = (id(old), id(new), direction)
            if key in self._visited:
                return
            self._visited.add(key)

        self._compare_type(old, new, where)
        self._compare_enum(old, new, direction, where)
        self._compare_required(old, new, direction, where)
        self._compare_properties(old, new, direction, where)
        self._compare_members(old, new, direction, where)

        if isinstance(old.get("items"), dict) and isinstance(new.get("items"), dict):
            self.compare(old["items"], new["items"], direction, f"{where}[]")

        old_extra, new_extra = old.get("additionalProperties"), new.get("additionalProperties")
        if isinstance(old_extra, dict) and isinstance(new_extra, dict):
            self.compare(old_extra, new_extra, direction, f"{where}{{*}}")

    def _compare_type(self, old: dict[str, Any], new: dict[str, Any], where: str) -> None:
        old_type, new_type = old.get("type"), new.get("type")
        if old_type and new_type and old_type != new_type:
            self.report.break_(where, f"el tipo pasó de {old_type} a {new_type}")

    def _compare_enum(
        self, old: dict[str, Any], new: dict[str, Any], direction: Direction, where: str
    ) -> None:
        old_enum, new_enum = _enum_of(old), _enum_of(new)
        if old_enum is None and new_enum is None:
            return

        if old_enum is not None and new_enum is not None:
            removed = [v for v in old_enum if v not in new_enum]
            added = [v for v in new_enum if v not in old_enum]
            if removed:
                self.report.break_(where, f"el enum ya no admite {_describe(removed)}")
            if added:
                self.report.ok(where, f"el enum admite además {_describe(added)}")
            return

        if old_enum is not None:  # el head dejó de restringir los valores
            if direction == "response":
                self.report.break_(
                    where,
                    "el enum desapareció: la respuesta puede traer valores que el "
                    "cliente no contempla",
                )
            else:
                self.report.ok(where, "el enum desapareció: se aceptan más valores")
            return

        # el head restringe algo que antes era libre
        if direction == "request":
            self.report.break_(
                where, f"ahora solo se aceptan los valores {_describe(new_enum or [])}"
            )
        else:
            self.report.ok(where, "la respuesta pasó a estar restringida a un enum")

    def _compare_required(
        self, old: dict[str, Any], new: dict[str, Any], direction: Direction, where: str
    ) -> None:
        old_required = set(old.get("required") or [])
        new_required = set(new.get("required") or [])
        # Solo tiene sentido sobre objetos con propiedades declaradas.
        if not isinstance(old.get("properties"), dict):
            return

        if direction == "response":
            for name in sorted(old_required - new_required):
                self.report.break_(
                    f"{where}.{name}", "dejó de estar garantizada en la respuesta"
                )
            for name in sorted(new_required - old_required):
                self.report.ok(f"{where}.{name}", "pasó a estar siempre presente")
        else:
            for name in sorted(new_required - old_required):
                self.report.break_(f"{where}.{name}", "pasó a ser obligatoria")
            for name in sorted(old_required - new_required):
                self.report.ok(f"{where}.{name}", "dejó de ser obligatoria")

    def _compare_properties(
        self, old: dict[str, Any], new: dict[str, Any], direction: Direction, where: str
    ) -> None:
        old_props = old.get("properties")
        new_props = new.get("properties")
        if not isinstance(old_props, dict) or not isinstance(new_props, dict):
            return

        for name in sorted(set(old_props) - set(new_props)):
            if direction == "response":
                self.report.break_(f"{where}.{name}", "desapareció de la respuesta")
            else:
                self.report.ok(
                    f"{where}.{name}", "dejó de aceptarse en la petición (se ignora)"
                )
        for name in sorted(set(new_props) - set(old_props)):
            self.report.ok(f"{where}.{name}", "es nueva")
        for name in sorted(set(old_props) & set(new_props)):
            self.compare(old_props[name], new_props[name], direction, f"{where}.{name}")

    def _compare_members(
        self, old: dict[str, Any], new: dict[str, Any], direction: Direction, where: str
    ) -> None:
        old_members, new_members = _members(old), _members(new)
        if old_members is None or new_members is None:
            return
        old_keyword, old_list = old_members
        new_keyword, new_list = new_members

        if old_keyword != new_keyword:
            self.report.break_(where, f"la composición pasó de {old_keyword} a {new_keyword}")
            return

        if len(old_list) == len(new_list):
            for index, (old_member, new_member) in enumerate(zip(old_list, new_list)):
                self.compare(old_member, new_member, direction, f"{where}|{index}")
            return

        if len(new_list) < len(old_list):
            self.report.break_(
                where,
                f"{old_keyword} perdió variantes ({len(old_list)} → {len(new_list)})",
            )
        elif direction == "response":
            self.report.break_(
                where,
                f"{old_keyword} ganó variantes ({len(old_list)} → {len(new_list)}): la "
                "respuesta puede traer una forma que el cliente no contempla",
            )
        else:
            self.report.ok(
                where, f"{old_keyword} acepta más variantes ({len(old_list)} → {len(new_list)})"
            )


def _parameter_key(parameter: dict[str, Any]) -> tuple[str, str]:
    return str(parameter.get("in", "")), str(parameter.get("name", ""))


def _parameters(operation: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    found = {}
    for parameter in operation.get("parameters") or []:
        if isinstance(parameter, dict):
            found[_parameter_key(parameter)] = parameter
    return found


def _compare_parameters(
    comparer: SchemaComparer,
    report: Report,
    old_op: dict[str, Any],
    new_op: dict[str, Any],
    where: str,
) -> None:
    old_params, new_params = _parameters(old_op), _parameters(new_op)

    for key in sorted(set(new_params) - set(old_params)):
        location, name = key
        if new_params[key].get("required"):
            report.break_(f"{where} {location}:{name}", "es un parámetro obligatorio nuevo")
        else:
            report.ok(f"{where} {location}:{name}", "es un parámetro opcional nuevo")

    for key in sorted(set(old_params) - set(new_params)):
        location, name = key
        report.ok(f"{where} {location}:{name}", "dejó de aceptarse (se ignora)")

    for key in sorted(set(old_params) & set(new_params)):
        location, name = key
        old_param, new_param = old_params[key], new_params[key]
        if new_param.get("required") and not old_param.get("required"):
            report.break_(f"{where} {location}:{name}", "pasó a ser obligatorio")
        elif old_param.get("required") and not new_param.get("required"):
            report.ok(f"{where} {location}:{name}", "dejó de ser obligatorio")
        if isinstance(old_param.get("schema"), dict) and isinstance(new_param.get("schema"), dict):
            comparer.compare(
                old_param["schema"], new_param["schema"], "request", f"{where} {location}:{name}"
            )


def _compare_body(
    comparer: SchemaComparer,
    report: Report,
    old_op: dict[str, Any],
    new_op: dict[str, Any],
    where: str,
) -> None:
    old_body = old_op.get("requestBody")
    new_body = new_op.get("requestBody")
    if not isinstance(old_body, dict) or not isinstance(new_body, dict):
        if isinstance(new_body, dict) and new_body.get("required"):
            report.break_(where, "la operación pasó a exigir cuerpo")
        return

    if new_body.get("required") and not old_body.get("required"):
        report.break_(where, "el cuerpo pasó a ser obligatorio")

    old_content = old_body.get("content") or {}
    new_content = new_body.get("content") or {}
    for media_type in sorted(set(old_content) - set(new_content)):
        report.break_(where, f"ya no se acepta el cuerpo en {media_type}")
    for media_type in sorted(set(new_content) - set(old_content)):
        report.ok(where, f"se acepta además el cuerpo en {media_type}")
    for media_type in sorted(set(old_content) & set(new_content)):
        old_schema = (old_content[media_type] or {}).get("schema")
        new_schema = (new_content[media_type] or {}).get("schema")
        if old_schema is not None and new_schema is not None:
            comparer.compare(old_schema, new_schema, "request", f"{where} body({media_type})")


def _compare_responses(
    comparer: SchemaComparer,
    report: Report,
    old_op: dict[str, Any],
    new_op: dict[str, Any],
    where: str,
) -> None:
    old_responses = old_op.get("responses") or {}
    new_responses = new_op.get("responses") or {}

    for status in sorted(set(old_responses) - set(new_responses)):
        report.break_(f"{where} {status}", "el código de respuesta desapareció")
    for status in sorted(set(new_responses) - set(old_responses)):
        report.ok(f"{where} {status}", "es un código de respuesta nuevo")

    for status in sorted(set(old_responses) & set(new_responses)):
        old_content = (old_responses[status] or {}).get("content") or {}
        new_content = (new_responses[status] or {}).get("content") or {}
        for media_type in sorted(set(old_content) - set(new_content)):
            report.break_(f"{where} {status}", f"ya no se devuelve {media_type}")
        for media_type in sorted(set(old_content) & set(new_content)):
            old_schema = (old_content[media_type] or {}).get("schema")
            new_schema = (new_content[media_type] or {}).get("schema")
            if old_schema is not None and new_schema is not None:
                comparer.compare(old_schema, new_schema, "response", f"{where} {status}")


def compare_documents(base_raw: dict[str, Any], head_raw: dict[str, Any]) -> Report:
    base, head = Document(base_raw), Document(head_raw)
    report = Report()
    comparer = SchemaComparer(base, head, report)

    old_ops, new_ops = base.operations(), head.operations()

    for key in sorted(set(old_ops) - set(new_ops)):
        path, method = key
        where = f"{method.upper()} {path}"
        if old_ops[key].get("deprecated"):
            # §5.3, pasos 6 y 7: se marcó deprecated, se midió y ahora se retira.
            report.ok(where, "se retiró una operación que ya estaba deprecated")
        else:
            report.break_(
                where,
                "la operación desapareció sin haber estado marcada deprecated (§5.3)",
            )

    for key in sorted(set(new_ops) - set(old_ops)):
        path, method = key
        report.ok(f"{method.upper()} {path}", "es una operación nueva")

    for key in sorted(set(old_ops) & set(new_ops)):
        path, method = key
        where = f"{method.upper()} {path}"
        old_op, new_op = old_ops[key], new_ops[key]

        old_id, new_id = old_op.get("operationId"), new_op.get("operationId")
        if old_id != new_id:
            # El `operationId` es el nombre del tipo generado: renombrarlo rompe
            # a todo el que lo importe, aunque el JSON viaje idéntico.
            report.break_(where, f"el operationId pasó de {old_id!r} a {new_id!r}")

        if new_op.get("deprecated") and not old_op.get("deprecated"):
            report.ok(where, "quedó marcada deprecated")

        _compare_parameters(comparer, report, old_op, new_op, where)
        _compare_body(comparer, report, old_op, new_op, where)
        _compare_responses(comparer, report, old_op, new_op, where)

    return report


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict):
        raise SystemExit(f"{path} no contiene un documento OpenAPI")
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path, help="OpenAPI de referencia (rama base)")
    parser.add_argument("head", type=Path, help="OpenAPI del commit a verificar")
    parser.add_argument(
        "--quiet-compatible",
        action="store_true",
        help="no listar los cambios aditivos, solo los que rompen",
    )
    args = parser.parse_args(argv)

    report = compare_documents(_load(args.base), _load(args.head))

    if report.compatible and not args.quiet_compatible:
        print(f"Cambios compatibles ({len(report.compatible)}):")
        for line in report.compatible:
            print(f"  + {line}")

    if not report.breaking:
        print("\nContrato compatible: ningún cambio rompe a los clientes actuales.")
        return 0

    print(f"\nCambios INCOMPATIBLES ({len(report.breaking)}):")
    for line in report.breaking:
        print(f"  ! {line}")
    print(
        "\nUn cambio deliberado se versiona (paths nuevos) o se retira por el "
        "camino de §5.3: marcar la operación deprecated, medir su uso durante un "
        "ciclo de release y retirarla después."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
