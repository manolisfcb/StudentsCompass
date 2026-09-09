# Ejecución de pruebas

Dos lanes. La rápida es hermética y corre en todas partes; la de integración
necesita servicios desechables locales y verifica lo que SQLite no puede.

Origen: TASK-001 del [tablero de refactor](refactor/TASKS.md). La toolchain que
se describe abajo la fija TASK-033.

## Dónde se ejecutan

Desde `backend/`. TASK-037 movió el árbol Python ahí y `pytest.ini`, `app/` y
las rutas que el código resuelve contra el directorio de trabajo viajaron con
él; lanzar la suite desde la raíz del repositorio ya no encuentra nada.

El entorno virtual sigue en la raíz mientras el monorepo tenga un solo lenguaje
instalado, así que el intérprete es `../.venv/bin/python`. Todos los comandos de
este documento asumen ese directorio:

```bash
cd backend
```

Las mediciones de abajo se repitieron desde la nueva ubicación y dieron los
mismos números, que es lo que TASK-037 tenía que demostrar.

## Toolchain fijada

| Runtime | Versión | Declarada en | Consumida por |
| --- | --- | --- | --- |
| Python | 3.12 | `backend/.python-version`, `requires-python` de `backend/pyproject.toml` | `Dockerfile` (`python:3.12-slim`), `actions/setup-python` en las tres lanes de CI, `uv venv` |
| Node | 24 | `.nvmrc` | Aún ninguno: la imagen del frontend y el `engines` de `frontend/package.json` la leerán cuando TASK-038 cree el scaffold |

`requires-python` está acotado por arriba (`>=3.12,<3.13`) a propósito: 3.12 es
la única versión en la que la suite se mide. Ampliarlo exige medir primero.

Crear el entorno local en la versión declarada:

```bash
uv venv --python 3.12
uv pip install -r requirements.txt \
  "pytest>=9.0.2" "pytest-asyncio>=1.3.0" "pytest-cov>=7.0.0" "httpx>=0.28.1"
```

`.python-version` hace que `uv venv` sin argumentos elija 3.12. Un intérprete
distinto al declarado invalida cualquier medición de paridad contra la baseline:
la suite verde en otra versión no dice nada sobre la imagen que se despliega.

### Baseline de la migración

Medida el 2026-09-07 sobre `325e92b` con CPython 3.12.12, las tres lanes de
`.github/workflows/ci.yml`. Los comandos aparecen ya en su forma posterior a
TASK-037, que repitió las tres desde `backend/` y obtuvo los mismos conteos; el
movimiento no cambió ni un resultado:

| Lane | Comando | Resultado |
| --- | --- | --- |
| Rápida | `../.venv/bin/python -m pytest -p no:cacheprovider` | 429 passed, 61 skipped |
| PostgreSQL + Redis | idem con `TEST_DATABASE_URL_PG` y `TEST_REDIS_URL`, sobre `tests/integration` | 61 passed |
| Navegador | `../.venv/bin/python -m pytest -p no:cacheprovider -m browser` | 14 passed, 476 deselected |

Cero fallos en las tres. Los 61 omitidos de la lane rápida son exactamente los
que su lane propia cubre: 60 de `tests/integration` sin
`TEST_DATABASE_URL_PG`/`TEST_REDIS_URL`, más `test_embedding_service.py:139`,
que necesita pgvector. Los 14 del navegador están dentro de los 429 porque
Playwright y Chromium están instalados; sin ellos se omiten solos.

El plan 08 §2 registraba `403 passed, 50 skipped, 1 failed` el 2026-09-06 sobre
`f9ca382` en Python 3.10. El fallo era
`test_a_repeated_join_is_refused_and_changes_nothing`, lo cerró TASK-017, y aquí
pasa. El resto de la diferencia son los tests que TASK-016 y TASK-017 añadieron
después de esa medición, y cuadra exacto:

- Pasados: `403 + 1` (el que fallaba) `+ 25` de `test_course_progress_projection.py` = `429`.
- Omitidos: `50 + 11` (5 de `test_community_member_count_pg.py` y 6 de `test_core_course_code_migration_pg.py`) = `61`.

Ninguna diferencia queda sin explicar, así que el cambio de 3.10 a 3.12 no
mueve ningún resultado.

## Lane rápida (por defecto)

```bash
../.venv/bin/python -m pytest -p no:cacheprovider
```

Sin argumentos corre SQLite en memoria, sin red y sin escribir reportes de
cobertura en el repositorio. Para reproducir exactamente la medición de la
auditoría:

```bash
../.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider -q
```

### Aislamiento

`tests/isolation.py` se aplica en `tests/conftest.py` **antes** de importar
cualquier módulo de `app`, porque `app/db.py` y `app/app.py` llaman
`load_dotenv()` y construyen el engine en tiempo de import. Garantiza tres
cosas:

1. **`.env` nunca se lee.** `load_dotenv`/`find_dotenv` quedan neutralizados, así
   que las credenciales reales del desarrollador no entran al proceso de test.
2. **Credenciales ficticias explícitas.** Cada variable sensible tiene un valor
   `test-...` evidente; si aparece en un log o una request, su origen es
   inequívoco. `REDIS_URL` queda vacía, de modo que la lane rápida usa el
   counter store en memoria.
3. **Sockets salientes bloqueados.** Solo loopback y los servicios desechables
   declarados con `allow_test_service()`. Un intento de salir lanza
   `ExternalConnectionBlocked`.

`assert_local_url()` además rechaza una URL de lane que no apunte a un host
local, para que una variable de entorno obsoleta no dirija las pruebas contra
un despliegue real. Ambos comportamientos están cubiertos en
`tests/test_isolation_harness.py`.

### Cobertura (opt-in)

```bash
../.venv/bin/python -m pytest --cov=app --cov-report=term-missing
```

El alcance está fijado en `[tool.coverage.run]` de `pyproject.toml` para que el
número signifique lo mismo en local y en CI.

## Lane PostgreSQL + Redis (integración)

SQLite no sustituye a esta lane: locks de fila, `SELECT ... FOR UPDATE`,
violaciones de unique bajo concurrencia, índices parciales, tipos `JSONB`/`UUID`
y búsqueda vectorial `pgvector` solo se comportan de verdad aquí.

```bash
docker run -d --name sc-test-pg \
  -e POSTGRES_USER=testuser -e POSTGRES_PASSWORD=testpw \
  -e POSTGRES_DB=studentscompass_test \
  -p 55432:5432 pgvector/pgvector:pg16

docker run -d --name sc-test-redis -p 56379:6379 redis:7-alpine

TEST_DATABASE_URL_PG='postgresql+asyncpg://testuser:testpw@127.0.0.1:55432/studentscompass_test' \
TEST_REDIS_URL='redis://127.0.0.1:56379/0' \
../.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/integration
```

Sin esas variables, los tests de `tests/integration` se saltan; la lane rápida
sigue verde. Las bases son desechables: nunca se apunta a producción, y
`assert_local_url` lo impide aunque se intente.

Limpieza: `docker rm -f sc-test-pg sc-test-redis`.

## Harness compartido

`tests/harness.py` da las dos herramientas que usan las tareas posteriores del
refactor:

- **`count_queries(engine)`** → `QueryCounter` con `selects`, `writes`, `total`
  y `matching(fragmento)`. Permite expresar presupuestos N+1 como aserciones
  ("este endpoint hace un número constante de SELECT") en vez de como cronómetro.
  Fixtures: `query_counter` (SQLite) y `pg_query_counter` (PostgreSQL).
- **`two_sessions(session_factory)`** → dos `AsyncSession` independientes para
  transacciones entrelazadas. Fixtures: `two_db_sessions` (SQLite, solo orden de
  sentencias) y `pg_two_sessions` (PostgreSQL, contención real). Nunca compartir
  una `AsyncSession` entre tareas concurrentes.

## Contratos capturados

`tests/test_contract_baseline.py` (marca `contract`) fija el comportamiento
actual de las fronteras que el refactor va a tocar: auth, CV, cuota de IA,
candidaturas, progreso y Career Lab. Pinnea forma de respuesta y control de
acceso, no reglas de negocio. Cambiar uno de estos contratos es un cambio de
contrato y pertenece a la tarea que lo declare.

Uno de ellos documenta una desviación conocida:
`test_dashboard_stats_currently_writes_a_user_stats_row_on_read` deja constancia
de que `GET /api/v1/dashboard/stats` materializa la fila `user_stats` en la
primera lectura (F-15). Es caracterización, no aprobación: TASK-016 lo corrige y
en ese momento el test pasa a exigir cero escrituras.

## Lane de navegador

`tests/test_frontend_xss_browser.py` (marca `browser`) ejecuta los scripts
estáticos reales en un Chromium headless vía Playwright y comprueba el DOM
resultante, en vez de buscar el nombre de un helper en el código. La página se
sirve desde un origen `http://` real y **todas** las peticiones las resuelve el
propio manejador de rutas del test, así que el navegador no alcanza ningún host
externo.

```bash
uv pip install playwright
../.venv/bin/python -m playwright install chromium
../.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider -m browser
```

Sin Playwright o sin el navegador instalado, estos tests se saltan solos.

## Marcas

| Marca | Significado |
| --- | --- |
| `integration` | Necesita un servicio externo desechable; se salta sin su URL de lane |
| `postgres` | Necesita la lane PostgreSQL + pgvector (`TEST_DATABASE_URL_PG`) |
| `redis` | Necesita la lane Redis (`TEST_REDIS_URL`) |
| `contract` | Caracterización que fija comportamiento antes de un refactor |
| `browser` | Ejecuta scripts estáticos reales en Chromium; se salta sin Playwright/navegador |

## CI

`.github/workflows/ci.yml` (hasta TASK-039, `tests.yml`). Son ocho jobs
independientes: backend y frontend no comparten job, ni caché, ni instalación,
así que un error de tipos de TypeScript no puede teñir de rojo la suite de Python
ni al revés.

| Job | Qué ejecuta | Bloquea |
| --- | --- | --- |
| `secrets` | gitleaks sobre el árbol del checkout | Sí |
| `deps-audit` | osv-scanner sobre `backend/requirements.txt` y `frontend/package-lock.json` | No — ver abajo |
| `backend-lint` | `uv lock --check` y `ruff check .` | Sí |
| `backend-fast` | lane rápida (SQLite) y export del OpenAPI del SHA | Sí |
| `backend-integration` | lane PostgreSQL + pgvector y Redis | Sí |
| `backend-browser` | lane de navegador (Chromium) | Sí |
| `backend-baseline` | `scripts/capture_baseline.py` y capturas como artefacto | Sí |
| `frontend` | `npm ci`, ESLint, `tsc --noEmit`, i18n, Vitest y build | Sí |

Al job rápido no se le pasa ningún secreto a propósito: si un test alcanza un
proveedor real, falla ahí y no en producción. Ningún job imprime variables de
entorno; las únicas credenciales que aparecen en el workflow son las del
PostgreSQL efímero de la lane de integración, que nace y muere con el job.

**Versiones desde ficheros versionados.** `actions/setup-python` lee
`backend/.python-version` y `actions/setup-node` lee `.nvmrc`, en vez de repetir
el número en el workflow. Hasta TASK-039 `.nvmrc` era una declaración sin ningún
consumidor que la verificara.

**El artefacto de contrato.** `backend-fast` publica `openapi-<sha>` con la
salida de `scripts/export_openapi.py`. Va en esa lane y no en la de baseline
porque solo necesita que la aplicación sea importable: colgarlo de la lane de
baseline dejaría al SHA sin contrato cada vez que fallara Chromium. TASK-043 lo
convierte en la fuente de los tipos TypeScript del frontend.

**Verificación de locks.** `uv lock --check` falla si alguien añade una
dependencia a `backend/pyproject.toml` sin correr `uv lock`; `npm ci` falla si
`frontend/package-lock.json` no concuerda con `package.json`. Nótese que
`backend/requirements.txt` —lo que instalan la imagen y las lanes de test— es un
tercer artefacto que hoy **no** concuerda con `uv.lock`: 58 paquetes difieren de
versión y 8 pines no existen en el lock. Es deuda anterior a esta tarea y su
dueño es TASK-029.

**Por qué `deps-audit` no bloquea.** Los pines actuales ya arrastran advisories
conocidos: 74 sobre 10 paquetes de `backend/requirements.txt` el 2026-09-08
(`starlette`, `python-multipart`, `pyjwt`, `cryptography`, `transformers`,
`torch`, `pillow`, `pyasn1`, `setuptools`, `soupsieve`);
`frontend/package-lock.json` sale limpio. Subir esas versiones es un cambio de
dependencias que pertenece a TASK-029, y bloquear con la deuda puesta pondría en
rojo PRs que no tocaron ninguna dependencia. El informe queda visible en cada run
y TASK-029 retira el `continue-on-error`.

## Lint / typecheck

Hasta TASK-039 esto era **N/A**: no había linter ni type checker en
configuración versionada, y la Definition of Done global exigía documentarlo en
vez de declarar aprobado un check inexistente. TASK-039 incorporó los dos.

| Capa | Herramienta | Versión | Alcance | Configuración |
| --- | --- | --- | --- | --- |
| Backend, lint | Ruff | resuelta por `backend/uv.lock` (0.16.6 al integrar) | `backend/`, reglas `E4`, `E7`, `E9`, `F` | `[tool.ruff]` de `backend/pyproject.toml` |
| Frontend, lint | ESLint | fijada por `frontend/package-lock.json` | `frontend/` | `frontend/eslint.config.js` (TASK-038) |
| Frontend, tipos | TypeScript | fijada por `frontend/package-lock.json` | `tsc -b --noEmit` | `frontend/tsconfig*.json` (TASK-038) |

```bash
cd backend  && uv run ruff check .
cd frontend && npm run lint && npm run typecheck
```

Ruff **no** formatea. `ruff format` no se ejecuta en CI ni se configura:
formatear el árbol entero es un diff que toca cada fichero de `app/` y no cabía
en una ficha que declara no cambiar comportamiento. Adoptarlo es una decisión con
su propia ficha.

`[tool.ruff.lint.per-file-ignores]` conserva **solo** dos entradas, y las dos son
la misma excepción permanente: `E402` en `app/app.py` y en `tests/conftest.py`.
En ambos ficheros hay código que debe correr antes de los imports, que es
exactamente lo que la regla prohíbe —`load_dotenv()` antes de construir el
engine, y `apply_isolation()` antes de importar nada de `app`—.

La deuda que TASK-039 inventarió ahí —`F401`, `F841` y `E741`, exenta fichero a
fichero— la retiró **TASK-060**, y con ella la propiedad que la hacía peligrosa:
una exención por fichero exime también al código que se escriba mañana, así que
mientras existió, un import muerto **nuevo** en cualquiera de esos 24 ficheros no
rompía CI.

Los pocos imports que siguen sin usarse llevan `# noqa: F401` **con su razón en
la línea**, que es donde se lee. Casi todos son registro de mappers de
SQLAlchemy: `app/models/applicationModel.py` importa `JobPosting` para que
`relationship("JobPosting")` resuelva por nombre, y borrarlo rompe el mapeo en
runtime sin que ningún test unitario tenga por qué notarlo —
`app/models/registry.py` lo importa todo, pero lo usan Alembic y los tests, no la
aplicación en ejecución—. Los dos ficheros de `alembic/versions/` conservan la
cabecera `op`/`sa` que genera la plantilla de Alembic.

No se añaden ficheros nuevos a la lista. Lo que necesite una excepción la lleva
en su línea.
