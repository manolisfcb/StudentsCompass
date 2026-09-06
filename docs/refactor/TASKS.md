# Refactor Task Board

## Allowed Statuses

- TODO
- IN PROGRESS
- BLOCKED
- COMPLETED

## Protocolo obligatorio para agentes

```text
1. Read the entire task.
2. Check dependencies.
3. If dependencies are incomplete, do not implement.
4. Change status from TODO to IN PROGRESS before touching production code.
5. Work strictly inside Scope.
6. Preserve existing behavior unless explicitly stated otherwise.
7. Run required validation.
8. Update documentation if architecture changed.
9. Add Completion Notes.
10. Only then change status to COMPLETED.
```

La primera modificación del agente debe reclamar su tarea: TODO → IN PROGRESS en este archivo. Leer [hallazgos](02_AUDIT_FINDINGS.md) y evidencia indicada antes de editar. READY es derivado: Status == TODO y todas las Dependencies == COMPLETED; no es un status permitido. **READY al generar el plan: TASK-001 y TASK-002.** Todas las tareas de este documento comienzan TODO; la auditoría no las ha implementado.

IDs estables: nunca renumerar/reutilizar; nueva tarea usa el siguiente ID libre. Sin cleanup lateral: descubrimiento fuera de Scope → finding/tarea nueva, no ampliar silenciosamente. Bug Fix significa que cambia el comportamiento defectuoso explícitamente descrito; el resto se preserva.

## Concurrencia e integración

Usar worktree/branch por tarea cuando haya agentes paralelos. Las reclamaciones y merges de TASKS.md se serializan mediante un único integrador: leer estado fresco, actualizar solo fila y sección propias y evitar sobrescribir reclamaciones. En workspace compartido reservar archivos antes de editar; si se descubre un solapamiento no anticipado, detener la parte conflictiva y coordinar. READY no es permiso para editar un archivo tomado por otra tarea.

Los grupos enumerados son combinaciones conservadoras; no implican esperar todas las tareas del grupo previo. Solo Dependencies bloquea funcionalmente, más exclusión de archivos. Todas las migraciones son archivos nuevos con ID único; reservar down_revision desde head integrado. El integrador serializa merges y crea merge revision si corresponde, probando upgrade sobre ambos caminos. Nunca dos agentes modifican una revisión ya aplicada, el mismo schema/modelo central ni el mismo contrato en paralelo. CI/pytest fixture central pertenece a TASK-001; tareas posteriores añaden tests locales, no reescriben ese fixture sin coordinación.

## Definition of Done global

Ninguna tarea COMPLETED con tests rotos, lint/typecheck relevante roto, vulnerabilidad nueva, nueva fuente de verdad duplicada, duplicación significativa, contrato roto sin transición, legacy activo sin justificación documentada, coupling innecesario o cambio de comportamiento fuera de Scope. Si no existe lint/typecheck configurado, documentar N/A y herramienta/alcance; no inventar un check aprobado. Una validación pendiente por acceso externo impide completar esa parte: registrar BLOCKED y evidencia faltante.

Reglas arquitectónicas: backend autoritativo en reglas sensibles; UI solo proyecta server state; composición/dependencias explícitas; DB relacionada atómica; idempotencia donde hay retries; evitar N+1 y SDKs dispersos; no abstracción que no resuelva duplicación/responsabilidad real. Toda migración incluye expansión, backfill si aplica, verificación, transición, constraints/índices, código compatible y rollback. No eliminación de datos por suposición. Métricas comparables antes/después para cada optimización.

## Summary Table

| ID | Title | Priority | Phase | Status | Depends On | Parallel |
| --- | --- | --- | --- | --- | --- | --- |
| TASK-001 | Fijar baseline aislada y pruebas PostgreSQL de integridad | HIGH | PHASE-0 | COMPLETED | NONE | TASK-002 |
| TASK-002 | Retirar secretos versionados y unificar destino de migraciones | CRITICAL | PHASE-1 | COMPLETED | NONE | TASK-001 |
| TASK-003 | Restringir borrado de posts al propietario | CRITICAL | PHASE-1 | COMPLETED | TASK-001 | TASK-004, TASK-007, TASK-009, TASK-020, TASK-030 |
| TASK-004 | Renderizar nombres de CV y enlaces sin HTML ejecutable | CRITICAL | PHASE-1 | COMPLETED | TASK-001 | TASK-003, TASK-007, TASK-009, TASK-020, TASK-030 |
| TASK-005 | Dar identidad única a objetos y hacer recuperable su ciclo de vida | CRITICAL | PHASE-1 | COMPLETED | TASK-001, TASK-009 | TASK-010, TASK-014, TASK-017, TASK-019, TASK-024 |
| TASK-006 | Acotar multipart, media y expansión de documentos | CRITICAL | PHASE-1 | COMPLETED | TASK-001, TASK-003, TASK-005 | TASK-012, TASK-015, TASK-021 |
| TASK-007 | Contabilizar cada intento Gemini y exigir límites compartidos | CRITICAL | PHASE-1 | COMPLETED | TASK-001 | TASK-003, TASK-004, TASK-009, TASK-020, TASK-030 |
| TASK-008 | Autorizar archivos de recursos por entidad visible | CRITICAL | PHASE-1 | COMPLETED | TASK-001, TASK-006 | TASK-013, TASK-022, TASK-027 |
| TASK-009 | Crear baseline y converger schemas históricos sin pérdida | CRITICAL | PHASE-0 | COMPLETED | TASK-001, TASK-002 | TASK-003, TASK-004, TASK-007, TASK-020, TASK-030 |
| TASK-010 | Cubrir autenticación de compañías y validar proxy confiable | CRITICAL | PHASE-1 | TODO | TASK-001, TASK-007 | TASK-005, TASK-014, TASK-017, TASK-019, TASK-024 |
| TASK-011 | Normalizar errores públicos y recuperación transaccional | CRITICAL | PHASE-1 | TODO | TASK-001, TASK-006, TASK-008 | TASK-023 |
| TASK-012 | Conciliar ledger IA y completar ciclo de reservas | HIGH | PHASE-2 | TODO | TASK-001, TASK-007, TASK-009 | TASK-006, TASK-015, TASK-021 |
| TASK-013 | Hacer durable e idempotente el procesamiento CV | HIGH | PHASE-2 | TODO | TASK-001, TASK-009, TASK-012 | TASK-008, TASK-022, TASK-027 |
| TASK-014 | Centralizar transiciones y proyección de candidaturas | HIGH | PHASE-2 | TODO | TASK-001, TASK-009 | TASK-005, TASK-010, TASK-017, TASK-019, TASK-024 |
| TASK-015 | Serializar selección de entrevista por candidatura | HIGH | PHASE-2 | TODO | TASK-001, TASK-009, TASK-014 | TASK-006, TASK-012, TASK-021 |
| TASK-016 | Unificar aprobación de CV y proyección de progreso | HIGH | PHASE-3 | TODO | TASK-001, TASK-009, TASK-011, TASK-012, TASK-014 | TASK-028 |
| TASK-017 | Derivar contador de comunidad desde membresías | HIGH | PHASE-2 | TODO | TASK-001, TASK-009 | TASK-005, TASK-010, TASK-014, TASK-019, TASK-024 |
| TASK-018 | Agrupar consultas de progreso de recursos | HIGH | PHASE-4 | TODO | TASK-001, TASK-016 | TASK-025 |
| TASK-019 | Hacer batch e idempotente la extracción de skills de ofertas | HIGH | PHASE-4 | TODO | TASK-001, TASK-009 | TASK-005, TASK-010, TASK-014, TASK-017, TASK-024 |
| TASK-020 | Sacar scraper de LinkedIn del event loop | HIGH | PHASE-4 | TODO | TASK-001 | TASK-003, TASK-004, TASK-007, TASK-009, TASK-030 |
| TASK-021 | Evitar regeneración de embeddings idénticos | MEDIUM | PHASE-4 | TODO | TASK-001, TASK-009, TASK-019 | TASK-006, TASK-012, TASK-015 |
| TASK-022 | Ejecutar CP-SAT fuera del loop con concurrencia acotada | MEDIUM | PHASE-4 | TODO | TASK-001, TASK-019, TASK-021 | TASK-008, TASK-013, TASK-027 |
| TASK-023 | Dividir Capstone conservando facade y contratos | HIGH | PHASE-5 | TODO | TASK-001, TASK-013, TASK-019, TASK-021, TASK-022, TASK-027 | TASK-011 |
| TASK-024 | Paginar mensajes con cursor estable y migrar inbox | MEDIUM | PHASE-4 | TODO | TASK-001, TASK-009 | TASK-005, TASK-010, TASK-014, TASK-017, TASK-019 |
| TASK-025 | Calcular dashboard en DB y definir transición de listados | MEDIUM | PHASE-4 | TODO | TASK-001, TASK-016 | TASK-018 |
| TASK-026 | Separar API, estado y render de Jobs y Career Lab | HIGH | PHASE-5 | TODO | TASK-001, TASK-004, TASK-013, TASK-016, TASK-018, TASK-020, TASK-023, TASK-024, TASK-025 | NONE |
| TASK-027 | Validar rangos, estados y metadata de datos analíticos | MEDIUM | PHASE-2 | TODO | TASK-001, TASK-009, TASK-015, TASK-019, TASK-021 | TASK-008, TASK-013, TASK-022 |
| TASK-028 | Medir flujos críticos y hacer visibles fallos parciales | MEDIUM | PHASE-4 | TODO | TASK-001, TASK-011, TASK-013, TASK-015, TASK-020, TASK-022, TASK-023 | TASK-016 |
| TASK-029 | Consolidar configuración y documentar dependencias activas | LOW | PHASE-6 | TODO | TASK-001, TASK-002, TASK-007, TASK-010, TASK-026, TASK-028, TASK-030 | NONE |
| TASK-030 | Validar respuestas y respetar versión histórica de cuestionario | MEDIUM | PHASE-3 | TODO | TASK-001 | TASK-003, TASK-004, TASK-007, TASK-009, TASK-020 |
| TASK-031 | Verificar compatibilidad integrada y ensayar rollout/restore | HIGH | PHASE-6 | TODO | TASK-003, TASK-005, TASK-008, TASK-009, TASK-010, TASK-011, TASK-012, TASK-013, TASK-014, TASK-015, TASK-016, TASK-017, TASK-018, TASK-019, TASK-020, TASK-021, TASK-022, TASK-023, TASK-024, TASK-025, TASK-026, TASK-027, TASK-028, TASK-029, TASK-030 | NONE |

## TASK-001 — Fijar baseline aislada y pruebas PostgreSQL de integridad

Status: COMPLETED
Priority: HIGH
Phase: PHASE-0
Category: Testing

### Objective

Fijar baseline aislada y pruebas PostgreSQL de integridad. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-24: Logs sin correlación uniforme, duración/query count/calls externos; algunos catch retornan vacío. Tests crean metadata en SQLite, no ejecutan Alembic ni reproducen locks, índices parciales/pgvector y restricciones Postgres. No se encontraron workflows CI versionados.

### Evidence / Location

- `app/logging.py:1; tests/conftest.py:51,79; pytest.ini; pyproject.toml; app/services/applications/dashboardService.py:420` (Confidence: HIGH). 
- Alcance de edición conocido: tests/conftest.py; tests de integración nuevos; pytest.ini; pyproject.toml solo tooling dev; workflow CI nuevo; documentación de ejecución.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita.

### Proposed Solution

Conservar suite SQLite y añadir fixture PostgreSQL+pgvector y Redis desechables sin credenciales de usuario. Bloquear red externa salvo servicios de test. Capturar contratos de auth, CV, cuotas, candidaturas, progreso y Career Lab antes de refactors. Añadir contadores SQL y harness de dos sesiones para tareas posteriores. Registrar estado operativo disponible sin conectarse a producción por defecto.

### Scope

IN SCOPE:

- tests/conftest.py; tests de integración nuevos; pytest.ini; pyproject.toml solo tooling dev; workflow CI nuevo; documentación de ejecución.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- tests/conftest.py; tests de integración nuevos; pytest.ini; pyproject.toml solo tooling dev; workflow CI nuevo; documentación de ejecución.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: NONE

### Blocks

Blocks: TASK-003, TASK-004, TASK-005, TASK-006, TASK-007, TASK-008, TASK-009, TASK-010, TASK-011, TASK-012, TASK-013, TASK-014, TASK-015, TASK-016, TASK-017, TASK-018, TASK-019, TASK-020, TASK-021, TASK-022, TASK-023, TASK-024, TASK-025, TASK-026, TASK-027, TASK-028, TASK-029, TASK-030

### Parallelization

Can run in parallel with: TASK-002

Grupo A; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [x] Se implementó el resultado concreto: Fijar baseline aislada y pruebas PostgreSQL de integridad.
- [x] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [x] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [x] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [x] Relevant tests pass.
- [x] No unrelated refactor was introduced.

### Validation

Reproducir baseline 173 passed/1 skipped en lane rápida; búsqueda vectorial corre en lane PostgreSQL, no se da por cubierta por SQLite. Probar aislamiento: una URL no local se rechaza por el harness. Publicar comandos y versiones; no exigir lint/typecheck inexistentes: definir herramienta/alcance si se incorporan.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Completion Notes

**Entregado.** Dos lanes con aislamiento verificado, harness de medición/concurrencia y contratos capturados. Documentación de ejecución en [`docs/TESTING.md`](../TESTING.md).

**Cambios**

- `tests/isolation.py` (nuevo): se aplica en `tests/conftest.py` antes de importar `app.*`, porque `app/db.py:10` y `app/app.py:10` llaman `load_dotenv()` y `app/db.py` construye el engine en tiempo de import. Neutraliza `load_dotenv`/`find_dotenv`, instala credenciales ficticias `test-*` (con `REDIS_URL` vacía, de modo que la lane rápida usa el counter store en memoria) y bloquea `socket.create_connection` / `socket.connect` / `socket.connect_ex` fuera de loopback. `assert_local_url()` rechaza una URL de lane no local; `allow_test_service()` habilita explícitamente un servicio desechable.
- `tests/harness.py` (nuevo): `count_queries(engine)` → `QueryCounter` (`selects`, `writes`, `total`, `matching`) y `two_sessions(session_factory)` → dos `AsyncSession` independientes. Son las primitivas que las tareas posteriores usan para presupuestos N+1 y transacciones entrelazadas.
- `tests/conftest.py`: cabecera reemplazada por `apply_isolation()` (sustituye al `os.environ.setdefault("DB_DISABLE_POOL", "1")` previo, que ahora forma parte del conjunto ficticio); añadidos los fixtures `query_counter` y `two_db_sessions`. No se tocó ningún fixture existente.
- `tests/integration/` (nuevo, lane opt-in): `conftest.py` con `pg_engine`, `pg_sessionmaker`, `pg_session`, `pg_two_sessions`, `pg_query_counter` y `redis_client`; skip limpio cuando `TEST_DATABASE_URL_PG` / `TEST_REDIS_URL` no están.
- `tests/test_isolation_harness.py` (nuevo, 11 tests): el harness como control — dotenv desactivado, credenciales placeholder, salida externa bloqueada, loopback intacto, URL de lane no local rechazada, contadores y dos sesiones.
- `tests/test_contract_baseline.py` (nuevo, 23 tests, marca `contract`): auth, CV, cuota IA, candidaturas, progreso y Career Lab.
- `pytest.ini`: `addopts` pasa de coverage-por-defecto a `-q`, así que un `pytest` limpio ya no escribe `htmlcov/`, `coverage.xml` ni `.coverage` en el repositorio; coverage queda opt-in. Registradas las marcas `integration`, `postgres`, `redis`, `contract`.
- `pyproject.toml`: `[tool.coverage.run]` / `[tool.coverage.report]` fijan el alcance de la cobertura opt-in. Sin dependencias nuevas.
- `.github/workflows/tests.yml` (nuevo): job `fast` (sin secretos, a propósito) y job `integration` con `pgvector/pgvector:pg16` y `redis:7-alpine` en loopback.
- `docs/TESTING.md` (nuevo) y enlace desde `tests/README.md`.

**Validación ejecutada**

- Baseline previa, con `.env` real todavía cargado: `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider -q` → **173 passed, 1 skipped en 20.08 s**.
- Misma suite ya con aislamiento aplicado (sin leer `.env`): → **173 passed, 1 skipped en 21.79 s**. La baseline se reproduce sin credenciales reales en el proceso.
- Suite completa por defecto tras añadir los tests nuevos: `.venv/bin/python -m pytest -p no:cacheprovider` → **208 passed, 10 skipped en 21.73 s**. Los 10 skips son 1 preexistente + 9 de la lane de integración que se saltan sin sus URLs.
- Lane PostgreSQL/Redis contra servicios desechables reales (`pgvector/pgvector:pg16` en 127.0.0.1:55432, `redis:7-alpine` en 127.0.0.1:56379): `TEST_DATABASE_URL_PG=... TEST_REDIS_URL=... .venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/integration` → **10 passed en 2.10 s**. Incluye `create_all`/`drop_all` de toda la metadata sobre PostgreSQL, orden por `l2_distance` en una columna `vector(384)` real, bloqueo efectivo de `SELECT ... FOR UPDATE` entre dos sesiones, `IntegrityError` por unique bajo dos sesiones, y `RedisCounterStore` (TTL fijado solo al crear, `reserve_incr` sembrado desde uso en DB, `decr` con piso en cero, ventana deslizante atómica: 20 llamadas concurrentes con límite 5 → exactamente 5 permitidas, y `CounterStoreError` cuando Redis no responde).
- Aislamiento comprobado como exige Validation: `socket.create_connection(("example.com", 80))` lanza `ExternalConnectionBlocked`, y `assert_local_url` rechaza `postgresql+asyncpg://…@db.example.com` y `redis://cache.internal.example.com`. Loopback sigue accesible.
- Versiones: Python 3.10.19, pytest 9.0.2, pytest-asyncio 1.3.0, pytest-cov 7.0.0, plataforma darwin.

**Hallazgo registrado, no corregido (fuera de Scope)**

`GET /api/v1/dashboard/stats` **escribe**: la primera lectura hace `INSERT INTO user_stats` del llamante, así que no es una proyección pura. Es F-15 y pertenece a TASK-016, cuyo criterio dice "GET no escribe caches". Queda caracterizado en `test_dashboard_stats_currently_writes_a_user_stats_row_on_read` (1 escritura en la primera lectura, 0 en la segunda). Cuando TASK-016 lo corrija, ese test debe pasar a exigir `writes == 0`. No se cambió el comportamiento aquí.

**Límites de la validación**

- La cadena Alembic **no** se ejecuta todavía en la lane: la baseline de migraciones es TASK-009. La lane crea el schema con `Base.metadata.create_all`, lo que prueba compatibilidad de la metadata con PostgreSQL, no la reproducibilidad de las migraciones.
- El workflow de CI se versiona pero no se ha ejecutado en GitHub Actions desde esta sesión; su equivalente local sí (ambas lanes, arriba).
- Sin smoke de navegador: TASK-001 no toca frontend.
- No se conectó a producción ni se ejecutó ninguna llamada pagada. Las credenciales del proceso de test son placeholders `test-*`.

**Lint / typecheck: N/A.** No hay linter ni type checker configurado en el repositorio (`ruff`, `flake8`, `mypy`, `pyright` ausentes de `pyproject.toml`, `requirements.txt` y configuración versionada) y esta tarea no introduce uno. Documentado en `docs/TESTING.md`.

### Estimated Impact

Security: LOW
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM


## TASK-002 — Retirar secretos versionados y unificar destino de migraciones

Status: COMPLETED
Priority: CRITICAL
Phase: PHASE-1
Category: Security

### Objective

Retirar secretos versionados y unificar destino de migraciones. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-01: SECRET DETECTED. La configuración de Alembic contiene una URL remota con usuario y contraseña; otro candidato aparece en el script de migración versionado. No se comprobó su vigencia. Además, Alembic usa sqlalchemy.url mientras la aplicación usa DATABASE_URL: pueden apuntar a bases distintas.

### Evidence / Location

- `alembic.ini:90; scripts/migrate_sqlite_to_postgres.py:26; alembic/env.py:85` (Confidence: HIGH). 
- Alcance de edición conocido: alembic.ini; alembic/env.py solo resolución de URL; scripts/migrate_sqlite_to_postgres.py; documentación segura de rotación y configuración.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita.

### Proposed Solution

Retirar literales, resolver explícitamente la URL de migración desde configuración segura y fallar si falta. Rotar/revocar las credenciales afectadas mediante el responsable de infraestructura; verificar consumidores antes del cambio. Revisar historial con salida redactada. No imprimir valores ni reescribir el historial automáticamente.

### Scope

IN SCOPE:

- alembic.ini; alembic/env.py solo resolución de URL; scripts/migrate_sqlite_to_postgres.py; documentación segura de rotación y configuración.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- alembic.ini; alembic/env.py solo resolución de URL; scripts/migrate_sqlite_to_postgres.py; documentación segura de rotación y configuración.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: NONE

### Blocks

Blocks: TASK-009, TASK-029

### Parallelization

Can run in parallel with: TASK-001

Grupo A; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [x] Se implementó el resultado concreto: Retirar secretos versionados y unificar destino de migraciones.
- [x] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [x] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [x] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [x] Relevant tests pass.
- [x] No unrelated refactor was introduced.

### Validation

Escaneo redactado sin coincidencias en el árbol; conexión exclusivamente a PostgreSQL desechable; comprobación de URL ausente y configuración app/migrador consistente; evidencia de revocación sin valores.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Nunca restaurar el secreto al hacer rollback. Mantener configuración env compatible y rotar coordinadamente consumidores. La parte operativa queda BLOCKED si el ejecutor no tiene acceso autorizado para revocar; no marcar completa solo por quitar el literal. No reescribir historial ni revocar otras credenciales fuera del alcance.

### Completion Notes

**Completada.** Parte de código entregada el 2026-09-05; parte operativa (rotación y revocación) ejecutada por el propietario el 2026-09-06 y verificada de punta a punta — ver Evidencia de revocación al final.

**Alcance del secreto (verificado sin imprimir valores)**

Comparando `alembic.ini:90`, `scripts/migrate_sqlite_to_postgres.py:26` y el `DATABASE_URL` de `.env`: **los tres son la misma credencial** — mismo usuario `neondb_owner`, mismo host Neon pooler, misma base `neondb` y la misma contraseña. Es decir, el literal versionado es la credencial de producción **en uso**, con permisos de escritura.

`git log -S` la localiza en el commit `6d89af0` (y `alembic.ini` se añadió en `6fdeca5`): **sigue en el historial**. Retirar el literal del árbol de trabajo no revoca nada. Hasta que se rote, cualquier clon o fork existente conserva acceso de escritura a producción. No se reescribió el historial (fuera de alcance y requiere coordinación del equipo).

**Cambios**

- `alembic.ini`: retirado el literal. `sqlalchemy.url` queda comentada con la explicación de por qué no debe fijarse; `alembic/env.py` la inyecta en tiempo de ejecución.
- `alembic/env.py` (solo resolución de URL, según Scope): `resolve_migration_url()` toma `ALEMBIC_DATABASE_URL` y, si no está, `DATABASE_URL` — **la misma variable que lee `app/db.py`**, con lo que migrador y aplicación no pueden apuntar a bases distintas por defecto. `ALEMBIC_DATABASE_URL` existe para el caso legítimo de migrar por el endpoint directo mientras la app pasa por el pooler. `_to_sync_url()` traduce solo el driver (`postgresql+asyncpg` → `postgresql+psycopg`), conservando usuario, host y base, para no necesitar una segunda URL que pueda derivar. Si no hay ninguna configurada, `RuntimeError` explícito: sin fallback silencioso. `run_migrations_offline` y `run_migrations_online` usan ambos el resolver.
- `alembic/env.py`: cada ejecución online imprime el destino **redactado** (`esquema://host/base`, sin usuario ni contraseña) mediante `_redacted()`, para poder confirmar contra qué base se va a migrar sin filtrar la credencial a los logs de CI.
- `scripts/migrate_sqlite_to_postgres.py`: eliminado el destino por defecto. `_resolve_postgres_url()` exige `POSTGRES_URL` y aborta con `SystemExit` e instrucciones si falta. La resolución es diferida hasta `main()`, así que importar el script no aborta. Un script que **escribe** en una base no debe tener destino implícito.
- `tests/test_migration_config.py` (nuevo, 9 tests): regresión que falla si vuelve a aparecer una URL con credenciales embebidas en los tres archivos, si `alembic.ini` vuelve a fijar `sqlalchemy.url`, si la resolución deja de fallar sin configuración, si el override deja de tener prioridad, o si la redacción filtra usuario/contraseña.
- `docs/DATABASE_CONFIG.md` (nuevo): tabla de configuración por componente, cómo comprobar el destino antes de migrar, estado de F-01 y runbook de rotación en 7 pasos. Sin ningún valor secreto.

**Validación ejecutada**

- Escaneo redactado del árbol: sin coincidencias de URL con credenciales embebidas en `alembic.ini`, `alembic/env.py` ni `scripts/migrate_sqlite_to_postgres.py`. Cubierto por `test_no_credentials_in_versioned_migration_config`.
- `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/test_migration_config.py` → **9 passed**.
- Conexión exclusivamente a PostgreSQL desechable: `DATABASE_URL='postgresql+asyncpg://testuser:testpw@127.0.0.1:55432/studentscompass_test' .venv/bin/alembic current` → conecta y anuncia `alembic: migrating postgresql+psycopg://127.0.0.1:55432/studentscompass_test`. La traducción de driver funciona contra un servidor real.
- URL ausente: `DATABASE_URL="" ALEMBIC_DATABASE_URL="" .venv/bin/alembic current` → falla en el arranque. **Matiz honesto:** el fallo lo emite `app/db.py:40` (que `env.py` importa por su `Base`) antes de llegar a `resolve_migration_url()`. El resultado es el exigido —fallo duro, mensaje claro, sin fallback— pero el resolver propio se verifica de forma directa en `test_missing_configuration_fails_loudly`.
- Consistencia app/migrador comprobada en `test_migrator_defaults_to_the_application_database`: con `DATABASE_URL=postgresql+asyncpg://u:p@host/db`, el migrador resuelve `postgresql+psycopg://u:p@host/db` — mismo usuario, host y base.
- Suite completa: `.venv/bin/python -m pytest -p no:cacheprovider` → **217 passed, 10 skipped en 35.45 s**. Sin regresiones.
- No se ejecutó ninguna migración contra producción.


**Evidencia de revocación — 2026-09-06 (parte operativa completada)**

Ejecutada por el propietario del proyecto (acceso autorizado a Neon y a Google Cloud). Ninguna credencial pasó por la conversación ni se registra aquí.

- **Rotación:** reset de contraseña del rol `neondb_owner` en Neon.
- **Consumidor actualizado:** Cloud Run `studentscompass-api`, proyecto `gen-lang-client-0908704200`, región `us-central1`. Revisión `studentscompass-api-00013-mq6` → **`studentscompass-api-00015-kxp`**, con `Ready=True`, `ConfigurationsReady=True`, `RoutesReady=True`.
- **Formato verificado:** el nuevo `DATABASE_URL` conserva driver `postgresql+asyncpg`, usuario `neondb_owner`, host pooler y base `neondb`, sin query params. Comparación por hash: el valor cambió respecto a la revisión anterior.
- **Servicio en funcionamiento:** `GET /` → 200. `POST /auth/jwt/login` con credenciales inexistentes → **400 `LOGIN_BAD_CREDENTIALS`**, no 500: la aplicación consultó la tabla `users` con la credencial nueva, luego la conectividad a la base es real y no solo un arranque sin tráfico.
- **Credencial antigua revocada:** intento de conexión directa a Neon con el valor anterior → el servidor **rechaza la autenticación explícitamente**. El acceso filtrado está cerrado.

**Alcance de la exposición (para el registro)**

El repositorio `github.com/manolisfcb/StudentsCompass` es **público**. La credencial estuvo expuesta desde el commit `6d89af0` (2026-01-21), y de nuevo en `f8a58f8` (2026-01-22), hasta la rotación del 2026-09-06: aproximadamente **7 meses y medio** de exposición pública. Sigue presente en el historial de Git, pero ya no es utilizable.

**Pendiente, elevado a tareas propias (no bloquea esta ficha)**

1. **Revisión de logs de acceso de Neon** del periodo 2026-01-21 → 2026-09-06, buscando conexiones desde IPs ajenas a Cloud Run. La rotación cierra el acceso futuro; no responde si hubo uso indebido durante la ventana. Requiere acceso a la consola de Neon.
2. **`app/credentials/google_drive.json`** estuvo commiteado (`14b6224`) y se eliminó después (`eab8902`), pero permanece en el historial de un repositorio público. Por tamaño (313–741 bytes) parece un client config de OAuth, no una clave de servicio; no se inspeccionó su contenido. Esas credenciales también deben rotarse.

El escaneo del historial completo (161 commits) no encontró patrones de credenciales AWS (`AKIA…`), Google API (`AIza…`), HuggingFace (`hf_…`), OpenAI (`sk-…`) ni Apify. `.env` nunca se commiteó (`.gitignore:1`). Las otras 13 variables de entorno de Cloud Run no estuvieron expuestas públicamente.

**Riesgo detectado, no modificado (fuera de Scope)**

En local, `app/db.py` y `app/app.py` cargan `.env`, así que un `alembic upgrade head` sin variables explícitas apunta a lo que `.env` defina — hoy, producción. El print redactado del destino lo hace visible, y `docs/DATABASE_CONFIG.md` indica exportar `ALEMBIC_DATABASE_URL` hacia una base desechable al probar. Un guard que exija confirmación explícita para un destino no local cambiaría el flujo operativo del migrador: corresponde a TASK-009, que es dueña de las rutas de baseline/upgrade.

**Lint / typecheck: N/A** — no hay herramienta configurada en el repositorio (ver `docs/TESTING.md`).

### Estimated Impact

Security: HIGH
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: HIGH


## TASK-003 — Restringir borrado de posts al propietario

Status: COMPLETED
Priority: CRITICAL
Phase: PHASE-1
Category: Security / Bug Fix

### Objective

Restringir borrado de posts al propietario. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-02: La ruta exige autenticación pero no pasa user.id al servicio. El servicio busca solamente por post_id y borra el registro: cualquier usuario autenticado con un ID puede borrar publicaciones ajenas.

### Evidence / Location

- `app/routes/postRoute.py:83 delete_post; app/services/community/postService.py:36 delete_post` (Confidence: HIGH). 
- Alcance de edición conocido: app/routes/postRoute.py delete_post; app/services/community/postService.py delete_post; tests/test_posts.py y prueba ownership nueva.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato.

### Proposed Solution

Pasar el actor explícitamente y filtrar por post_id y user_id; responder 404 para ajeno/inexistente. Definir por separado el tratamiento de posts legacy con user_id nulo; no conceder privilegios administrativos implícitos.

### Scope

IN SCOPE:

- app/routes/postRoute.py delete_post; app/services/community/postService.py delete_post; tests/test_posts.py y prueba ownership nueva.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/routes/postRoute.py delete_post; app/services/community/postService.py delete_post; tests/test_posts.py y prueba ownership nueva.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001

### Blocks

Blocks: TASK-006, TASK-031

### Parallelization

Can run in parallel with: TASK-004, TASK-007, TASK-009, TASK-020, TASK-030

Grupo B; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [x] Se implementó el resultado concreto: Restringir borrado de posts al propietario.
- [x] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [x] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [x] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [x] Relevant tests pass.
- [x] No unrelated refactor was introduced.

### Validation

Prueba A crea, B intenta borrar y recibe 404 sin cambios; A borra; anónimo rechazado; registro inexistente no produce 500.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Completion Notes

**Bug Fix entregado.** El borrado de publicaciones ahora exige propiedad.

**Cambios**

- `app/services/community/postService.py` — `delete_post(post_id, *, user_id)`: la propiedad forma parte del **lookup**, no de una comprobación posterior. El `SELECT` filtra por `id` **y** `user_id`, de modo que la publicación de otro usuario es indistinguible de una inexistente y el endpoint no sirve para sondear qué IDs existen. Devuelve `bool` en lugar de lanzar `Exception("Post not found")`, que era la causa del 500.
- `app/routes/postRoute.py` — `delete_post` pasa el actor (`user_id=user.id`) y responde `404 Post not found` cuando no se borró nada. La respuesta de éxito se mantiene byte a byte: `{"detail": "Post deleted successfully"}`.

**Posts legacy con `user_id` NULL (tratado por separado, según Proposed Solution)**

`PostModel.user_id` es nullable. La comparación `PostModel.user_id == user_id` nunca casa con NULL, así que esas publicaciones **no** son borrables por esta ruta: pertenecen a nadie y borrarlas es una operación deliberada aparte, no un privilegio que se conceda implícitamente al primer usuario que lo pida. No se concedió ningún privilegio administrativo y no se borró ningún dato legacy. Está documentado en el docstring del servicio y cubierto por `test_legacy_post_without_an_author_is_not_deletable`.

**Validación ejecutada** — `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/test_posts.py` → **6 passed en 1.01 s**, cubriendo exactamente los casos que pide Validation:

| Caso | Test | Resultado |
| --- | --- | --- |
| A crea, B intenta borrar → 404 y sin cambios | `test_other_user_cannot_delete_a_post_they_do_not_own` | 404, la fila sigue existiendo |
| A borra lo suyo | `test_owner_can_delete_their_own_post` | 200, contrato de respuesta intacto, fila eliminada |
| Anónimo rechazado | `test_anonymous_caller_is_rejected` | 401, la fila sigue existiendo |
| Registro inexistente no produce 500 | `test_unknown_post_id_is_404_not_500` | 404 |
| Legacy sin autor | `test_legacy_post_without_an_author_is_not_deletable` | 404, la fila sigue existiendo |

**Prueba de que el test detecta la vulnerabilidad (evidencia anterior/posterior)**

Se retiró temporalmente el filtro `PostModel.user_id == user_id` para reproducir F-02: `test_other_user_cannot_delete_a_post_they_do_not_own` y `test_legacy_post_without_an_author_is_not_deletable` **fallan** (2 failed, 4 passed). Con el filtro restaurado: 6 passed. Los tests fallan por la causa raíz, no por casualidad.

- Suite completa: `.venv/bin/python -m pytest -p no:cacheprovider` → **222 passed, 10 skipped en 22.76 s**. Sin regresiones.

**Notas**

- `delete_post` no tiene más llamadores: `grep` sobre `app/` confirma que solo lo invoca la ruta, y no hay referencias a `delete_post` en `app/static/js/` ni en `app/templates/`. No hay contrato de frontend que migrar.
- Verificación de concurrencia en PostgreSQL: no aplica aquí. El borrado es un único `DELETE` filtrado por clave primaria y propietario; dos borrados simultáneos del propietario dan 200 y 404, sin estado intermedio incorrecto.
- Sin cambios de esquema, sin migración.

**Lint / typecheck: N/A** — no hay herramienta configurada en el repositorio (ver `docs/TESTING.md`).

### Estimated Impact

Security: HIGH
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM


## TASK-004 — Renderizar nombres de CV y enlaces sin HTML ejecutable

Status: COMPLETED
Priority: CRITICAL
Phase: PHASE-1
Category: Security / Bug Fix

### Objective

Renderizar nombres de CV y enlaces sin HTML ejecutable. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-03: original_filename procede del upload y se inserta directamente en tbody.innerHTML junto con view_url. Existe un sumidero de XSS almacenado; el listado comprobado pertenece al propio usuario, por lo que no se afirma explotación entre cuentas.

### Evidence / Location

- `app/static/js/userProfile.js:433; app/routes/resumeRoute.py:80; app/services/resumes/resumeService.py:61` (Confidence: HIGH). 
- Alcance de edición conocido: app/static/js/userProfile.js lista de CV; sumideros URL en jobs.js/resource_detail.js; helper DOM seguro y pruebas de navegador acotadas.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato.

### Proposed Solution

Construir nodos con textContent, validar esquemas de URL http/https y usar atributos DOM seguros. Revisar los sumideros de URLs de jobs.js y resource_detail.js sin asumir que escapeHtml valida protocolos.

### Scope

IN SCOPE:

- app/static/js/userProfile.js lista de CV; sumideros URL en jobs.js/resource_detail.js; helper DOM seguro y pruebas de navegador acotadas.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/static/js/userProfile.js lista de CV; sumideros URL en jobs.js/resource_detail.js; helper DOM seguro y pruebas de navegador acotadas.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001

### Blocks

Blocks: TASK-026

### Parallelization

Can run in parallel with: TASK-003, TASK-007, TASK-009, TASK-020, TASK-030

Grupo B; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [x] Se implementó el resultado concreto: Renderizar nombres de CV y enlaces sin HTML ejecutable.
- [x] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [x] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [x] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [x] Relevant tests pass.
- [x] No unrelated refactor was introduced.

### Validation

Nombres con etiquetas, comillas y caracteres internacionales se muestran literalmente; enlaces javascript/data rechazados; flujo subir/listar/borrar conservado en navegador.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Completion Notes

**Bug Fix entregado.** El listado de CV construye nodos DOM y todo destino de enlace se valida por esquema.

**Gravedad confirmada en navegador real**

Antes del cambio no era solo un sumidero teórico. Con el `innerHTML` original y un CV llamado `<img src=x onerror="window.__xss=true">Résumé "final" <b>v2</b>.pdf`, Chromium headless ejecuta el payload: `window.__xss === true`. Tras el cambio, con exactamente el mismo dato: `false`. Es XSS almacenado con ejecución de JavaScript arbitrario en el origen de la aplicación, no solo HTML mal renderizado. Como indica F-03, el listado comprobado es el del propio usuario, así que no se afirma explotación entre cuentas.

**Cambios**

- `app/static/js/safeDom.js` (nuevo, helper DOM seguro compartido): `SafeDom.el()` asigna siempre `textContent` (nunca parsea markup) y rechaza que se fijen atributos `on*`, `href` o `src` por esa vía; `SafeDom.link()` construye un `<a>` solo si la URL valida, y si no devuelve un `<span>` con el mismo texto —el usuario sigue viendo el nombre, pero un clic no puede navegar a un destino peligroso—; `SafeDom.safeHttpUrl()` acepta únicamente `http:`/`https:`; `SafeDom.replaceChildren()` sustituye hijos sin `innerHTML`.
- `app/static/js/userProfile.js`: `loadResumes` ya no compone una plantilla `innerHTML`. La nueva `buildResumeRow(item)` crea `<tr>/<td>/<a>/<button>` con `SafeDom`, de modo que `original_filename` y `view_url` nunca se interpretan como markup. Se conservan clases, estilos inline, `data-resume-id`, `target="_blank"` y el resto de la estructura de la tabla.
- `app/static/js/jobs.js`: nuevo `safeLinkHref()` junto a `escapeHtml`, aplicado a los tres sumideros de URL (`job.url` en el botón Apply, `job.company_website`, `application.application_url`). **`escapeHtml` no valida protocolos**: `javascript:alert(1)` sobrevive intacto al escapado y sigue siendo un `href` vivo. Estas URLs provienen de ofertas scrapeadas, así que ahora pasan primero por validación de esquema; si no es http/https no se emite enlace.
- `app/static/js/resource_detail.js`: `linkUrl` ya estaba comprobado con `isSafeHttpUrl`, pero se interpolaba sin escapar en el atributo. Ahora se escapa también, para que una comilla en la URL no pueda salir del atributo.
- `app/templates/base.html`: una línea para cargar `safeDom.js` con `defer` antes del script de página. Los scripts `defer` se ejecutan en orden de documento, así que el helper siempre está definido. Es el único punto de carga común de las tres páginas afectadas; definirlo en cada archivo habría duplicado el helper.
- `pytest.ini`: registrada la marca `browser`. `pyproject.toml`: `playwright` en el grupo dev. `.github/workflows/tests.yml`: job `browser`. `docs/TESTING.md`: sección de la lane de navegador.

**Validación ejecutada** — `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/test_frontend_xss_browser.py` → **14 passed en 1.46 s**, en Chromium 151.0.7922.34 real, con la página servida desde un origen `http://` real (no `about:blank`, cuyo origen opaco no representa cómo corre la app) y todas las peticiones resueltas por el propio manejador de rutas del test: el navegador no alcanza ningún host externo.

Cubre exactamente lo que pide Validation:

| Caso | Resultado |
| --- | --- |
| Nombres con etiquetas (`<script>`, `<img onerror>`, `<b>`) | Se muestran literalmente; 0 elementos inyectados; `window.__xss === false` |
| Comillas y apóstrofos | Literales |
| Caracteres internacionales (`Curriculum Vitæ – Ünïcodé 简历.pdf`) | Literales |
| `javascript:` (incl. `JaVaScRiPt:`), `data:`, `vbscript:` | Sin `<a>`; el nombre se muestra como texto; sin ejecución |
| `http`, `https` y URLs relativas | Enlace intacto, con `target="_blank"` y `rel="noopener noreferrer"` |
| Flujo listar/borrar en navegador | 2 filas renderizadas, botones de borrado conectados, el clic emite `DELETE /api/v1/profile/cv/<id>` con el id correcto |
| Lista vacía | Estado vacío correcto |
| Contrato de `SafeDom.safeHttpUrl` | 7 valores peligrosos rechazados, 3 válidos aceptados |

**Prueba de que los tests detectan la vulnerabilidad (evidencia anterior/posterior)**

Restaurando el `innerHTML` original: **9 failed, 5 passed**. Con el cambio aplicado: **14 passed**. Fallan por la causa raíz.

- Suite completa: `.venv/bin/python -m pytest -p no:cacheprovider` → **236 passed, 10 skipped en 24.66 s**. Sin regresiones.
- Lane PostgreSQL/Redis revalidada tras el cambio → **10 passed en 2.05 s**.

**Límites de la validación**

- El smoke de navegador cubre **listar y borrar** con `fetch` interceptado en la página; la **subida** de un archivo no se ejercita end-to-end contra el backend real (requeriría un servidor vivo con almacenamiento aislado). Esa ruta sigue cubierta por los tests de backend existentes (`tests/test_resume.py`, `tests/test_upload_size_limit.py`), pero no por un smoke de navegador.
- Los sumideros corregidos en `jobs.js` y `resource_detail.js` están verificados por lectura del código y por el contrato de `SafeDom.safeHttpUrl` en navegador; no tienen todavía un smoke de página completa propio, porque sus páginas dependen de más estado de backend del que esta tarea acota.
- `playwright` se instaló en el `.venv` y se declaró en el grupo dev, pero el navegador es una descarga aparte (`python -m playwright install chromium`). Sin cualquiera de los dos, los tests marcados `browser` se saltan solos en vez de fallar.
- El job `browser` de CI se versiona pero no se ha ejecutado en GitHub Actions desde esta sesión.

**Lint / typecheck: N/A** — no hay herramienta configurada en el repositorio (ver `docs/TESTING.md`).

### Estimated Impact

Security: HIGH
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM


## TASK-005 — Dar identidad única a objetos y hacer recuperable su ciclo de vida

Status: COMPLETED
Priority: CRITICAL
Phase: PHASE-1
Category: Security / Database / Bug Fix

### Objective

Dar identidad única a objetos y hacer recuperable su ciclo de vida. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-04: Los CV usan timestamp con precisión de segundos + nombre, sin usuario/UUID. S3 usa esa clave y put_object; media S3 usa directamente el nombre saneado. Dos cargas pueden compartir objeto. delete_resume borra almacenamiento antes del commit DB y no exige éxito del proveedor: un rollback puede dejar un registro cuyo archivo ya no existe.

### Evidence / Location

- `app/services/resumes/resumeService.py:166,202; app/services/storage/s3Service.py:54; app/services/storage/mediaStorageService.py:75; app/models/resumeModel.py:14` (Confidence: HIGH). 
- Alcance de edición conocido: app/services/resumes/resumeService.py; app/services/storage/s3Service.py; app/services/storage/mediaStorageService.py; modelo/migración nueva para intención de cleanup si procede; tests de storage.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato.

### Proposed Solution

Claves nuevas opacas y únicas por objeto, con identidad del propietario o UUID. Mantener resolución de claves legacy. Implementar intención durable de borrado y reintentos idempotentes después de confirmar la decisión DB; compensar uploads cuyo alta DB falla. Inventariar referencias compartidas antes de eliminar cualquier objeto. Primero testear colisión y fallos; expandir schema si hace falta para intención de borrado, backfill solo referencias conocidas, verificar objetos compartidos, cambiar writer y preservar reader legacy. No mover/borrar todo el bucket.

### Scope

IN SCOPE:

- app/services/resumes/resumeService.py; app/services/storage/s3Service.py; app/services/storage/mediaStorageService.py; modelo/migración nueva para intención de cleanup si procede; tests de storage.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/services/resumes/resumeService.py; app/services/storage/s3Service.py; app/services/storage/mediaStorageService.py; modelo/migración nueva para intención de cleanup si procede; tests de storage.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-009

### Blocks

Blocks: TASK-006, TASK-031

### Parallelization

Can run in parallel with: TASK-010, TASK-014, TASK-017, TASK-019, TASK-024

Grupo C; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Dar identidad única a objetos y hacer recuperable su ciclo de vida.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Dos uploads con mismo nombre/instante tienen claves distintas; borrar uno no afecta al otro; inyección de fallo DB/storage no pierde archivos referenciados; reintento de borrado converge; comprobar referencias legacy.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Reader debe seguir aceptando claves antiguas y nuevas. Rollback del código conserva nuevas claves; no volver al generador colisionable. No borrar intención pendiente ni objetos durante downgrade; restaurar objeto desde copia/versioning solo tras verificar referencia.

### Completion Notes

**Claves opacas y únicas.** `app/services/storage/objectKeys.py` genera
`<folder>/[<owner>/]<uuid4hex><ext>`. `S3Service.upload_file` ya no deriva la
clave del nombre subido (`basename(file_name)`): la construye, así que dos
subidas nunca comparten objeto y `put_object` no puede sobrescribir el archivo
de otro usuario. `ResumeService` pasa `owner_id`, de modo que los CV quedan bajo
`resumes/<user_id>/`. El nombre visible sigue en `original_filename` en DB, lo
que además saca del bucket cualquier nombre hostil. El parámetro `owner_id` se
añadió al Protocol `StorageService` con default `None`, así que los callers que
no conocen dueño (media, recursos) no cambian de contrato pero sí obtienen
claves únicas.

**Compensación de upload.** `create_resume_from_upload` envuelve el alta DB: si
falla, hace rollback y borra el objeto recién subido; si el proveedor tampoco
coopera, registra intención durable y commitea solo eso. El fallo original nunca
queda enmascarado por el fallo de compensación.

**Borrado: DB primero, intención durable, reintento idempotente.** Tabla nueva
`storage_deletion_intents` (`StorageDeletionIntentModel`, revisión
`c3e8b1a7d240`, puramente aditiva). `delete_resume` ahora: verifica propiedad →
**inventaría referencias compartidas** (`is_object_still_referenced`) → borra la
fila y escribe la intención **en la misma transacción** → commit → recién
entonces llama al proveedor. Commit y el objeto está registrado como no deseado
aunque el proceso muera; rollback y no pasó nada. `StorageCleanupService`
ejecuta la intención inmediata y reintenta las pendientes; `delete_object` sobre
una clave ausente es un no-op, que es lo que hace idempotente el reintento.

**Referencias compartidas.** Las claves legacy se derivaban del nombre y podían
estar compartidas por varias filas. El objeto solo se borra cuando ninguna otra
fila lo referencia; mientras tanto se conserva y se registra en log. Cubierto
por `test_an_object_two_rows_share_is_not_deleted`.

**Claves legacy.** Nada reescribe ni migra claves almacenadas: los readers
siguen resolviendo la clave que lleve la fila. `test_legacy_keys_are_still_readable`
lo fija.

**Bug encontrado y corregido durante la tarea.** Al conectar el baseline en
`alembic/env.py`, la comprobación de base vacía usa `sa.inspect(connection)`, que
abre una transacción implícita; Alembic abría luego la suya y el `upgrade` de una
instalación existente **corría y hacía rollback sin marcar nada**. Corregido con
un `connection.rollback()` explícito antes de `context.configure`, y cubierto por
`test_upgrade_head_commits_on_an_existing_database`, que ejecuta `alembic upgrade
head` de verdad en lugar de llamar solo al helper.

**Fuera de Scope, no tocado.** `adminService.upload_resource_file` ya incluye un
UUID en el nombre y no es colisionable; `postRoute` no pasa `owner_id` a media
(las claves siguen siendo únicas por UUID) porque ese archivo pertenece al Scope
de TASK-006.

**Validación ejecutada.**

- `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/test_storage_object_lifecycle.py`
  → **25 passed**. Cubre: mismo nombre e instante producen claves distintas;
  borrar una subida no afecta a la otra; carpeta hostil no escapa del prefijo;
  extensión whitelisted por forma; fallo de DB borra el objeto huérfano; fallo de
  proveedor en la compensación encola la intención; fallo de proveedor al borrar
  no bloquea el borrado y queda registrado; la intención converge cuando el
  proveedor se recupera; reintentar sobre objeto ya ausente converge; objeto
  compartido por dos filas no se borra; borrado ajeno sigue rechazado; claves
  legacy siguen legibles.
- `TEST_DATABASE_URL_PG=... .venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/integration/test_storage_deletion_intents.py`
  → **3 passed** (camino `ON CONFLICT` de PostgreSQL, unicidad como constraint
  real, reapertura de intención completada).
- Suite completa SQLite → **268 passed, 1 skipped**.
- Carril PostgreSQL + Redis completo → **26 passed**.
- Bootstrap vacío y upgrade forward verificados por CLI: `alembic upgrade head`
  sobre schema vacío → `c3e8b1a7d240 (head)`; rebobinado a `a7f4c2b8d590` y
  reejecutado → `Running upgrade a7f4c2b8d590 -> c3e8b1a7d240` con la tabla
  creada y la versión commiteada.

**Límites de la validación.** No se ejecutó ninguna llamada real a S3 ni a
ImageKit: los proveedores son fakes que reproducen la semántica relevante
(`put_object` sobrescribe, `delete_object` es idempotente). Que S3 se comporte
así es documentación del proveedor, no algo verificado aquí. Tampoco se
inventarió el bucket real: la comprobación de referencias compartidas es sobre
filas de `resumes`, no sobre objetos del bucket, así que un objeto referenciado
desde fuera de esa tabla no está cubierto. No se movió ni borró nada del bucket
de producción.

**Sweeper.** `StorageCleanupService.process_pending()` existe y es idempotente,
pero **no hay todavía un disparador programado** que lo ejecute: hoy solo corre
el intento inmediato tras el commit. Enganchar un job periódico requiere decidir
dónde vive el scheduler, que no está en este Scope.

**Lint/typecheck:** N/A — no hay lint ni typecheck configurados en el proyecto.

### Estimated Impact

Security: HIGH
Performance: MEDIUM
Maintainability: HIGH
Cost: HIGH
Risk: HIGH


## TASK-006 — Acotar multipart, media y expansión de documentos

Status: COMPLETED
Priority: CRITICAL
Phase: PHASE-1
Category: Security / Cost / Bug Fix

### Objective

Acotar multipart, media y expansión de documentos. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-05: CV comprueba tamaño después de await cv.read(); Content-Length puede faltar y el parser multipart ya se ejecutó. Posts no aplica cota de bytes/tipo antes de leer o copiar a disco y enviar a terceros. Un límite de archivo comprimido tampoco limita DOCX descomprimido. Impacto potencial: RAM, disco y almacenamiento pagado.

### Evidence / Location

- `app/routes/resumeRoute.py:31; app/routes/postRoute.py:58; app/services/storage/mediaStorageService.py:39,75; app/core/resume_analyzer/resume_text_extractor.py:32` (Confidence: HIGH). 
- Alcance de edición conocido: app/routes/resumeRoute.py; app/routes/postRoute.py upload_post; app/services/storage/mediaStorageService.py lectura; app/core/resume_analyzer/resume_text_extractor.py; config/middleware de tamaño; tests/test_upload_size_limit.py.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato.

### Proposed Solution

Definir presupuestos por ruta, lectura incremental hasta límite+1, límite de cuerpo en ingreso/ASGI antes del multipart, tipos y firmas permitidos y límites de expansión DOCX. Mantener MIME admitidos por el producto y respuestas 413/400 explícitas.

### Scope

IN SCOPE:

- app/routes/resumeRoute.py; app/routes/postRoute.py upload_post; app/services/storage/mediaStorageService.py lectura; app/core/resume_analyzer/resume_text_extractor.py; config/middleware de tamaño; tests/test_upload_size_limit.py.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/routes/resumeRoute.py; app/routes/postRoute.py upload_post; app/services/storage/mediaStorageService.py lectura; app/core/resume_analyzer/resume_text_extractor.py; config/middleware de tamaño; tests/test_upload_size_limit.py.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-003, TASK-005

### Blocks

Blocks: TASK-008, TASK-011

### Parallelization

Can run in parallel with: TASK-012, TASK-015, TASK-021

Grupo D; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Acotar multipart, media y expansión de documentos.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Con/sin Content-Length y multipart chunked sobredimensionado se rechaza antes del proveedor; memoria acotada; archivo pequeño válido funciona; DOCX con expansión excesiva falla de forma controlada.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Completion Notes

**Tres puntos de control, porque uno solo no cubre el problema.**

1. `app/middleware/body_size.py::RequestBodySizeLimitMiddleware` — ASGI puro (no
   `BaseHTTPMiddleware`) para poder situarse **delante** del parser multipart.
   `Content-Length` es el atajo cuando está presente; el conteo incremental sobre
   `receive` es lo único que cubre una petición *chunked*, que no manda
   `Content-Length` en absoluto. Presupuestos por prefijo de ruta, gana el más
   largo. Añadido el último en `app.py` para que envuelva a todo lo demás.
2. `app/core/uploads.py::read_upload_within_limit` — lee la parte ya parseada en
   chunks de 64 KB y corta en cuanto pasa el presupuesto, así que la ruta nunca
   materializa más de un chunk de más.
3. `ensure_allowed_upload` — allowlist de MIME por ruta y comprobación de firma:
   el tipo declarado lo pone el cliente y no vale nada por sí solo.

**CV.** `_read_upload_within_limit` ya no depende de `Content-Length` ni de un
`await cv.read()` sin cota. Ambas rutas (`/profile/cv/upload` y
`/profile/cv/course-audit-upload`) validan además la firma.

**Posts.** `upload_post` no tenía **ninguna** cota de bytes ni de tipo antes de
copiar a disco y enviar al proveedor de pago. Ahora lee acotado, valida tipo y
firma, y pasa los bytes ya validados a `upload_media`. `MediaStorageService`
acepta `file_bytes`/`content_type` para no releer: el `shutil.copyfileobj` de
ImageKit copiaba a disco un cuerpo de cualquier tamaño y el `await file.read()`
de S3 lo metía entero en memoria; ambos usan ya el payload acotado.

**Expansión DOCX.** Una cota sobre el archivo comprimido no acota nada:
`_read_document_part_within_limit` rechaza el tamaño declarado, rechaza un ratio
de compresión implausible, y **además** lee acotado — porque la cabecera del ZIP
también la controla quien sube el archivo, y solo la tercera comprobación no
depende de ella. El fallo es controlado: texto vacío, igual que con cualquier
documento ilegible, con el motivo en log.

**Presupuestos** en `app/config.py`, todos por variable de entorno:
`MAX_UPLOAD_BYTES` (5 MB), `MAX_POST_UPLOAD_BYTES` (10 MB),
`MAX_REQUEST_BODY_BYTES` (1 MB, resto de rutas), `MAX_DOCX_EXPANDED_BYTES`
(20 MB), `MAX_DOCX_COMPRESSION_RATIO` (200). Los del middleware llevan 16 KB de
holgura multipart para que sea la ruta la que decida el límite exacto.

**Cambio de comportamiento declarado (Bug Fix).** Un payload cuya firma
contradice su `Content-Type` ahora recibe 400, y `upload_post` solo acepta la
allowlist de media. Riesgo de regresión considerado: los navegadores derivan el
tipo de la extensión, así que un `.docx` guardado como `.doc` llega etiquetado
`application/msword`; se acepta también la firma ZIP para ese tipo porque es un
documento normal, no un ataque. `image/webp` y MP4/MOV se comprueban por offset
(RIFF y `ftyp`), no por prefijo, que aceptaría un WAV disfrazado.

**Validación ejecutada.**

- `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/test_upload_size_limit.py`
  → **19 passed**. Cubre explícitamente lo que pide Validation: cuerpo con
  `Content-Length` sobredimensionado rechazado **sin leer un solo byte**
  (`seen == []`); cuerpo *chunked* sin `Content-Length` acotado igualmente y sin
  que la app llegue a ver un cuerpo completo; memoria acotada (la lectura corta
  en el presupuesto, y hay caso de payload exactamente en el límite que sí pasa);
  archivo pequeño válido funciona (200); DOCX con expansión excesiva falla de
  forma controlada, con el test anclado en el guard y no solo en el resultado
  vacío —que habría pasado igual sin guard, porque ese XML no parsea.
- Suite completa SQLite → **286 passed, 1 skipped**.
- Carril PostgreSQL + Redis → **26 passed**.

**Límites de la validación.** Todo se ejercitó vía `ASGITransport` en proceso, no
contra un servidor real: no se comprobó cómo se comporta uvicorn/gunicorn ni un
proxy delante al cortar una petición chunked a mitad, ni si el proxy impone su
propio límite antes. Tampoco se midió memoria residente durante una subida
grande; "memoria acotada" está verificado por construcción (la lectura corta en
el presupuesto y la app no recibe el cuerpo completo), no por medición. No se
hizo llamada real a S3 ni a ImageKit.

**Smoke de navegador:** N/A. Esta tarea no toca ningún archivo de frontend; el
único cambio observable desde la UI es un 400 en un payload cuya firma no
coincide, y el flujo real de la UI sube PDF/DOCX auténticos.

**Lint/typecheck:** N/A — no hay lint ni typecheck configurados en el proyecto.

### Estimated Impact

Security: HIGH
Performance: MEDIUM
Maintainability: HIGH
Cost: HIGH
Risk: MEDIUM


## TASK-007 — Contabilizar cada intento Gemini y exigir límites compartidos

Status: COMPLETED
Priority: CRITICAL
Phase: PHASE-1
Category: Cost / Security / Bug Fix

### Objective

Contabilizar cada intento Gemini y exigir límites compartidos. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-06: Sin REDIS_URL o si falla la inicialización, se usa memoria incluso en producción: el presupuesto se multiplica por procesos y reinicios. El guard se llama una vez antes de evaluadores que reintentan: ask_llm_model permite hasta tres intentos por reserva global. El fail-closed sí existe para errores del store después de inicializarse.

### Evidence / Location

- `app/services/ratelimit/counterStore.py:257 get_counter_store; app/services/ai/aiBudgetGuard.py:51; app/services/ai/cvAnalysisService.py:254; app/core/resume_analyzer/llm_model.py:116; app/core/resume_analyzer/resume_audit_llm.py:99` (Confidence: HIGH). 
- Alcance de edición conocido: app/services/ratelimit/counterStore.py; app/services/ai/aiBudgetGuard.py; app/core/resume_analyzer/llm_model.py; resume_audit_llm.py; guards de cvAnalysisService y resumeCourseAuditService; app/config.py; tests IA.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato.

### Proposed Solution

Exigir store compartido para gasto en producción o desactivar IA de forma segura; aplicar guard inmediatamente antes de cada intento del proveedor, con una sola ubicación y sin doble contabilización. Separar unidades de usuario, intentos y consumo monetario; no llamar a un número de requests un límite de dinero. Probar también decremento concurrente de reservas: decr actualmente puede usar DECR seguido de SET al bajar de cero; hacerlo atómico si el caso de test demuestra pérdida de una reserva. No mezclar esta tarea con backfill del ledger.

### Scope

IN SCOPE:

- app/services/ratelimit/counterStore.py; app/services/ai/aiBudgetGuard.py; app/core/resume_analyzer/llm_model.py; resume_audit_llm.py; guards de cvAnalysisService y resumeCourseAuditService; app/config.py; tests IA.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/services/ratelimit/counterStore.py; app/services/ai/aiBudgetGuard.py; app/core/resume_analyzer/llm_model.py; resume_audit_llm.py; guards de cvAnalysisService y resumeCourseAuditService; app/config.py; tests IA.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001

### Blocks

Blocks: TASK-010, TASK-012, TASK-029

### Parallelization

Can run in parallel with: TASK-003, TASK-004, TASK-009, TASK-020, TASK-030

Grupo B; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Contabilizar cada intento Gemini y exigir límites compartidos.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Dos procesos comparten techo; Redis ausente/fallo de inicialización no habilita gasto; tres intentos consumen tres unidades globales; kill switch y fallos transitorios/no reintentables preservan respuestas compatibles.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Completion Notes

**El guard estaba en el lugar equivocado.** `ensure_llm_budget()` se llamaba una
vez por petición de usuario, y justo debajo `ask_llm_model` /
`GeminiResumeAuditEvaluator.evaluate` mandaban hasta **tres** peticiones a
Gemini por esa única reserva. Ahora la comprobación vive dentro del bucle de
reintentos, inmediatamente antes de cada `generate_content`, y se ha quitado de
`cvAnalysisService` y `resumeCourseAuditService` — una sola ubicación por
evaluador, sin doble contabilización. `AIBudgetExhausted` se re-lanza sin
envolver desde ambos bucles: un techo no es un fallo del proveedor, reintentarlo
solo quemaría la ventana de rate, y el llamador necesita reconocerlo para
liberar la reserva del usuario y responder "Manual mode" / 503.

**Tres unidades, separadas de verdad.** `AI_BASE_DAILY_LIMIT` cuenta unidades de
usuario; `AI_GLOBAL_DAILY_ATTEMPTS` y `AI_LLM_ATTEMPTS_PER_MIN` cuentan intentos
al proveedor; ninguna cuenta dinero, y el código ya no llama *budget* a un
número de requests. Los nombres antiguos (`AI_GLOBAL_DAILY_BUDGET`,
`AI_LLM_CALLS_PER_MIN`) se siguen leyendo como variables de entorno vía
`env_int_any`, así que un despliegue existente no cambia de comportamiento. La
clave Redis del contador **no** se renombró a propósito: renombrarla pondría a
cero el techo vivo en el despliegue que lleve este cambio.

**Store compartido exigido para gastar.** Sin `REDIS_URL`, o si la construcción
del cliente Redis falla, `get_counter_store()` cae a memoria; eso está bien para
los límites por IP (best-effort, fail-open) pero un techo por proceso se
multiplica por réplicas y se reinicia con el proceso, así que no es un techo. Con
`ENV=production` y un store no compartido el guard **rechaza** en vez de gastar
(`CounterStore.is_shared` es el dato que lo decide). Escape hatch explícito y
apagado por defecto: `AI_ALLOW_UNSHARED_COUNTER=1` para un despliegue que
realmente sea un único proceso — sin él, un deploy monoproceso legítimo se
quedaría sin IA sin recurso alguno.

**Liberación atómica.** `RedisCounterStore.decr` hacía `DECRBY` y, si el
resultado bajaba de cero, `SET 0`. Un `INCR` que aterrizara entre ambos comandos
quedaba borrado por el `SET`: una reserva perdida y, por tanto, gasto de más.
Ahora es un único script Lua (`_DECR_FLOOR_LUA`). El caso está demostrado, no
supuesto: `test_legacy_release_sequence_drops_a_concurrent_reservation` reproduce
el intercalado exacto contra el Redis real y comprueba que la reserva desaparece;
`test_atomic_release_keeps_a_concurrent_reservation` corre la misma secuencia por
el store y la conserva.

**Validación ejecutada.**

- `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/test_ai_budget_guard.py`
  → **14 passed**. Cubre lo que pide Validation: tres intentos consumen tres
  unidades globales (`calls == 3`, contador `== 3`); error no reintentable
  consume exactamente una; techo alcanzado a mitad de reintentos corta los
  intentos restantes y sale sin envolver; kill switch bloquea **sin** contar
  nada; store no compartido en producción rechaza; fallo de init de Redis en
  producción cae a memoria y **no** habilita gasto; opt-in monoproceso funciona;
  store caído falla cerrado; dos réplicas con objetos de store distintos comparten
  un único techo; 25 intentos concurrentes cuentan 25.
- Carril PostgreSQL + Redis → **31 passed** (incluye los 4 casos nuevos de
  release atómico y el techo global compartido entre dos conexiones Redis
  distintas, que es lo más cerca de "dos procesos" que da el carril).
- Suite completa SQLite → **308 passed, 31 skipped** (los skips son los carriles
  opt-in: PostgreSQL/Redis y navegador).

Comandos exactos del carril:

```
docker run -d --name sc-test-pg -e POSTGRES_PASSWORD=testpw -e POSTGRES_USER=testuser \
    -e POSTGRES_DB=studentscompass_test -p 55432:5432 pgvector/pgvector:pg16
docker run -d --name sc-test-redis -p 56379:6379 redis:7-alpine
TEST_DATABASE_URL_PG=postgresql+asyncpg://testuser:testpw@127.0.0.1:55432/studentscompass_test \
TEST_REDIS_URL=redis://127.0.0.1:56379/0 \
.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/integration
```

**Límites de la validación.** "Dos procesos" se ejercita con dos objetos
`RedisCounterStore` sobre conexiones distintas dentro de un proceso, no con dos
intérpretes ni dos contenedores de la app: lo que se prueba es que el estado vive
en Redis y no en el proceso, no el arranque real de dos réplicas. No se hizo
ninguna llamada real a Gemini — el proveedor es un doble en todos los casos — así
que no está medido el coste monetario real por intento, solo el conteo de
intentos. El rechazo por store no compartido se prueba con `IS_PRODUCTION`
parcheado, no con un despliegue real en producción. `KEEPTTL` exige Redis ≥ 6.0;
verificado contra `redis:7-alpine`, no contra versiones anteriores.

**Smoke de navegador:** N/A. La tarea no toca ningún archivo de frontend; lo
único observable desde la UI es el mensaje "Manual mode" que ya existía.

**Lint/typecheck:** N/A — no hay lint ni typecheck configurados en el proyecto.

### Estimated Impact

Security: HIGH
Performance: MEDIUM
Maintainability: HIGH
Cost: HIGH
Risk: MEDIUM


## TASK-008 — Autorizar archivos de recursos por entidad visible

Status: COMPLETED
Priority: CRITICAL
Phase: PHASE-1
Category: Security / Bug Fix

### Objective

Autorizar archivos de recursos por entidad visible. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-07: /resources/file acepta cualquier key bajo resources/ para un usuario activo y no resuelve recurso/lección ni verifica is_published/is_locked. En contraste, el acceso al recurso sí usa esas restricciones. Conocer una clave permite saltarse el control del catálogo; acceso real depende de objetos existentes.

### Evidence / Location

- `app/routes/resourceRoute.py:33; app/services/resources/resourceService.py:253 download_resource_file; app/services/resources/resourceService.py:118 get_published_resource` (Confidence: HIGH). 
- Alcance de edición conocido: app/routes/resourceRoute.py get_resource_file; app/services/resources/resourceService.py download_resource_file; resourceLessonContentCodec solo resolución de referencia; tests/test_resource_storage.py.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato.

### Proposed Solution

Resolver la clave a una lección/recurso permitido antes de leer storage, o introducir endpoint por lesson_id con compatibilidad controlada para enlaces previos. La mera pertenencia al prefijo no concede acceso.

### Scope

IN SCOPE:

- app/routes/resourceRoute.py get_resource_file; app/services/resources/resourceService.py download_resource_file; resourceLessonContentCodec solo resolución de referencia; tests/test_resource_storage.py.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/routes/resourceRoute.py get_resource_file; app/services/resources/resourceService.py download_resource_file; resourceLessonContentCodec solo resolución de referencia; tests/test_resource_storage.py.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-006

### Blocks

Blocks: TASK-011, TASK-031

### Parallelization

Can run in parallel with: TASK-013, TASK-022, TASK-027

Grupo E; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Autorizar archivos de recursos por entidad visible.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Archivos de recurso publicado y desbloqueado accesibles; bloqueado/no publicado/clave sin asociación devuelve 404; ninguna descarga al proveedor en rechazo; conservar enlaces autorizados.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Completion Notes

**Pertenecer al prefijo no era autorización.** `download_resource_file` aceptaba
cualquier clave bajo `resources/` para cualquier usuario activo; el catálogo
—`is_published`, `is_locked`— solo se aplicaba al recurso, nunca al archivo. Ahora
`resolve_authorized_file_key` resuelve la clave hasta una lección de un recurso
publicado y desbloqueado (o hasta el `external_url` de un recurso visible) **antes**
de tocar el proveedor, con las mismas condiciones que `get_published_resource`.
Sin asociación, no hay descarga.

**Resolución de referencia en el codec.** Una lección guarda el archivo como
clave desnuda (`resources/x.pdf`) o como la URL absoluta que devolvió el
proveedor (`https://bucket.s3.region.amazonaws.com/resources/x.pdf`); ambas
formas tienen que resolver a la misma clave o la autorización no reconocería a la
lección dueña del archivo. `extract_storage_key` recorta query/fragmento,
deshace el percent-encoding y corta desde el prefijo;
`referenced_storage_keys` lo aplica a todos los valores del payload decodificado.
Es lo único que se añadió al codec, como marcaba el Scope.

**El prefiltro SQL no autoriza.** Escanear y decodificar cada lección por
descarga sería un coste innecesario, así que la consulta se acota con un LIKE
sobre el nombre de archivo — pero solo sobre el tramo inicial formado por
caracteres *unreserved*, porque el resto puede venir percent-encodeado en la URL
guardada y entonces el LIKE no casaría (fallo real, detectado por el test de
nombre con espacio antes de darlo por bueno). Si ese tramo sale vacío se escanea
sin filtro: corrección antes que velocidad. La autorización siempre la decide la
igualdad exacta contra las claves decodificadas, nunca el LIKE. `autoescape=True`
mantiene literal el `_` de los nombres generados.

**Cambio de comportamiento declarado (Bug Fix).** Una clave que no resuelve
devuelve **404**, no 400: mismo cuerpo para "no existe", "existe pero el recurso
está bloqueado o sin publicar" y "existe en el bucket pero nadie la referencia".
Distinguirlas devolvería el endpoint al estado de oráculo del contenido del
bucket. Los enlaces autorizados se conservan: la ruta y el parámetro `key` no
cambian, y ninguna plantilla ni JS del proyecto construye esa URL (el frontend
usa la `file_url` del proveedor que guarda el admin), así que no hay enlace de UI
que romper. `..` como segmento se rechaza en la normalización — una clave es el
nombre de un objeto, no una ruta que recorrer.

**Validación ejecutada.**

- `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/test_resource_storage.py`
  → **13 passed**. Cubre lo que pide Validation: archivo de recurso publicado y
  desbloqueado accesible (por URL, por clave desnuda, con percent-encoding, y vía
  `external_url` del recurso); bloqueado, no publicado, clave sin asociación,
  prefijo suelto, traversal y prefijo ajeno devuelven 404; en todos los rechazos
  `download_calls == 0`, es decir **ninguna descarga al proveedor**; a nivel de
  ruta, 200 para el archivo autorizado y 404 para el bloqueado en la misma
  petición-par, con una sola llamada al proveedor; sin sesión, 401.
- Carril PostgreSQL → **31 passed** con
  `tests/integration/test_resource_file_authorization_pg.py` nuevo: la resolución
  se comprueba contra Postgres porque el escapado del LIKE es comportamiento del
  dialecto y las claves llevan `_`, que es comodín; incluye el caso de una clave
  que solo difiere donde la buena tiene `_` y que no debe colarse por el
  prefiltro.
- Suite completa SQLite → **308 passed, 31 skipped** (los skips son los carriles
  opt-in: PostgreSQL/Redis y navegador).

Comandos exactos del carril: los mismos registrados en TASK-007.

**Límites de la validación.** No se hizo ninguna llamada real a S3: el proveedor
es un doble en todos los casos, así que lo verificado es que no se le pide la
descarga, no el comportamiento del bucket. Tampoco se probó contra datos de
producción reales: las lecciones sembradas usan las dos formas de referencia
conocidas (clave desnuda y URL del proveedor); una lección cuya URL almacenada no
contuviera el segmento `resources/` no resolvería, y no hay forma de descartarlo
sin inventariar la base real. El coste de la consulta se acota por prefiltro pero
no se midió con volumen realista de lecciones.

**Smoke de navegador:** N/A justificado, no por omisión. La tarea no toca ningún
archivo de frontend y `grep` sobre `app/templates`, `app/static` y `app/views` no
encuentra ninguna construcción de `/resources/file`: ningún flujo de UI llega a
este endpoint, así que un smoke no observaría nada de este cambio.

**Lint/typecheck:** N/A — no hay lint ni typecheck configurados en el proyecto.

### Estimated Impact

Security: HIGH
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM


## TASK-009 — Crear baseline y converger schemas históricos sin pérdida

Status: COMPLETED
Priority: CRITICAL
Phase: PHASE-0
Category: Database / Bug Fix

### Objective

Crear baseline y converger schemas históricos sin pérdida. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-08: La raíz añade columnas a users sin crearlo. Un upgrade elimina job_analysis; otro elimina y recrea applications. No se afirma que producción haya perdido datos, pero ejecutar esta cadena sobre una base heredada o vacía es inseguro/no reproducible. F-20: Dos ramas crean resource_lesson_progress con shapes diferentes; una incluye resource_id NOT NULL y otra no. CREATE condicional no reconcilia columnas. resource_enrollments existe en migración sin model/caller actual. Alembic no importa explícitamente roadmapModel; autogenerate puede omitirlo. Hay índices en migraciones ausentes en metadata.

### Evidence / Location

- `alembic/versions/025e4d7c446f_add_first_name_last_name_nickname_to_.py:21; alembic/versions/4897b7743b34_add_companies_table.py:24; alembic/versions/73a6e7c411b9_add_job_postings_and_update_.py:45` (Confidence: HIGH). 
- `alembic/env.py:9; alembic/versions/6e4bc7a18f21_add_resource_enrollment_and_progress_tables.py:49; alembic/versions/8c1d4a2b9f77_add_resource_lesson_progress_table.py; app/models/resourceModel.py:83` (Confidence: HIGH). 
- Alcance de edición conocido: alembic/env.py metadata; revisiones nuevas y estrategia baseline; tests de migración; manifest de modelos; modelo resource_lesson_progress solo compatibilidad de schema.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato.

### Proposed Solution

Diseñar baseline verificable para instalaciones nuevas y ruta forward-only para estados existentes, inventariando alembic_version y schema primero. No editar/reaplicar revisiones desplegadas ni ejecutar upgrade/downgrade real durante la auditoría. Proteger restores y pruebas de preservación antes de migrar. Con baseline de F-08, comparar schema real con metadata completa, crear migración de convergencia sin pérdida y manifest de import de modelos. resource_id puede derivarse de lesson→module; rellenar/verificar antes de retirarlo en fase posterior. Mantener enrollments hasta conocer consumidores/datos. Comparar revisiones y columnas en copias, incluir roadmaps y resume_course_evaluations explícitamente en metadata. No usar create_all para ocultar fallos de Alembic ni hacer stamp sobre DB sin comparación estructural. Conservar resource_enrollments.

### Scope

IN SCOPE:

- alembic/env.py metadata; revisiones nuevas y estrategia baseline; tests de migración; manifest de modelos; modelo resource_lesson_progress solo compatibilidad de schema.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- alembic/env.py metadata; revisiones nuevas y estrategia baseline; tests de migración; manifest de modelos; modelo resource_lesson_progress solo compatibilidad de schema.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-002

### Blocks

Blocks: TASK-005, TASK-012, TASK-013, TASK-014, TASK-015, TASK-016, TASK-017, TASK-019, TASK-021, TASK-024, TASK-027, TASK-031

### Parallelization

Can run in parallel with: TASK-003, TASK-004, TASK-007, TASK-020, TASK-030

Grupo B; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Crear baseline y converger schemas históricos sin pérdida.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Restaurar copia desechable, verificar conteos/checksums y FKs antes/después; probar bootstrap vacío y upgrades desde estados soportados; dry-run de rollback/restore documentado sin DROP accidental. Comparación PostgreSQL introspectada; ambas shapes convergen; insertar progreso con código actual funciona; autogenerate tras upgrade no propone DROP de tablas activas ni elimina índices funcionales.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Restauración probada de copia y cambios forward-only. No modificar checksums de revisiones ya desplegadas. Baseline nueva solo para instalaciones vacías; estados existentes tienen ruta separada. No downgrade destructivo ni DROP de enrollments.

### Completion Notes

**Inventario (evidencia, no suposición).** `alembic upgrade head` contra una
base PostgreSQL desechable vacía falla en el primer paso:
`relation "users" does not exist` en `ALTER TABLE users ADD COLUMN first_name`.
Siguiendo la cadena hay tres roturas independientes, todas en revisiones **ya
desplegadas**: `025e4d7c446f` añade columnas a `users` sin crearla;
`4897b7743b34` hace `DROP TABLE job_analysis` y ninguna revisión posterior la
recrea, pero `1720e86014a0` y `e1f7c2b9a4d3` siguen alterándola; `73a6e7c411b9`
hace `DROP TABLE applications` antes de que nada la cree. La cadena histórica
por tanto **no es reproducible desde cero**, y arreglarla exigiría editar
revisiones por las que producción ya pasó, que Rollback/Risk prohíbe.

**Decisión: dos rutas, un solo head y un solo comando.** `alembic/env.py`
distingue el caso. Base con tablas → cadena forward-only sin cambios. Base sin
ninguna tabla → `app/db_baseline.py`: DDL explícito versionado (generado desde
`Base.metadata`, no `create_all` en despliegue) → reintrospección y
`compare_metadata` contra los modelos → `stamp head` **solo** si el diff es
vacío; si no, `BaselineVerificationError` y la base queda sin marcar. Esto
cumple literalmente "no create_all para ocultar fallos" y "no stamp sin
comparación estructural". Documentado en `docs/DATABASE_CONFIG.md`, incluido el
procedimiento de regeneración y que estas bases son forward-only.

**Manifest de modelos.** `alembic/env.py` y `tests/conftest.py` mantenían dos
listas de imports; `roadmapModel` y `resumeCourseEvaluationModel` faltaban en la
de Alembic, así que sus tablas eran invisibles para autogenerate. Ambos importan
ahora `app/models/registry.py`. `tests/test_model_manifest.py` recorre
`app/models/` y falla si un modelo mapeado no está en el manifest.

**Índices ausentes de metadata.** Comparando `create_index`/`drop_index` de las
migraciones contra `Base.metadata`: 16 índices vivos más el HNSW
`ix_resume_embeddings_embedding_hnsw` (declarado con nombre variable) existían
solo en migraciones. Ya declarados en los modelos. Nota de auditoría: la
revisión `1720e86014a0` fue autogenerada con metadata incompleta y **borró** 16
índices funcionales por esa misma causa; restaurarlos es un cambio de
rendimiento fuera de este Objective y no se ha hecho aquí.

**Convergencia F-20.** Revisión nueva `a7f4c2b8d590` (head). Añade `resource_id`
si falta con backfill `lesson -> module -> resource` reanudable (solo filas
`NULL`), añade `created_at`/`updated_at` si faltan (NOT NULL + server default), y
relaja a nullable `resource_id`, `completed_at` y `last_opened_at`. El primer
test escrito detectó que sin relajar `resource_id` una base de la rama
`6e4bc7a18f21` rechaza toda inserción del writer actual, que no lo informa; se
corrigió la revisión. `downgrade()` es no-op deliberado y documentado: no
descarta backfill ni reimpone NOT NULL sobre filas que esta revisión hizo
representables. `resource_enrollments` se conserva y se mapea
(`ResourceEnrollmentModel`) para que autogenerate no proponga borrarla; no tiene
consumidores y su retirada es una tarea destructiva aparte.

**Modelo `ResourceLessonProgressModel`** pasa a la unión permisiva de ambos
shapes (solo compatibilidad de schema, como fija el Scope). El writer sigue
poblando `completed_at`/`last_opened_at` por default de aplicación, así que lo
que ven los readers no cambia.

**Validación ejecutada.**

Servicios desechables locales:

```bash
docker run -d --name sc-test-pg -e POSTGRES_PASSWORD=testpw -e POSTGRES_USER=testuser \
  -e POSTGRES_DB=studentscompass_test -p 55432:5432 pgvector/pgvector:pg16
docker run -d --name sc-test-redis -p 56379:6379 redis:7-alpine
```

- Bootstrap vacío: `ALEMBIC_DATABASE_URL=... .venv/bin/python -m alembic upgrade head`
  sobre `DROP SCHEMA public CASCADE; CREATE SCHEMA public` → `baseline applied and
  stamped at head`; `alembic current` → `a7f4c2b8d590 (head)`; segunda ejecución
  no-op.
- Comparación estructural post-bootstrap: `compare_metadata` → **0 diferencias**.
  Ninguna propuesta de `remove_table`/`remove_index`/`remove_column`.
- `TEST_DATABASE_URL_PG=postgresql+asyncpg://testuser:testpw@127.0.0.1:55432/studentscompass_test`
  `TEST_REDIS_URL=redis://127.0.0.1:56379/0`
  `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/integration`
  → **21 passed**.
- `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/test_model_manifest.py`
  → **8 passed**.
- Suite completa SQLite: `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests --ignore=tests/integration`
  → **243 passed, 1 skipped** (el skip es previo a esta tarea).
- Ambas shapes históricas convergen a las mismas columnas, la fila sobrevive,
  `resource_id` queda backfilleado, reejecutar la migración es idempotente y el
  writer actual inserta después de converger — todo cubierto en
  `tests/integration/test_migrations.py`.
- Un baseline desactualizado se prueba explícitamente: con metadata que declara
  una tabla que el DDL no crea, `bootstrap` lanza `BaselineVerificationError` y
  **no** deja `alembic_version`.

**Límites de la validación.** No se ejecutó ninguna migración ni restore contra
producción ni contra la copia real; toda la evidencia es de PostgreSQL 16 +
pgvector desechable local. La verificación de "restaurar copia desechable y
comparar conteos/checksums" solo se pudo hacer sobre datos sembrados por los
tests, no sobre un dump de producción: eso requiere acceso al backup real y
queda pendiente de ejecutar en el ensayo de rollout (TASK-031). El dry-run de
downgrade no se ejecutó porque `a7f4c2b8d590.downgrade()` es un no-op
deliberado y las bases con baseline son forward-only por diseño.

**Lint/typecheck:** N/A — el proyecto no tiene lint ni typecheck configurados
(`pyproject.toml` no declara ruff/flake8/mypy y no hay configuración propia).

### Estimated Impact

Security: HIGH
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: HIGH


## TASK-010 — Cubrir autenticación de compañías y validar proxy confiable

Status: TODO
Priority: CRITICAL
Phase: PHASE-1
Category: Security / Bug Fix

### Objective

Cubrir autenticación de compañías y validar proxy confiable. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-09: El limitador cubre login/registro de estudiantes pero no /api/v1/auth/company/login ni registro de compañía. Docker confía en cualquier proxy mediante FORWARDED_ALLOW_IPS=*. El bypass de IP depende de que el contenedor sea alcanzable directamente, algo no verificado.

### Evidence / Location

- `app/middleware/rate_limit.py:111 from_env; app/routes/companyRoute.py:199,205; Dockerfile:8` (Confidence: HIGH). 
- Alcance de edición conocido: app/middleware/rate_limit.py; Dockerfile flags proxy; tests de login/registro compañía y recuperación; documentación de ingreso.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato.

### Proposed Solution

Añadir reglas explícitas para autenticación de compañías y flujos de recuperación; declarar proxies permitidos según despliegue y probar IP resuelta. Conservar cookies HttpOnly/SameSite actuales; centralizar solo configuración realmente compartida. Revisar SameSite/Origin en mutaciones de formulario con pruebas cross-site; aplicar defensa adicional solo si evidencia/contrato lo requiere. No cambiar JWT ni roles como refactor lateral.

### Scope

IN SCOPE:

- app/middleware/rate_limit.py; Dockerfile flags proxy; tests de login/registro compañía y recuperación; documentación de ingreso.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/middleware/rate_limit.py; Dockerfile flags proxy; tests de login/registro compañía y recuperación; documentación de ingreso.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-007

### Blocks

Blocks: TASK-029, TASK-031

### Parallelization

Can run in parallel with: TASK-005, TASK-014, TASK-017, TASK-019, TASK-024

Grupo C; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Cubrir autenticación de compañías y validar proxy confiable.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Límites efectivos para ambas identidades; pruebas de X-Forwarded-For desde peer no confiable; revisar ingreso real antes de cerrar configuración; login legítimo conserva contrato.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: HIGH
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM


## TASK-011 — Normalizar errores públicos y recuperación transaccional

Status: TODO
Priority: CRITICAL
Phase: PHASE-1
Category: Security / Bug Fix

### Objective

Normalizar errores públicos y recuperación transaccional. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-10: Varias rutas retornan str(e), incluyendo excepciones de storage/DB. Pueden revelar nombres internos, queries o parámetros; no se observó un error real que expusiera una credencial.

### Evidence / Location

- `app/routes/resumeRoute.py:93; app/routes/questionnaireRoute.py:41; app/routes/resourceRoute.py:46; app/routes/adminRoute.py:369` (Confidence: HIGH). 
- Alcance de edición conocido: app/routes/resumeRoute.py, questionnaireRoute.py, resourceRoute.py, adminRoute.py: manejo de errores; helper error mapping; tests de errores redactados.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato.

### Proposed Solution

Mapear errores esperados a códigos estables y mensaje público seguro; registrar causa con identificador de correlación y redacción. Añadir rollback donde un fallo deja la sesión transaccional inválida.

### Scope

IN SCOPE:

- app/routes/resumeRoute.py, questionnaireRoute.py, resourceRoute.py, adminRoute.py: manejo de errores; helper error mapping; tests de errores redactados.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/routes/resumeRoute.py, questionnaireRoute.py, resourceRoute.py, adminRoute.py: manejo de errores; helper error mapping; tests de errores redactados.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-006, TASK-008

### Blocks

Blocks: TASK-016, TASK-028, TASK-031

### Parallelization

Can run in parallel with: TASK-023

Grupo F; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Normalizar errores públicos y recuperación transaccional.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Excepción simulada con marcador sensible no aparece en body/log público; 4xx conservados; 500 genérico con correlación; no continuar usando sesión fallida.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: HIGH
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM


## TASK-012 — Conciliar ledger IA y completar ciclo de reservas

Status: TODO
Priority: HIGH
Phase: PHASE-2
Category: Business Logic / Database / Bug Fix

### Objective

Conciliar ledger IA y completar ciclo de reservas. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-13: get_used_today usa max(ledger_count, legacy_count), no conciliación por identidad. La reserva vive en Redis/memoria y commit_usage solo agrega/flush; no existe clave única por referencia. Upload, alta de evaluación y extracción suceden fuera del try que libera reserva. Puede haber cuota retenida, estados parciales y contabilidad ambigua.

### Evidence / Location

- `app/services/ai/aiUsageService.py:124,167,208,240; app/services/resumes/resumeCourseAuditService.py:120; app/models/aiUsageModel.py:12` (Confidence: HIGH). 
- Alcance de edición conocido: app/services/ai/aiUsageService.py; app/services/resumes/resumeCourseAuditService.py; app/models/aiUsageModel.py; migración/backfill nuevos; tests de reservas y fallos.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato.

### Proposed Solution

Definir ledger autoritativo con referencia idempotente, ciclo de reserva durable y conciliación explícita legacy. Diferenciar gasto del proveedor y derecho de usuario; liberar solo cuando la política lo permite. Transacción coherente para resultado y consumo; cubrir todos los fallos previos y posteriores. Expandir referencia/estado primero, backfill solo jobs/evaluaciones atribuibles, comparar por usuario/feature/día, cambiar escritura y lectura al ledger y retirar max legacy solo tras parity. No borrar datos históricos ni asociar resultados al último CV por suposición.

### Scope

IN SCOPE:

- app/services/ai/aiUsageService.py; app/services/resumes/resumeCourseAuditService.py; app/models/aiUsageModel.py; migración/backfill nuevos; tests de reservas y fallos.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/services/ai/aiUsageService.py; app/services/resumes/resumeCourseAuditService.py; app/models/aiUsageModel.py; migración/backfill nuevos; tests de reservas y fallos.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-007, TASK-009

### Blocks

Blocks: TASK-013, TASK-016, TASK-031

### Parallelization

Can run in parallel with: TASK-006, TASK-015, TASK-021

Grupo D; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Conciliar ledger IA y completar ciclo de reservas.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Fallo en upload/extracción/flush/commit/cancelación deja estado recuperable; replay no duplica ledger; backfill por referencia con conteos por usuario/feature/día; no cambiar cuota histórica sin evidencia.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: MEDIUM
Maintainability: HIGH
Cost: HIGH
Risk: HIGH


## TASK-013 — Hacer durable e idempotente el procesamiento CV

Status: TODO
Priority: HIGH
Phase: PHASE-2
Category: Business Logic / Database / Bug Fix

### Objective

Hacer durable e idempotente el procesamiento CV. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-14: get_running_analysis seguido de create_pending_analysis no es atómico; BackgroundTasks no sobrevive al proceso. Un job PROCESSING sin recuperación bloquea nuevos análisis y el frontend deja de consultar tras 20 intentos de 3 s. El fallo de sesión puede impedir marcar FAILED sin rollback.

### Evidence / Location

- `app/routes/jobRoute.py:275,302; app/services/ai/cvAnalysisService.py:103,115,179,339; app/models/jobAnalysisModel.py:18; app/static/js/jobs.js:800` (Confidence: HIGH). 
- Alcance de edición conocido: app/routes/jobRoute.py flujo analyze/status; app/services/ai/cvAnalysisService.py; app/models/jobAnalysisModel.py; runner de jobs nuevo; migración nueva; tests/test_resume_analysis.py.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato.

### Proposed Solution

Usar job_analysis como cola durable pequeña con claim atómico, lease y recuperación; evitar Redis como segunda cola si DB basta. Índice parcial para job activo por usuario/CV, reintentos acotados y consulta de estado tras recarga. Separar reejecución idempotente de repetir gasto externo. Añadir lease/claim y estados compatibles de forma aditiva; clasificar trabajos históricos pendientes y expirados, no reiniciar gasto incierto automáticamente. El runner tendrá sesión propia y cierre limpio; la API existente conserva polling sin introducir WebSockets.

### Scope

IN SCOPE:

- app/routes/jobRoute.py flujo analyze/status; app/services/ai/cvAnalysisService.py; app/models/jobAnalysisModel.py; runner de jobs nuevo; migración nueva; tests/test_resume_analysis.py.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/routes/jobRoute.py flujo analyze/status; app/services/ai/cvAnalysisService.py; app/models/jobAnalysisModel.py; runner de jobs nuevo; migración nueva; tests/test_resume_analysis.py.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-009, TASK-012

### Blocks

Blocks: TASK-023, TASK-026, TASK-028, TASK-031

### Parallelization

Can run in parallel with: TASK-008, TASK-022, TASK-027

Grupo E; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Hacer durable e idempotente el procesamiento CV.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Dos POST simultáneos devuelven el mismo trabajo efectivo; reinicio tras claim recupera o falla explícitamente; probar antes/después de gasto; no duplicar llamadas confirmadas; mantener respuesta job_id/status.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: MEDIUM
Maintainability: HIGH
Cost: HIGH
Risk: HIGH


## TASK-014 — Centralizar transiciones y proyección de candidaturas

Status: TODO
Priority: HIGH
Phase: PHASE-2
Category: Business Logic / Database / Bug Fix

### Objective

Centralizar transiciones y proyección de candidaturas. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-11: ApplicationService registra eventos y agregados, pero InterviewService escribe INTERVIEW directamente. El agregado usa leer-modificar-escribir sin bloqueo/upsert y puede perder incrementos o chocar al crearse. Model y schema duplican enums.

### Evidence / Location

- `app/services/applications/applicationService.py:168,390; app/services/jobs/interviewService.py:67; app/models/applicationAnalyticsModel.py:46; app/schemas/applicationSchema.py:11` (Confidence: HIGH). 
- Alcance de edición conocido: app/services/applications/applicationService.py; app/services/jobs/interviewService.py publicación; app/models/applicationModel.py/applicationAnalyticsModel.py; app/schemas/applicationSchema.py; tests de candidaturas.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato.

### Proposed Solution

Crear una operación de transición de estado reutilizable con actor, evento y delta en la misma transacción; usar incremento SQL atómico/upsert y bloqueo/versionado del estado. Mantener applications.status como estado actual y eventos como historial autoritativo desde un punto de corte documentado. Conservar permisos actuales de estudiante/recruiter; si se cuestiona que el usuario pueda cambiar status, proponer una tarea de producto aparte. Reconstruir agregados desde eventos existentes; documentar punto de corte y diferencias legacy. Compartir ranking de rol ya duplicado sin cambiar criterio.

### Scope

IN SCOPE:

- app/services/applications/applicationService.py; app/services/jobs/interviewService.py publicación; app/models/applicationModel.py/applicationAnalyticsModel.py; app/schemas/applicationSchema.py; tests de candidaturas.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/services/applications/applicationService.py; app/services/jobs/interviewService.py publicación; app/models/applicationModel.py/applicationAnalyticsModel.py; app/schemas/applicationSchema.py; tests de candidaturas.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-009

### Blocks

Blocks: TASK-015, TASK-016, TASK-031

### Parallelization

Can run in parallel with: TASK-005, TASK-010, TASK-017, TASK-019, TASK-024

Grupo C; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Centralizar transiciones y proyección de candidaturas.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Publicar entrevista genera exactamente un evento coherente; 20 transiciones concurrentes conservan conteos; replay de comando no duplica eventos; snapshots de enums/payloads compatibles.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: HIGH


## TASK-015 — Serializar selección de entrevista por candidatura

Status: TODO
Priority: HIGH
Phase: PHASE-2
Category: Business Logic / Database / Bug Fix

### Objective

Serializar selección de entrevista por candidatura. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-12: Se lee AVAILABLE, se marca BOOKED y se cancelan alternativas sin serializar por candidatura. Dos selecciones concurrentes pueden producir conflicto, más de una confirmación o logs duplicados; la DB no impone una única reserva por candidatura.

### Evidence / Location

- `app/services/jobs/interviewService.py:113 select_user_availability; app/models/interviewAvailabilityModel.py:18` (Confidence: HIGH). 
- Alcance de edición conocido: app/services/jobs/interviewService.py; app/models/interviewAvailabilityModel.py; índice parcial nuevo; tests de entrevista concurrente y logs mock.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato.

### Proposed Solution

Bloquear candidatura antes de publicar/seleccionar, imponer unicidad parcial de BOOKED por application_id tras revisar duplicados y hacer idempotente elegir de nuevo el mismo slot. No introducir agenda global: los slots actuales pertenecen a candidaturas. Primero inventariar BOOKED duplicados; preservar registros en conflicto y resolver explícitamente antes de validar índice. Migración no elimina disponibilidades. Reutilizar transición canónica de TASK-014.

### Scope

IN SCOPE:

- app/services/jobs/interviewService.py; app/models/interviewAvailabilityModel.py; índice parcial nuevo; tests de entrevista concurrente y logs mock.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/services/jobs/interviewService.py; app/models/interviewAvailabilityModel.py; índice parcial nuevo; tests de entrevista concurrente y logs mock.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-009, TASK-014

### Blocks

Blocks: TASK-027, TASK-028, TASK-031

### Parallelization

Can run in parallel with: TASK-006, TASK-012, TASK-021

Grupo D; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Serializar selección de entrevista por candidatura.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Dos sesiones seleccionando slots distintos dejan exactamente uno BOOKED y una transición efectiva; reintento mismo slot devuelve estado existente; migración detecta conflictos sin descartarlos.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: HIGH


## TASK-016 — Unificar aprobación de CV y proyección de progreso

Status: TODO
Priority: HIGH
Phase: PHASE-3
Category: Business Logic / Database / Bug Fix

### Objective

Unificar aprobación de CV y proyección de progreso. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-15: ResourceService completa virtualmente lecciones de CV por evaluación aprobada; dashboard cuenta solo filas de progress y sincroniza user_stats durante lecturas. El fallback usa porcentajes fijos. Aprobación de score >=8 se repite y recursos solo consulta pass_status. user_stage_progress también es derivado de tareas.

### Evidence / Location

- `app/services/resources/resourceService.py:149,174; app/services/applications/dashboardService.py:277,307,387,512; app/core/resume_analyzer/resume_audit_llm.py:121; app/services/applications/applicationService.py:43; app/services/roadmaps/roadmapService.py:246` (Confidence: HIGH). 
- Alcance de edición conocido: app/services/resources/resourceService.py; app/services/applications/dashboardService.py; applicationService.py elegibilidad; resume_audit_llm.py policy; schema/report de auditoría; app/models/resourceModel.py código core; policy/proyector nuevos; tests de progreso.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato.

### Proposed Solution

Centralizar elegibilidad de CV y proyección de progreso; distinguir resource_lesson_progress y evaluaciones como hechos, user_stats/user_stage_progress como proyecciones. Identificar cursos core por código estable, no título editable. Preservar DTO y separar corrección de porcentajes de extracción estructural. Introducir código core nullable, identificar correspondencias únicas por inventario y luego validar unicidad sin obligar código a todos los recursos. Migrar consumers del título al código. Mantener user_stats como legacy documentado sin writes en GET; no eliminar columnas/tablas en esta tarea. Roadmap stage cache se documenta y verifica, no se fusiona con recursos.

### Scope

IN SCOPE:

- app/services/resources/resourceService.py; app/services/applications/dashboardService.py; applicationService.py elegibilidad; resume_audit_llm.py policy; schema/report de auditoría; app/models/resourceModel.py código core; policy/proyector nuevos; tests de progreso.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/services/resources/resourceService.py; app/services/applications/dashboardService.py; applicationService.py elegibilidad; resume_audit_llm.py policy; schema/report de auditoría; app/models/resourceModel.py código core; policy/proyector nuevos; tests de progreso.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-009, TASK-011, TASK-012, TASK-014

### Blocks

Blocks: TASK-018, TASK-025, TASK-026, TASK-031

### Parallelization

Can run in parallel with: TASK-028

Grupo G; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Unificar aprobación de CV y proyección de progreso.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Mismo usuario obtiene mismos porcentajes en dashboard/recurso; evaluación aprobada sin fila de progreso coherente; score 7.99/8, múltiples evaluaciones y CV borrado; lecturas no escriben stats; parity report legacy antes del switch.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: HIGH


## TASK-017 — Derivar contador de comunidad desde membresías

Status: TODO
Priority: HIGH
Phase: PHASE-2
Category: Business Logic / Bug Fix

### Objective

Derivar contador de comunidad desde membresías. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-16: La membresía tiene unique(community_id,user_id) pero member_count usa incrementos/decrementos Python; las altas/bajas simultáneas pueden perder cambios. Cascadas de usuarios también alteran miembros sin actualizar el contador.

### Evidence / Location

- `app/models/communityModel.py:22; app/services/community/communityService.py:96,124,152` (Confidence: HIGH). 
- Alcance de edición conocido: app/services/community/communityService.py; lectura de count en adminRoute.py; consultas de comunidad; tests/test_communities.py; migración solo si se conserva cache atómico.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato.

### Proposed Solution

community_members será autoritativa. Preferir COUNT agrupado con índice existente si benchmark lo permite; de conservar caché, actualización atómica y reconstrucción/reconciliación explícita. No fusionar tabla de membresías con comunidades. Añadir comparación count histórico vs membresías antes de cambiar respuesta. No borrar member_count aún; marcarlo cache/legacy explícitamente y excluirlo de decisiones.

### Scope

IN SCOPE:

- app/services/community/communityService.py; lectura de count en adminRoute.py; consultas de comunidad; tests/test_communities.py; migración solo si se conserva cache atómico.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/services/community/communityService.py; lectura de count en adminRoute.py; consultas de comunidad; tests/test_communities.py; migración solo si se conserva cache atómico.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-009

### Blocks

Blocks: TASK-031

### Parallelization

Can run in parallel with: TASK-005, TASK-010, TASK-014, TASK-019, TASK-024

Grupo C; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Derivar contador de comunidad desde membresías.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Altas/bajas simultáneas y eliminación de usuario mantienen count igual a COUNT(*); repetición de join/leave tiene resultado estable; medir consultas/latencia con catálogo representativo.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM


## TASK-018 — Agrupar consultas de progreso de recursos

Status: TODO
Priority: HIGH
Phase: PHASE-4
Category: Performance

### Objective

Agrupar consultas de progreso de recursos. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-17: list_user_enrollment_progress consulta completados y lecciones por cada recurso, con otra query si hay lección de CV. Extracción batch comparte lookup, pero consulta links y hace commit por oferta. No atribuir N+1 a messageService: allí ya hay batching.

### Evidence / Location

- `app/services/resources/resourceService.py:267; app/services/resources/resourceService.py:149; app/services/analytics/capstoneAnalyticsService.py:185,238` (Confidence: HIGH). 
- Alcance de edición conocido: app/services/resources/resourceService.py list_user_enrollment_progress/progreso batch; consultas de proyector creadas en TASK-016; tests de query count.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita.

### Proposed Solution

Tras la policy canónica, reemplazar llamadas por recurso por queries agrupadas: catálogo/outline, progreso de user+lesson_ids y aprobación CV una sola vez. Mantener DTO, orden y semántica de completado. Excluir extracción de ofertas, cubierta por TASK-019.

### Scope

IN SCOPE:

- app/services/resources/resourceService.py list_user_enrollment_progress/progreso batch; consultas de proyector creadas en TASK-016; tests de query count.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/services/resources/resourceService.py list_user_enrollment_progress/progreso batch; consultas de proyector creadas en TASK-016; tests de query count.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-016

### Blocks

Blocks: TASK-026, TASK-031

### Parallelization

Can run in parallel with: TASK-025

Grupo H; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Agrupar consultas de progreso de recursos.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Con 1/10/100 recursos, número de SELECT constante por lote y no lineal en recursos; resultados idénticos al proyector TASK-016; medir p50/p95 y bytes de payload. No compartir AsyncSession dentro de gather.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: HIGH
Maintainability: HIGH
Cost: MEDIUM
Risk: MEDIUM


## TASK-019 — Hacer batch e idempotente la extracción de skills de ofertas

Status: TODO
Priority: HIGH
Phase: PHASE-4
Category: Performance / Database

### Objective

Hacer batch e idempotente la extracción de skills de ofertas. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-17: list_user_enrollment_progress consulta completados y lecciones por cada recurso, con otra query si hay lección de CV. Extracción batch comparte lookup, pero consulta links y hace commit por oferta. No atribuir N+1 a messageService: allí ya hay batching. F-23: job_skills no tiene unicidad por oferta/skill/método; check-then-insert permite duplicados concurrentes. Estados de resume_skills son strings sin CHECK; rangos de score/cost/duration y orden de módulos/lecciones no están protegidos por constraints equivalentes. Float es aproximado para costes de optimización, no un libro de pagos.

### Evidence / Location

- `app/services/resources/resourceService.py:267; app/services/resources/resourceService.py:149; app/services/analytics/capstoneAnalyticsService.py:185,238` (Confidence: HIGH). 
- `app/models/skillModel.py:64,85,114; app/models/interviewAvailabilityModel.py:18; app/models/resourceModel.py:42; app/services/analytics/capstoneAnalyticsService.py:207` (Confidence: HIGH). 
- Alcance de edición conocido: app/services/analytics/capstoneAnalyticsService.py extract_job_skills_from_job_posting/extract_job_skills_for_open_postings; app/models/skillModel.py JobSkillModel; migración única propia; tests de extracción batch.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita.

### Proposed Solution

Reutilizar lookup existente; precargar links por posting_id/método, pasar objetos ya cargados y flush/commit por lote acotado. Añadir unicidad parcial para oferta+skill+método, tras inventario/dedup con provenance preservada. No fusionar requisitos fallback por rol ni modificar el algoritmo de extracción.

### Scope

IN SCOPE:

- app/services/analytics/capstoneAnalyticsService.py extract_job_skills_from_job_posting/extract_job_skills_for_open_postings; app/models/skillModel.py JobSkillModel; migración única propia; tests de extracción batch.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/services/analytics/capstoneAnalyticsService.py extract_job_skills_from_job_posting/extract_job_skills_for_open_postings; app/models/skillModel.py JobSkillModel; migración única propia; tests de extracción batch.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-009

### Blocks

Blocks: TASK-021, TASK-022, TASK-023, TASK-027, TASK-031

### Parallelization

Can run in parallel with: TASK-005, TASK-010, TASK-014, TASK-017, TASK-024

Grupo C; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Hacer batch e idempotente la extracción de skills de ofertas.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Para 10/100/500 ofertas, commits por batch; queries no una por oferta; segunda ejecución no duplica; dos ejecuciones concurrentes mantienen links únicos; misma evidencia y conteo; backfill no descarta métodos distintos.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: HIGH
Maintainability: HIGH
Cost: MEDIUM
Risk: HIGH


## TASK-020 — Sacar scraper de LinkedIn del event loop

Status: TODO
Priority: HIGH
Phase: PHASE-4
Category: Performance

### Objective

Sacar scraper de LinkedIn del event loop. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-18: search async llama requests.get y time.sleep directamente por el scraper. CP-SAT Solve también se ejecuta en el event loop (con límite real de 1 s y un worker, que conviene conservar). Una petición puede frenar otras del mismo worker.

### Evidence / Location

- `app/services/jobs/jobSearchService.py:69,84; app/core/JobsScraper/linkedin_scraper.py fetch_linkedin_jobs; app/services/analytics/learningRouteOptimizerService.py:409,571` (Confidence: HIGH). 
- Alcance de edición conocido: app/services/jobs/jobSearchService.py; app/core/JobsScraper/linkedin_scraper.py; tests/test_job_board.py y prueba de concurrencia de búsqueda.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita.

### Proposed Solution

Encapsular scraper síncrono en executor limitado o cliente async sin cambiar parsing/salida; aplicar límite normalizado también a proveedor, timeout total y cola acotada. La query SQL permanece en loop. Cache breve por parámetros normalizados solo después de medir llamadas repetidas y documentar TTL/invalidación.

### Scope

IN SCOPE:

- app/services/jobs/jobSearchService.py; app/core/JobsScraper/linkedin_scraper.py; tests/test_job_board.py y prueba de concurrencia de búsqueda.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/services/jobs/jobSearchService.py; app/core/JobsScraper/linkedin_scraper.py; tests/test_job_board.py y prueba de concurrencia de búsqueda.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001

### Blocks

Blocks: TASK-026, TASK-028, TASK-031

### Parallelization

Can run in parallel with: TASK-003, TASK-004, TASK-007, TASK-009, TASK-030

Grupo B; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Sacar scraper de LinkedIn del event loop.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Proveedor falso con latencia de 2 s no bloquea request liviano; lista/orden/status compatibles; cancelación/timeout no deja cola ilimitada; medir event loop lag, llamadas por búsqueda y p95; no scrapear sitio real en tests.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: HIGH
Maintainability: HIGH
Cost: MEDIUM
Risk: MEDIUM


## TASK-021 — Evitar regeneración de embeddings idénticos

Status: TODO
Priority: MEDIUM
Phase: PHASE-4
Category: Performance / Database

### Objective

Evitar regeneración de embeddings idénticos. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-21: analyze_gap sincroniza embedding de resumen; upsert genera antes de consultar y hace commit incluso si texto/modelo no cambiaron. El default es hash local; no se demostró gasto en API de embeddings. Con modelo local el coste CPU/RAM es mayor.

### Evidence / Location

- `app/services/analytics/capstoneAnalyticsService.py:476,694; app/services/analytics/embeddingService.py:128,156` (Confidence: HIGH). 
- Alcance de edición conocido: app/services/analytics/embeddingService.py; capstoneAnalyticsService.py _sync_resume_embedding_if_possible; app/models/resumeEmbeddingsModel.py; migración fingerprint nueva; tests/test_embedding_service.py.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita.

### Proposed Solution

Persistir fingerprint de texto normalizado+modelo+versión; saltar generación y write si coincide. Guardar explícitamente modelo efectivo; conservar separación hash-v1/modelo semántico y no prometer equivalencia de calidad. Verificar Vector(384) contra dimensiones del proveedor antes de persistir. Backfill fingerprint solo con entrada demostrable; vectores sin provenance se invalidan para regeneración controlada, no se etiquetan con hash inventado. Upsert atómico ante primera generación concurrente.

### Scope

IN SCOPE:

- app/services/analytics/embeddingService.py; capstoneAnalyticsService.py _sync_resume_embedding_if_possible; app/models/resumeEmbeddingsModel.py; migración fingerprint nueva; tests/test_embedding_service.py.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/services/analytics/embeddingService.py; capstoneAnalyticsService.py _sync_resume_embedding_if_possible; app/models/resumeEmbeddingsModel.py; migración fingerprint nueva; tests/test_embedding_service.py.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-009, TASK-019

### Blocks

Blocks: TASK-022, TASK-023, TASK-027, TASK-031

### Parallelization

Can run in parallel with: TASK-006, TASK-012, TASK-015

Grupo D; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Evitar regeneración de embeddings idénticos.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Segunda petición idéntica: cero regeneraciones/writes; cambio de texto/modelo invalida; fallback no mezcla espacios; medir CPU, RSS, writes y p95 con ambos proveedores. Dimensión incompatible falla controladamente; similarity PostgreSQL usa modelo/índice correcto.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: HIGH
Maintainability: HIGH
Cost: MEDIUM
Risk: HIGH


## TASK-022 — Ejecutar CP-SAT fuera del loop con concurrencia acotada

Status: TODO
Priority: MEDIUM
Phase: PHASE-4
Category: Performance

### Objective

Ejecutar CP-SAT fuera del loop con concurrencia acotada. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-18: search async llama requests.get y time.sleep directamente por el scraper. CP-SAT Solve también se ejecuta en el event loop (con límite real de 1 s y un worker, que conviene conservar). Una petición puede frenar otras del mismo worker.

### Evidence / Location

- `app/services/jobs/jobSearchService.py:69,84; app/core/JobsScraper/linkedin_scraper.py fetch_linkedin_jobs; app/services/analytics/learningRouteOptimizerService.py:409,571` (Confidence: HIGH). 
- Alcance de edición conocido: app/services/analytics/learningRouteOptimizerService.py ORTools optimizer; tests del solver y de loop lag.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita.

### Proposed Solution

Pasar candidatos y constraints como datos a executor acotado y ejecutar solo construcción/Solve fuera del event loop. No llevar AsyncSession al thread. Conservar max_time_in_seconds=1, num_search_workers=1, seed y criterio de selección. No crear servicio separado ni GPU.

### Scope

IN SCOPE:

- app/services/analytics/learningRouteOptimizerService.py ORTools optimizer; tests del solver y de loop lag.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/services/analytics/learningRouteOptimizerService.py ORTools optimizer; tests del solver y de loop lag.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-019, TASK-021

### Blocks

Blocks: TASK-023, TASK-028, TASK-031

### Parallelization

Can run in parallel with: TASK-008, TASK-013, TASK-027

Grupo E; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Ejecutar CP-SAT fuera del loop con concurrencia acotada.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Goldens de selección/constraints compatibles; simular solver lento sin bloquear request liviano; máximo de tareas activas y cola comprobado; timeout/cancelación resuelto; reportar lag/RSS/p95 frente al baseline.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: HIGH
Maintainability: HIGH
Cost: MEDIUM
Risk: MEDIUM


## TASK-023 — Dividir Capstone conservando facade y contratos

Status: TODO
Priority: HIGH
Phase: PHASE-5
Category: Architecture

### Objective

Dividir Capstone conservando facade y contratos. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-19: CapstoneAnalyticsService tiene 1393 líneas y mezcla extracción, revisión, catálogo, métricas, embeddings, recomendaciones, optimización y persistencia. career_lab.js 1304 y jobs.js 1284 combinan fetch, estado, reglas/presentación y eventos. Longitud es indicio acompañado por esas responsabilidades, no criterio aislado.

### Evidence / Location

- `app/services/analytics/capstoneAnalyticsService.py:1; app/static/js/career_lab.js:1; app/static/js/jobs.js:1; app/routes/companyRoute.py:48` (Confidence: HIGH). 
- Alcance de edición conocido: app/services/analytics/capstoneAnalyticsService.py; nuevos servicios de catálogo, revisión de skills y gap/optimización; tests de contratos Capstone; routes solo wiring indispensable.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita.

### Proposed Solution

Mantener facade y rutas; extraer use cases de skills, catálogo y análisis/optimización con contratos concretos. En JS separar acceso API, estado del flujo y rendering por pantalla, sin cambiar a React ni introducir repositorios universales. Esta tarea solo divide backend Capstone; no edita JS. Extraer primero catálogo, luego revisión y coordinador gap/optimización con facade delegadora. Mover queries realmente compartidas a funciones específicas. No modificar pesos, heurísticas, thresholds ni snapshots históricos.

### Scope

IN SCOPE:

- app/services/analytics/capstoneAnalyticsService.py; nuevos servicios de catálogo, revisión de skills y gap/optimización; tests de contratos Capstone; routes solo wiring indispensable.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/services/analytics/capstoneAnalyticsService.py; nuevos servicios de catálogo, revisión de skills y gap/optimización; tests de contratos Capstone; routes solo wiring indispensable.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-013, TASK-019, TASK-021, TASK-022, TASK-027

### Blocks

Blocks: TASK-026, TASK-028, TASK-031

### Parallelization

Can run in parallel with: TASK-011

Grupo F; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Dividir Capstone conservando facade y contratos.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Comparar payloads gap, revisión, calidad catálogo, optimización y runs antes/después; fixture determinista produce mismo resultado; suite capstone verde; imports sin dependencia router→servicio→router; facade no duplicará implementación activa.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM


## TASK-024 — Paginar mensajes con cursor estable y migrar inbox

Status: TODO
Priority: MEDIUM
Phase: PHASE-4
Category: Performance

### Objective

Paginar mensajes con cursor estable y migrar inbox. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-22: Mensajes/posts/CV/candidaturas sin paginación; dashboard materializa candidaturas y cuenta/ordena en Python. Recursos filtra catálogo en memoria. Impacto crece con historial; no hay volúmenes ni EXPLAIN de producción para afirmar scans lentos.

### Evidence / Location

- `app/services/community/messageService.py:171; app/services/community/postService.py:30; app/services/resumes/resumeService.py:105; app/services/applications/applicationService.py:127; app/services/applications/dashboardService.py:266; app/services/resources/resourceService.py:85` (Confidence: HIGH). 
- Alcance de edición conocido: app/services/community/messageService.py list_messages; app/routes/messageRoute.py; schemas de mensajes; consumidor de inbox identificado por búsqueda de endpoint; índice nuevo si EXPLAIN justifica; tests/test_messages.py.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita.

### Proposed Solution

Introducir contrato de cursor created_at+id y página acotada, migrar consumidor de inbox con carga incremental. Mantener endpoint/forma legacy durante transición hasta verificar todos los callers. Reutilizar batching de autores/últimos mensajes existente y controles de pertenencia.

### Scope

IN SCOPE:

- app/services/community/messageService.py list_messages; app/routes/messageRoute.py; schemas de mensajes; consumidor de inbox identificado por búsqueda de endpoint; índice nuevo si EXPLAIN justifica; tests/test_messages.py.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/services/community/messageService.py list_messages; app/routes/messageRoute.py; schemas de mensajes; consumidor de inbox identificado por búsqueda de endpoint; índice nuevo si EXPLAIN justifica; tests/test_messages.py.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-009

### Blocks

Blocks: TASK-026, TASK-031

### Parallelization

Can run in parallel with: TASK-005, TASK-010, TASK-014, TASK-017, TASK-019

Grupo C; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Paginar mensajes con cursor estable y migrar inbox.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Conversación con 10000 mensajes y timestamps repetidos se recorre sin omisiones/duplicados; payload máximo fijo; usuario ajeno denegado; orden de UI y no leídos conservados; EXPLAIN/RSS/bytes antes y después.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: HIGH
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM


## TASK-025 — Calcular dashboard en DB y definir transición de listados

Status: TODO
Priority: MEDIUM
Phase: PHASE-4
Category: Performance

### Objective

Calcular dashboard en DB y definir transición de listados. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-22: Mensajes/posts/CV/candidaturas sin paginación; dashboard materializa candidaturas y cuenta/ordena en Python. Recursos filtra catálogo en memoria. Impacto crece con historial; no hay volúmenes ni EXPLAIN de producción para afirmar scans lentos.

### Evidence / Location

- `app/services/community/messageService.py:171; app/services/community/postService.py:30; app/services/resumes/resumeService.py:105; app/services/applications/applicationService.py:127; app/services/applications/dashboardService.py:266; app/services/resources/resourceService.py:85` (Confidence: HIGH). 
- Alcance de edición conocido: app/services/applications/dashboardService.py consultas student stats/recent; tests/test_dashboard.py; inventario de callers para posts/resumes/applications/resource list en docs.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita.

### Proposed Solution

Reemplazar materialización de todas las candidaturas para métricas/top5 por agregados SQL y orden estable con LIMIT. Mantener el progreso de TASK-016. Medir los otros listados F-22 y crear tareas posteriores específicas de paginación si superan presupuesto; no truncar respuestas sin migrar callers.

### Scope

IN SCOPE:

- app/services/applications/dashboardService.py consultas student stats/recent; tests/test_dashboard.py; inventario de callers para posts/resumes/applications/resource list en docs.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/services/applications/dashboardService.py consultas student stats/recent; tests/test_dashboard.py; inventario de callers para posts/resumes/applications/resource list en docs.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-016

### Blocks

Blocks: TASK-026, TASK-031

### Parallelization

Can run in parallel with: TASK-018

Grupo H; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Calcular dashboard en DB y definir transición de listados.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Stats/top5 idénticos con 0/100/10000 candidaturas, empates de fecha y estados; memoria/payload de recientes acotados; query count fijo. Documentar medición y decisión por listado restante, con tareas nuevas si hay trabajo pendiente.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: HIGH
Maintainability: HIGH
Cost: MEDIUM
Risk: MEDIUM


## TASK-026 — Separar API, estado y render de Jobs y Career Lab

Status: TODO
Priority: HIGH
Phase: PHASE-5
Category: Architecture

### Objective

Separar API, estado y render de Jobs y Career Lab. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-19: CapstoneAnalyticsService tiene 1393 líneas y mezcla extracción, revisión, catálogo, métricas, embeddings, recomendaciones, optimización y persistencia. career_lab.js 1304 y jobs.js 1284 combinan fetch, estado, reglas/presentación y eventos. Longitud es indicio acompañado por esas responsabilidades, no criterio aislado.

### Evidence / Location

- `app/services/analytics/capstoneAnalyticsService.py:1; app/static/js/career_lab.js:1; app/static/js/jobs.js:1; app/routes/companyRoute.py:48` (Confidence: HIGH). 
- Alcance de edición conocido: app/static/js/jobs.js; career_lab.js; módulos JS nuevos; templates Jobs/Career Lab para carga; smoke de frontend.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita.

### Proposed Solution

Mantener vanilla JS/Jinja. Extraer cliente API de cada feature, estado UI y render; reusable helpers solo para comportamiento equivalente. Server state se invalida tras mutaciones; polling de jobs reanudable/abortable al navegar sin duplicar requests. Conservar DOM/estilos y la seguridad de TASK-004.

### Scope

IN SCOPE:

- app/static/js/jobs.js; career_lab.js; módulos JS nuevos; templates Jobs/Career Lab para carga; smoke de frontend.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/static/js/jobs.js; career_lab.js; módulos JS nuevos; templates Jobs/Career Lab para carga; smoke de frontend.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-004, TASK-013, TASK-016, TASK-018, TASK-020, TASK-023, TASK-024, TASK-025

### Blocks

Blocks: TASK-029, TASK-031

### Parallelization

Can run in parallel with: NONE

Grupo I; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Separar API, estado y render de Jobs y Career Lab.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Smoke login→upload→análisis→búsqueda→apply e independiente skills→gap→optimize/review; mismos mensajes y resultados; sin fetch duplicados tras navegación/reintento; verificar loading/error/cancelación y dos pestañas. Medir request count por flujo.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM


## TASK-027 — Validar rangos, estados y metadata de datos analíticos

Status: TODO
Priority: MEDIUM
Phase: PHASE-2
Category: Database

### Objective

Validar rangos, estados y metadata de datos analíticos. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-23: job_skills no tiene unicidad por oferta/skill/método; check-then-insert permite duplicados concurrentes. Estados de resume_skills son strings sin CHECK; rangos de score/cost/duration y orden de módulos/lecciones no están protegidos por constraints equivalentes. Float es aproximado para costes de optimización, no un libro de pagos. F-20: Dos ramas crean resource_lesson_progress con shapes diferentes; una incluye resource_id NOT NULL y otra no. CREATE condicional no reconcilia columnas. resource_enrollments existe en migración sin model/caller actual. Alembic no importa explícitamente roadmapModel; autogenerate puede omitirlo. Hay índices en migraciones ausentes en metadata.

### Evidence / Location

- `app/models/skillModel.py:64,85,114; app/models/interviewAvailabilityModel.py:18; app/models/resourceModel.py:42; app/services/analytics/capstoneAnalyticsService.py:207` (Confidence: HIGH). 
- `alembic/env.py:9; alembic/versions/6e4bc7a18f21_add_resource_enrollment_and_progress_tables.py:49; alembic/versions/8c1d4a2b9f77_add_resource_lesson_progress_table.py; app/models/resourceModel.py:83` (Confidence: HIGH). 
- Alcance de edición conocido: app/models/skillModel.py CHECK de resume_skills/courses/course_skills; revisiones nuevas; metadata de índices existentes; tests DB y queries de inventario.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita.

### Proposed Solution

Inventariar estados inválidos, negativos/NaN y rangos definidos por schemas/policies antes de añadir CHECK. No imponer unicidad de orden pedagógico ni cambiar Float a Numeric sin evidencia: registrar decisión con query/fixture. Corregir metadata que omite índices ya existentes sin recrearlos innecesariamente; no tocar reglas solver.

### Scope

IN SCOPE:

- app/models/skillModel.py CHECK de resume_skills/courses/course_skills; revisiones nuevas; metadata de índices existentes; tests DB y queries de inventario.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/models/skillModel.py CHECK de resume_skills/courses/course_skills; revisiones nuevas; metadata de índices existentes; tests DB y queries de inventario.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-009, TASK-015, TASK-019, TASK-021

### Blocks

Blocks: TASK-023, TASK-031

### Parallelization

Can run in parallel with: TASK-008, TASK-013, TASK-022

Grupo E; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Validar rangos, estados y metadata de datos analíticos.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Filas válidas permanecen idénticas; inválidas reportadas y resueltas sin borrado silencioso; upgrade y restore en copia; alembic compare_metadata sin drops espurios; pruebas de CHECK en PostgreSQL, no solo Pydantic.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: HIGH


## TASK-028 — Medir flujos críticos y hacer visibles fallos parciales

Status: TODO
Priority: MEDIUM
Phase: PHASE-4
Category: Maintainability

### Objective

Medir flujos críticos y hacer visibles fallos parciales. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-24: Logs sin correlación uniforme, duración/query count/calls externos; algunos catch retornan vacío. Tests crean metadata en SQLite, no ejecutan Alembic ni reproducen locks, índices parciales/pgvector y restricciones Postgres. No se encontraron workflows CI versionados.

### Evidence / Location

- `app/logging.py:1; tests/conftest.py:51,79; pytest.ini; pyproject.toml; app/services/applications/dashboardService.py:420` (Confidence: HIGH). 
- Alcance de edición conocido: app/logging.py; middleware de request id nuevo; hooks métricos en jobs/AI/search/solver; tests de redacción y fallo; documentación operativa.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita.

### Proposed Solution

Añadir request/job correlation, duración y contadores SQL/intentos con IDs seguros. Eliminar logs de nombres/keywords CV donde no aportan diagnóstico. Registrar fallos recuperables sin ocultarlos como éxito vacío. Definir p95/edad de jobs/reservas y budget denials; no introducir tracing empresarial ni logs por fila.

### Scope

IN SCOPE:

- app/logging.py; middleware de request id nuevo; hooks métricos en jobs/AI/search/solver; tests de redacción y fallo; documentación operativa.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/logging.py; middleware de request id nuevo; hooks métricos en jobs/AI/search/solver; tests de redacción y fallo; documentación operativa.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-011, TASK-013, TASK-015, TASK-020, TASK-022, TASK-023

### Blocks

Blocks: TASK-029, TASK-031

### Parallelization

Can run in parallel with: TASK-016

Grupo G; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Medir flujos críticos y hacer visibles fallos parciales.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Inyectar fallo proveedor/DB y seguirlo por correlation id; logs no contienen texto CV, nombre de archivo, token ni URL firmada; consultas/llamadas externas registradas sin doble conteo; medir overhead bajo carga equivalente.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM


## TASK-029 — Consolidar configuración y documentar dependencias activas

Status: TODO
Priority: LOW
Phase: PHASE-6
Category: Maintainability

### Objective

Consolidar configuración y documentar dependencias activas. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-26: ENV/helpers de configuración repetidos; extra sqlchemy mal escrito en fastapi-users; comentario TODO de progreso contradice tabla existente. scripts está ignorado aunque seis scripts ya están versionados. Hay imports locales TYPE_CHECKING que parecen ciclos: no se confirmó ciclo de ejecución.

### Evidence / Location

- `app/config.py; app/db.py:16; app/services/accounts/userService.py:24; app/services/companies/companyService.py:21; pyproject.toml:13; app/models/resourceModel.py:36; .gitignore; README.md` (Confidence: HIGH). 
- Alcance de edición conocido: app/config.py; app/db.py helpers; userService.py y companies/companyService.py configuración compartida; pyproject.toml/uv.lock/requirements.txt; README/PROJECT_STRUCTURE; .gitignore scripts y comentarios obsoletos.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita.

### Proposed Solution

Unificar parsing compartido sin un framework de settings adicional; corregir metadatos/documentación; inventariar imports y consumidores antes de retirar apify/drivers/aliases. Comparar uv.lock con requirements usado por Docker y consultar advisories vigentes al ejecutar tarea; no afirmar CVE sin evidencia. Mantener dos identidades auth distintas. Verificar también dependencias transitivas usadas directamente por scraper/analytics. Consultar advisories oficiales vigentes con versiones lock exactas al ejecutar; si surge CVE abrir tarea con prioridad propia, no actualizar todo dentro de cleanup.

### Scope

IN SCOPE:

- app/config.py; app/db.py helpers; userService.py y companies/companyService.py configuración compartida; pyproject.toml/uv.lock/requirements.txt; README/PROJECT_STRUCTURE; .gitignore scripts y comentarios obsoletos.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/config.py; app/db.py helpers; userService.py y companies/companyService.py configuración compartida; pyproject.toml/uv.lock/requirements.txt; README/PROJECT_STRUCTURE; .gitignore scripts y comentarios obsoletos.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001, TASK-002, TASK-007, TASK-010, TASK-026, TASK-028, TASK-030

### Blocks

Blocks: TASK-031

### Parallelization

Can run in parallel with: NONE

Grupo J; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Consolidar configuración y documentar dependencias activas.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Instalación reproducible con locks; smoke de arranque; escaneo de imports/callers y documentación actualizada; ningún paquete/tabla eliminado solo por heurística.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM


## TASK-030 — Validar respuestas y respetar versión histórica de cuestionario

Status: TODO
Priority: MEDIUM
Phase: PHASE-3
Category: Business Logic / Bug Fix

### Objective

Validar respuestas y respetar versión histórica de cuestionario. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-25: submit suma cada respuesta sin unicidad ni pertenencia validada; IDs desconocidos aportan cero en silencio y repetidos suman varias veces. El perfil lee la definición actual aunque el resultado persistido guarda version.

### Evidence / Location

- `app/services/accounts/questionnaireService.py:19,33,75; app/schemas/questionnaireSchema.py:36; app/models/questionnaireModel.py:8` (Confidence: HIGH). 
- Alcance de edición conocido: app/services/accounts/questionnaireService.py; app/schemas/questionnaireSchema.py; definiciones app/data/questionnaires por versión; tests/test_questionnaire_profile.py.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato.

### Proposed Solution

Validar contra definición versionada: IDs válidos y unicidad según tipo de pregunta. Conservar answers/results como snapshot histórico ligado a versión inmutable; no recalcular resultados anteriores con el JSON actual. Conservar scores válidos y orden de desempate actual. No cambiar pesos ni interpretar preguntas opcionales de forma arbitraria: fijar el comportamiento soportado en fixtures.

### Scope

IN SCOPE:

- app/services/accounts/questionnaireService.py; app/schemas/questionnaireSchema.py; definiciones app/data/questionnaires por versión; tests/test_questionnaire_profile.py.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- app/services/accounts/questionnaireService.py; app/schemas/questionnaireSchema.py; definiciones app/data/questionnaires por versión; tests/test_questionnaire_profile.py.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-001

### Blocks

Blocks: TASK-029, TASK-031

### Parallelization

Can run in parallel with: TASK-003, TASK-004, TASK-007, TASK-009, TASK-020

Grupo B; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Validar respuestas y respetar versión histórica de cuestionario.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Respuesta válida conserva scores; duplicado/desconocido devuelve 422; perfil de versión anterior usa definición anterior; cualquier política de preguntas opcionales queda explícita.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM


## TASK-031 — Verificar compatibilidad integrada y ensayar rollout/restore

Status: TODO
Priority: HIGH
Phase: PHASE-6
Category: Testing

### Objective

Verificar compatibilidad integrada y ensayar rollout/restore. Corregir la causa raíz delimitada en Scope y entregar la validación especificada sin cambios laterales.

### Problem

F-08: La raíz añade columnas a users sin crearlo. Un upgrade elimina job_analysis; otro elimina y recrea applications. No se afirma que producción haya perdido datos, pero ejecutar esta cadena sobre una base heredada o vacía es inseguro/no reproducible. F-24: Logs sin correlación uniforme, duración/query count/calls externos; algunos catch retornan vacío. Tests crean metadata en SQLite, no ejecutan Alembic ni reproducen locks, índices parciales/pgvector y restricciones Postgres. No se encontraron workflows CI versionados.

### Evidence / Location

- `alembic/versions/025e4d7c446f_add_first_name_last_name_nickname_to_.py:21; alembic/versions/4897b7743b34_add_companies_table.py:24; alembic/versions/73a6e7c411b9_add_job_postings_and_update_.py:45` (Confidence: HIGH). 
- `app/logging.py:1; tests/conftest.py:51,79; pytest.ini; pyproject.toml; app/services/applications/dashboardService.py:420` (Confidence: HIGH). 
- Alcance de edición conocido: tests de integración/end-to-end; documentación de rollout, restore y parity; TASKS.md Completion Notes; sin cambios productivos fuera de bug nuevo acordado.

### Why this is a problem

La causa raíz y consecuencias están descritas en Problem, con evidencia del snapshot. Esta tarea resuelve la parte delimitada en Scope; no trata síntomas ajenos ni asume que el estado de producción coincide con SQLite de tests.

### Desired State

Una sola implementación del comportamiento descrito en Proposed Solution, con contratos conservados y fallos/concurrencia tratados según Validation.

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita.

### Proposed Solution

Integrar las ramas en orden del DAG y ejecutar flujos completos con PostgreSQL/Redis/storage fake. Ensayar despliegue de código viejo compatible con schema expandido y rollback. Comparar contratos y métricas con baseline, validar cada Bug Fix declarado. Crear tareas nuevas para defectos descubiertos; no corregirlos lateralmente.

### Scope

IN SCOPE:

- tests de integración/end-to-end; documentación de rollout, restore y parity; TASKS.md Completion Notes; sin cambios productivos fuera de bug nuevo acordado.
- Pruebas de regresión/contrato y documentación estrictamente necesarias para el cambio.

OUT OF SCOPE:

- Reescritura de la aplicación, cambio de framework/proveedor y cualquier refactor no requerido por Objective.
- Modificar umbral de aprobación, pesos de scoring, roles/permisos ajenos al defecto o activar pagos/envío real de email.
- Borrar tablas/columnas/objetos históricos sin inventario, transición y tarea destructiva específica.

### Files / Components Likely Affected

- tests de integración/end-to-end; documentación de rollout, restore y parity; TASKS.md Completion Notes; sin cambios productivos fuera de bug nuevo acordado.
- Tests propios nuevos; no editar fixtures centrales ni archivos reservados por otro agente sin coordinación.

### Dependencies

Depends on: TASK-003, TASK-005, TASK-008, TASK-009, TASK-010, TASK-011, TASK-012, TASK-013, TASK-014, TASK-015, TASK-016, TASK-017, TASK-018, TASK-019, TASK-020, TASK-021, TASK-022, TASK-023, TASK-024, TASK-025, TASK-026, TASK-027, TASK-028, TASK-029, TASK-030

### Blocks

Blocks: NONE

### Parallelization

Can run in parallel with: NONE

Grupo K; solo cuando sus dependencias estén completas y no haya archivo reservado en conflicto. Integración de migraciones y TASKS.md serializada.

### Implementation Notes

**Compatibilidad:** extracción/optimización sin cambiar reglas, resultados ni permisos del producto; cambios de contrato requieren transición explícita. Leer evidencia en los archivos indicados antes de decidir detalles. Si schema real/contrato difiere, documentar diferencia y ajustar únicamente dentro del objetivo. Tests de fallos/concurrencia se agregan antes del cambio que protegen. Para migración: inventario → expansión → backfill reanudable → verificación → constraints/índices → switch de callers → parity; retiro legacy en otra tarea si es destructivo. No compartir AsyncSession entre tareas concurrentes.

### Acceptance Criteria

- [ ] Se implementó el resultado concreto: Verificar compatibilidad integrada y ensayar rollout/restore.
- [ ] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [ ] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Suite rápida e integración pasan; migrations en copia preservan datos; restore probado; flujos estudiante/recruiter/admin/recursos/comunidad/career lab verificados; sin secretos ni requests reales en pruebas. Todos los findings tienen cierre verificado o tarea de seguimiento explícita; no afirmar rollout de producción si solo se ensayó.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Estimated Impact

Security: LOW
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: HIGH

## Completion Notes protocol

El agente añade al final de su tarea, tras validar, este bloque con resultados reales (no rellenarlo anticipadamente), y después cambia su estado/fila a COMPLETED:

```markdown
### Completion Notes

Implemented:
- ...

Validation performed:
- ...

Unexpected findings:
- ...

Follow-up tasks created:
- ...
```

## PARALLEL EXECUTION GROUPS

### Parallel Group A

Can start immediately:

- TASK-001 — Fijar baseline aislada y pruebas PostgreSQL de integridad; depends on NONE.
- TASK-002 — Retirar secretos versionados y unificar destino de migraciones; depends on NONE.

### Parallel Group B

Can start when each task's concrete dependencies are COMPLETED (no barrera global del grupo previo):

- TASK-003 — Restringir borrado de posts al propietario; depends on TASK-001.
- TASK-004 — Renderizar nombres de CV y enlaces sin HTML ejecutable; depends on TASK-001.
- TASK-007 — Contabilizar cada intento Gemini y exigir límites compartidos; depends on TASK-001.
- TASK-009 — Crear baseline y converger schemas históricos sin pérdida; depends on TASK-001, TASK-002.
- TASK-020 — Sacar scraper de LinkedIn del event loop; depends on TASK-001.
- TASK-030 — Validar respuestas y respetar versión histórica de cuestionario; depends on TASK-001.

### Parallel Group C

Can start when each task's concrete dependencies are COMPLETED (no barrera global del grupo previo):

- TASK-005 — Dar identidad única a objetos y hacer recuperable su ciclo de vida; depends on TASK-001, TASK-009.
- TASK-010 — Cubrir autenticación de compañías y validar proxy confiable; depends on TASK-001, TASK-007.
- TASK-014 — Centralizar transiciones y proyección de candidaturas; depends on TASK-001, TASK-009.
- TASK-017 — Derivar contador de comunidad desde membresías; depends on TASK-001, TASK-009.
- TASK-019 — Hacer batch e idempotente la extracción de skills de ofertas; depends on TASK-001, TASK-009.
- TASK-024 — Paginar mensajes con cursor estable y migrar inbox; depends on TASK-001, TASK-009.

### Parallel Group D

Can start when each task's concrete dependencies are COMPLETED (no barrera global del grupo previo):

- TASK-006 — Acotar multipart, media y expansión de documentos; depends on TASK-001, TASK-003, TASK-005.
- TASK-012 — Conciliar ledger IA y completar ciclo de reservas; depends on TASK-001, TASK-007, TASK-009.
- TASK-015 — Serializar selección de entrevista por candidatura; depends on TASK-001, TASK-009, TASK-014.
- TASK-021 — Evitar regeneración de embeddings idénticos; depends on TASK-001, TASK-009, TASK-019.

### Parallel Group E

Can start when each task's concrete dependencies are COMPLETED (no barrera global del grupo previo):

- TASK-008 — Autorizar archivos de recursos por entidad visible; depends on TASK-001, TASK-006.
- TASK-013 — Hacer durable e idempotente el procesamiento CV; depends on TASK-001, TASK-009, TASK-012.
- TASK-022 — Ejecutar CP-SAT fuera del loop con concurrencia acotada; depends on TASK-001, TASK-019, TASK-021.
- TASK-027 — Validar rangos, estados y metadata de datos analíticos; depends on TASK-001, TASK-009, TASK-015, TASK-019, TASK-021.

### Parallel Group F

Can start when each task's concrete dependencies are COMPLETED (no barrera global del grupo previo):

- TASK-011 — Normalizar errores públicos y recuperación transaccional; depends on TASK-001, TASK-006, TASK-008.
- TASK-023 — Dividir Capstone conservando facade y contratos; depends on TASK-001, TASK-013, TASK-019, TASK-021, TASK-022, TASK-027.

### Parallel Group G

Can start when each task's concrete dependencies are COMPLETED (no barrera global del grupo previo):

- TASK-016 — Unificar aprobación de CV y proyección de progreso; depends on TASK-001, TASK-009, TASK-011, TASK-012, TASK-014.
- TASK-028 — Medir flujos críticos y hacer visibles fallos parciales; depends on TASK-001, TASK-011, TASK-013, TASK-015, TASK-020, TASK-022, TASK-023.

### Parallel Group H

Can start when each task's concrete dependencies are COMPLETED (no barrera global del grupo previo):

- TASK-018 — Agrupar consultas de progreso de recursos; depends on TASK-001, TASK-016.
- TASK-025 — Calcular dashboard en DB y definir transición de listados; depends on TASK-001, TASK-016.

### Parallel Group I

Can start when each task's concrete dependencies are COMPLETED (no barrera global del grupo previo):

- TASK-026 — Separar API, estado y render de Jobs y Career Lab; depends on TASK-001, TASK-004, TASK-013, TASK-016, TASK-018, TASK-020, TASK-023, TASK-024, TASK-025.

### Parallel Group J

Can start when each task's concrete dependencies are COMPLETED (no barrera global del grupo previo):

- TASK-029 — Consolidar configuración y documentar dependencias activas; depends on TASK-001, TASK-002, TASK-007, TASK-010, TASK-026, TASK-028, TASK-030.

### Parallel Group K

Can start when each task's concrete dependencies are COMPLETED (no barrera global del grupo previo):

- TASK-031 — Verificar compatibilidad integrada y ensayar rollout/restore; depends on TASK-003, TASK-005, TASK-008, TASK-009, TASK-010, TASK-011, TASK-012, TASK-013, TASK-014, TASK-015, TASK-016, TASK-017, TASK-018, TASK-019, TASK-020, TASK-021, TASK-022, TASK-023, TASK-024, TASK-025, TASK-026, TASK-027, TASK-028, TASK-029, TASK-030.

## DEPENDENCY GRAPH

```mermaid
graph TD
    T001["TASK-001"]
    T002["TASK-002"]
    T003["TASK-003"]
    T004["TASK-004"]
    T005["TASK-005"]
    T006["TASK-006"]
    T007["TASK-007"]
    T008["TASK-008"]
    T009["TASK-009"]
    T010["TASK-010"]
    T011["TASK-011"]
    T012["TASK-012"]
    T013["TASK-013"]
    T014["TASK-014"]
    T015["TASK-015"]
    T016["TASK-016"]
    T017["TASK-017"]
    T018["TASK-018"]
    T019["TASK-019"]
    T020["TASK-020"]
    T021["TASK-021"]
    T022["TASK-022"]
    T023["TASK-023"]
    T024["TASK-024"]
    T025["TASK-025"]
    T026["TASK-026"]
    T027["TASK-027"]
    T028["TASK-028"]
    T029["TASK-029"]
    T030["TASK-030"]
    T031["TASK-031"]
    T001 --> T003
    T001 --> T004
    T001 --> T005
    T009 --> T005
    T001 --> T006
    T003 --> T006
    T005 --> T006
    T001 --> T007
    T001 --> T008
    T006 --> T008
    T001 --> T009
    T002 --> T009
    T001 --> T010
    T007 --> T010
    T001 --> T011
    T006 --> T011
    T008 --> T011
    T001 --> T012
    T007 --> T012
    T009 --> T012
    T001 --> T013
    T009 --> T013
    T012 --> T013
    T001 --> T014
    T009 --> T014
    T001 --> T015
    T009 --> T015
    T014 --> T015
    T001 --> T016
    T009 --> T016
    T011 --> T016
    T012 --> T016
    T014 --> T016
    T001 --> T017
    T009 --> T017
    T001 --> T018
    T016 --> T018
    T001 --> T019
    T009 --> T019
    T001 --> T020
    T001 --> T021
    T009 --> T021
    T019 --> T021
    T001 --> T022
    T019 --> T022
    T021 --> T022
    T001 --> T023
    T013 --> T023
    T019 --> T023
    T021 --> T023
    T022 --> T023
    T027 --> T023
    T001 --> T024
    T009 --> T024
    T001 --> T025
    T016 --> T025
    T001 --> T026
    T004 --> T026
    T013 --> T026
    T016 --> T026
    T018 --> T026
    T020 --> T026
    T023 --> T026
    T024 --> T026
    T025 --> T026
    T001 --> T027
    T009 --> T027
    T015 --> T027
    T019 --> T027
    T021 --> T027
    T001 --> T028
    T011 --> T028
    T013 --> T028
    T015 --> T028
    T020 --> T028
    T022 --> T028
    T023 --> T028
    T001 --> T029
    T002 --> T029
    T007 --> T029
    T010 --> T029
    T026 --> T029
    T028 --> T029
    T030 --> T029
    T001 --> T030
    T003 --> T031
    T005 --> T031
    T008 --> T031
    T009 --> T031
    T010 --> T031
    T011 --> T031
    T012 --> T031
    T013 --> T031
    T014 --> T031
    T015 --> T031
    T016 --> T031
    T017 --> T031
    T018 --> T031
    T019 --> T031
    T020 --> T031
    T021 --> T031
    T022 --> T031
    T023 --> T031
    T024 --> T031
    T025 --> T031
    T026 --> T031
    T027 --> T031
    T028 --> T031
    T029 --> T031
    T030 --> T031
```
