# Ejecución de pruebas

Dos lanes. La rápida es hermética y corre en todas partes; la de integración
necesita servicios desechables locales y verifica lo que SQLite no puede.

Origen: TASK-001 del [tablero de refactor](refactor/TASKS.md). La toolchain que
se describe abajo la fija TASK-033.

## Toolchain fijada

| Runtime | Versión | Declarada en | Consumida por |
| --- | --- | --- | --- |
| Python | 3.12 | `.python-version`, `requires-python` de `pyproject.toml` | `Dockerfile` (`python:3.12-slim`), `actions/setup-python` en las tres lanes de CI, `uv venv` |
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
`.github/workflows/tests.yml`:

| Lane | Comando | Resultado |
| --- | --- | --- |
| Rápida | `.venv/bin/python -m pytest -p no:cacheprovider` | 429 passed, 61 skipped |
| PostgreSQL + Redis | idem con `TEST_DATABASE_URL_PG` y `TEST_REDIS_URL`, sobre `tests/integration` | 61 passed |
| Navegador | `.venv/bin/python -m pytest -p no:cacheprovider -m browser` | 14 passed, 476 deselected |

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
.venv/bin/python -m pytest -p no:cacheprovider
```

Sin argumentos corre SQLite en memoria, sin red y sin escribir reportes de
cobertura en el repositorio. Para reproducir exactamente la medición de la
auditoría:

```bash
.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider -q
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
.venv/bin/python -m pytest --cov=app --cov-report=term-missing
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
.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/integration
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
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider -m browser
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

`.github/workflows/tests.yml` corre ambas lanes. Al job rápido no se le pasa
ningún secreto a propósito: si un test alcanza un proveedor real, falla ahí y no
en producción.

## Lint / typecheck

**N/A.** El repositorio no tiene linter ni type checker configurado (no hay
`ruff`, `flake8`, `mypy` ni `pyright` en `pyproject.toml`, `requirements.txt` ni
en configuración versionada), y TASK-001 no introduce uno. La Definition of Done
global exige documentarlo en vez de declarar aprobado un check inexistente. Si
se incorpora uno más adelante, debe registrarse aquí con herramienta, versión y
alcance.
