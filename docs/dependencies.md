# Dependencias activas

Origen: TASK-029 del tablero de refactor, hallazgo F-26. Medido el 2026-09-09
sobre `backend/`, con un barrido AST de todos los `import` de `app/`, `tests/`,
`alembic/`, `scripts/` y `main.py`.

## Las tres fuentes de verdad, y que hoy no coinciden

| Artefacto | Quién lo usa |
| --- | --- |
| `pyproject.toml` | declara las 20 dependencias directas; es lo que `uv` resuelve |
| `uv.lock` | lo que `uv sync --frozen` instala (incluye el grupo dev) |
| `requirements.txt` | **lo que instalan la imagen Docker y las lanes de test de CI** |

**Divergen.** 58 paquetes difieren de versión entre `requirements.txt` y
`uv.lock`, y 8 pines de `requirements.txt` no existen en el lock. El entorno
realmente instalado coincide con `requirements.txt` en los 58 casos y con
`uv.lock` en ninguno: **el lock es el obsoleto**. Cerrar esa brecha cambia
versiones en producción en una dirección o en la otra, así que es **TASK-066**,
no limpieza.

`uv lock --check` (CI, desde TASK-039) solo prueba que el lock describe
`pyproject.toml`. Nada comprueba hoy que `requirements.txt` describa el lock.

## Advisories

**74 advisories vigentes sobre 10 paquetes** de `requirements.txt`, medidos con
`osv-scanner` v2.5.1 el 2026-09-08: `starlette`, `python-multipart`, `pyjwt`,
`cryptography`, `transformers`, `torch`, `pillow`, `pyasn1`, `setuptools`,
`soupsieve`. `frontend/package-lock.json` limpio.

TASK-043 añadió una dependencia de desarrollo al frontend, `openapi-typescript`
(pin exacto `7.13.0`), que genera `frontend/src/api/generated/` desde
`contract/openapi.json`. No entra en el bundle —los tipos se borran al compilar—
ni en la imagen: solo corre en `npm run api:types`. La cifra de arriba es de
antes de añadirla; `deps-audit` vuelve a medir el lock en cada run.

Los pines no han cambiado desde esa medición —`requirements.txt` no se toca
desde `cf6d1ef`— así que la cifra sigue vigente. El job `deps-audit` la vuelve a
medir en cada run de CI y **no bloquea**, deliberadamente. Remediarlos y quitar
ese `continue-on-error` es **TASK-067**.

## Qué importa cada dependencia directa

| Paquete | Importado en | Nota |
| --- | --- | --- |
| `fastapi` | 48 ficheros | |
| `alembic` | 49 ficheros | migraciones |
| `fastapi-users` | 21 ficheros | las dos identidades de auth |
| `python-dotenv` | 8 ficheros | cargado en `app/config.py` |
| `google-genai` | 3 ficheros | los dos evaluadores LLM |
| `pgvector` | 3 ficheros | |
| `redis` | 2 ficheros | contador compartido |
| `uvicorn` | 2 ficheros | |
| `beautifulsoup4` | `app/core/JobsScraper/linkedin_scraper.py` | |
| `boto3` | `app/services/storage/s3Service.py` | |
| `imagekitio` | `app/services/storage/mediaStorageService.py` | |
| `ortools` | `app/services/analytics/learningRouteOptimizerService.py` | CP-SAT |
| `sentence-transformers` | `app/services/analytics/embeddingService.py` | opcional en runtime |

### Sin `import` directo, y por qué cada una se queda

| Paquete | Motivo |
| --- | --- |
| `pymupdf` | **sí se importa**, como `fitz`, en `app/core/resume_analyzer/read_pdf_data.py` |
| `jinja2` | lo usa `Jinja2Templates` de Starlette (`app/template_utils.py`, `views.py`) |
| `asyncpg` | driver async de PostgreSQL, cargado por el esquema de la URL |
| `psycopg` | driver **sync**; es a lo que `alembic/env.py` traduce la URL para migrar |
| `aiosqlite` | driver de la lane SQLite de tests y de `capture_baseline.py` |
| `pillow` | sin import propio; lo pide `transformers` en su extra `vision`. Candidato a revisar, **no** retirado: la evidencia es indirecta |
| `psycopg2-binary` | sin ningún consumidor en el repositorio — `alembic/env.py` usa `psycopg` v3 y `psycopg2` solo aparece dentro de un ejemplo en un comentario. **No se retira** porque un despliegue puede fijar una URL `postgresql+psycopg2://` por configuración, y el mapa de traducción la dejaría pasar tal cual. Retirarlo exige comprobar las URLs reales, que no están en el repositorio |

### Retirada en TASK-029

- **`apify-client`** — retirada. Evidencia completa, no heurística: **cero
  `import`** en `app/`, `tests/`, `alembic/`, `scripts/` y `main.py`; la
  variable `APIFY_API_TOKEN` **no se lee en ningún sitio** (su única aparición
  es un valor falso en `tests/isolation.py`); y el scraper que la sustituyó dice
  en su propia cabecera «no Apify». Al retirarla el lock pierde también sus
  transitivas `impit` y `more-itertools`: 134 → 130 paquetes.

  `requirements.txt` todavía la pina; corregirlo es parte de **TASK-066**, que
  es quien decide la dirección de la reconciliación.

## Ciclos de import

F-26 señalaba «imports locales `TYPE_CHECKING` que parecen ciclos: no se
confirmó ciclo de ejecución». **Confirmado: no hay ciclo.**

Solo hay **dos** imports bajo `TYPE_CHECKING`:

- `app/schemas/applicationSchema.py` → `applicationService.ApprovedResumeOption`
- `app/schemas/resumeSchema.py` → `resumeModel.ResumeModel`

Importando **los 142 módulos de `app/`** uno a uno: 0 fallos. Y forzando cada
pareja en las dos direcciones, sin la guarda: las cuatro combinaciones importan
correctamente. Las guardas son de anotación, no de ciclo; retirarlas es posible
pero no aporta nada y no se hizo.

## Configuración

Desde TASK-029, **todo lo que se lee del entorno se parsea en `app/config.py`**,
con un solo juego de helpers. `app/db.py` tenía copias propias de `_env_flag` y
`_env_int`; `userService.py` y `companyService.py` tenían el cargador de
`SECRET_KEY` duplicado carácter por carácter, incluida la regla de que en
producción su ausencia es un error — de modo que arreglar uno habría dejado al
otro firmando tokens con el secreto de desarrollo. **Las dos identidades de auth
siguen separadas**, que es lo que el plan exige; lo que se comparte es la regla.

`load_dotenv()` se ejecuta en `app/config.py`, antes de la primera lectura. No es
un detalle: en cuanto `db.py` importa `config.py`, el cuerpo de `config.py` corre
*antes* de cualquier `load_dotenv()` que `db.py` hiciera después, y todas las
constantes se calcularían contra un entorno sin cargar. Cargarlo en el único
módulo que lee el entorno hace que «la configuración se parsea después del
fichero de entorno» sea cierto por construcción. Los tests neutralizan
`load_dotenv` antes de importar nada de `app` (`tests/isolation.py`), lo que
sigue funcionando: sustituyen la función, no el sitio donde se llama.
