"""Exporta el schema OpenAPI de la API a un fichero.

Origen: TASK-039 del tablero de refactor (docs/refactor/TASKS.md). El plan 08
§10 pide «export OpenAPI» como paso propio de la lane de backend, y TASK-043 lo
convierte en contrato del que se generan los tipos TypeScript del frontend. Para
eso el export tiene que ser barato y determinista: sin base sembrada, sin
navegador y sin red.

Es deliberadamente más pequeño que `capture_baseline.py`, que también exporta
OpenAPI pero como una parte de la baseline visual —siembra una SQLite, recorre
los GET y abre Chromium—. Esa baseline responde «¿se ve igual que antes?»; este
script responde «¿cuál es el contrato de este SHA?». Acoplarlos haría que un
fallo del navegador dejara a CI sin contrato.

El aislamiento de `tests/isolation.py` corre antes de importar `app`: `app.app`
y `app.db` llaman `load_dotenv()` y construyen el engine en tiempo de import, así
que sin él este script leería el `.env` del desarrollador. Importar la app no
abre conexiones —el engine es perezoso— y `app.openapi()` solo recorre las rutas
declaradas.

Uso:

    cd backend && python scripts/export_openapi.py                  # a stdout
    cd backend && python scripts/export_openapi.py -o openapi.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from tests.isolation import apply_isolation  # noqa: E402

apply_isolation()

from app.app import app  # noqa: E402


def build_schema() -> dict:
    return app.openapi()


def serialise(schema: dict) -> str:
    # `sort_keys` e `indent` fijos: el artefacto de dos SHA distintos debe
    # poder compararse con `diff`, y un orden de claves dependiente del
    # intérprete convertiría cualquier ejecución en un diff falso.
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="fichero de destino; sin él, el schema se escribe en stdout",
    )
    args = parser.parse_args()

    text = serialise(build_schema())
    if args.output is None:
        sys.stdout.write(text)
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    paths = len(json.loads(text)["paths"])
    print(f"openapi: {args.output} ({paths} paths)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
