# Refactor Task Board

## Allowed Statuses

- TODO
- IN PROGRESS
- BLOCKED
- COMPLETED
- SUPERSEDED

SUPERSEDED se añadió al adoptar el plan 08: una tarea cuyo trabajo pasó a otra ficha no se borra ni se renumera, porque su ID es estable y su historia sigue siendo evidencia. Se marca SUPERSEDED, se nombra la tarea que la reemplaza y no se vuelve a reclamar. No es un estado terminal de éxito: no cuenta como COMPLETED.

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

La primera modificación del agente debe reclamar su tarea: TODO → IN PROGRESS en este archivo. Leer [hallazgos](02_AUDIT_FINDINGS.md) y evidencia indicada antes de editar. READY es derivado: Status == TODO y todas las Dependencies == COMPLETED; no es un status permitido. **READY al generar el plan: TASK-001 y TASK-002.** **READY al adoptar el plan 08 (2026-09-07): TASK-018, TASK-019, TASK-020, TASK-024, TASK-025, TASK-030, TASK-032, TASK-033, TASK-034 y TASK-036.** Las tres últimas abren la migración y no tocan código de producción, así que pueden arrancar en paralelo con las de backend. Una tarea SUPERSEDED nunca es READY.

## Plan vigente

Este tablero ejecuta **[08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md)**: separación en `backend/` y `frontend/`, FastAPI como API JSON bajo `/api/v1`, SPA React + TypeScript servida por Nginx y despliegue en dos servicios de Cloud Run. Ese plan reemplaza explícitamente la decisión de conservar Jinja de [07_REFACTOR_PLAN.md](07_REFACTOR_PLAN.md).

Qué sobrevive del plan anterior y qué no:

- **La auditoría sigue siendo válida como insumo.** [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md), [05_DATABASE_AUDIT.md](05_DATABASE_AUDIT.md) y [04_SOURCE_OF_TRUTH_MATRIX.md](04_SOURCE_OF_TRUTH_MATRIX.md) describen el dominio, no la capa de presentación. Los hallazgos se corrigen dentro de la vertical que toca ese dominio; no se portan al código nuevo como si fueran diseño.
- **TASK-001 a TASK-032 siguen vigentes salvo donde se indique.** Son correcciones de backend —seguridad, integridad, concurrencia, N+1— que hacen falta con Jinja y con React por igual. Migrar sobre un backend con IDOR o con carreras de estado solo traslada el defecto a una pantalla nueva.
- **Lo que sí cambia** es todo lo que asumía que la presentación seguiría siendo Jinja + JS por pantalla. Ver *Reconciliación con el plan 08* más abajo.
- **PHASE-0 a PHASE-6** son las fases del plan anterior. **PHASE-M0 a PHASE-M5** son las de la migración y corresponden a las Fases 0–5 de §9 del plan 08. Se numeran aparte para que no se confundan.

Las fases M no bloquean globalmente a las anteriores: una tarea de backend pendiente puede ejecutarse en paralelo mientras no toque un archivo reservado. Solo Dependencies bloquea funcionalmente.

## Reconciliación con el plan 08

| Tarea previa | Efecto de adoptar el plan 08 |
| --- | --- |
| TASK-018, TASK-019, TASK-020, TASK-021, TASK-022, TASK-023, TASK-025, TASK-027, TASK-030 | **Sin cambios.** Son correcciones de backend, independientes de la capa de presentación. |
| TASK-024 | **Vigente, con su consumidor reasignado.** El cursor estable y la paginación siguen siendo suyos y TASK-041 los generaliza; el inbox lo migra TASK-051 en React, no reescribiendo el JS legacy. |
| TASK-026 | **SUPERSEDED.** Su Proposed Solution dice literalmente «sin cambiar a React», que es lo contrario del plan vigente. Su intención —separar API, estado y render de Jobs y Career Lab— la cumplen TASK-049 y TASK-052 sobre React. El backend de Capstone lo sigue dividiendo TASK-023, que continúa vigente. |
| TASK-028 | **Vigente y ampliada.** TASK-045 añade health, readiness y logging estructurado que Cloud Run consume; TASK-057 construye alertas sobre las métricas que TASK-028 emite. No son dos telemetrías. |
| TASK-029 | **Vigente y ampliada.** El alcance pasa a cubrir dependencias de backend y de frontend, y el lock de cada uno. |
| TASK-031 | **Vigente y ampliada.** Verifica compatibilidad integrada sobre el monolito; TASK-058 hace lo propio sobre la topología de dos servicios. TASK-058 depende de ella. |
| TASK-032 | **Absorbida por TASK-040.** Extender el mapeo de errores a las rutas restantes se hace ya con la forma final del error model (`code` estable, `request_id`), en vez de normalizar dos veces. TASK-032 sigue siendo su dependencia formal. |

Ninguna tarea COMPLETED se reabre. TASK-016 y TASK-017, cerradas bajo el plan anterior, dejan resultados que el plan 08 necesita: una policy de aprobación y una proyección de progreso únicas (§7 exige que React no recalcule reglas), y una baseline verde — el fallo que §2 del plan 08 pone como condición de salida de su Fase 0 se corrigió en TASK-017.

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
| TASK-010 | Cubrir autenticación de compañías y validar proxy confiable | CRITICAL | PHASE-1 | COMPLETED | TASK-001, TASK-007 | TASK-005, TASK-014, TASK-017, TASK-019, TASK-024 |
| TASK-011 | Normalizar errores públicos y recuperación transaccional | CRITICAL | PHASE-1 | COMPLETED | TASK-001, TASK-006, TASK-008 | TASK-023 |
| TASK-012 | Conciliar ledger IA y completar ciclo de reservas | HIGH | PHASE-2 | COMPLETED | TASK-001, TASK-007, TASK-009 | TASK-006, TASK-015, TASK-021 |
| TASK-013 | Hacer durable e idempotente el procesamiento CV | HIGH | PHASE-2 | COMPLETED | TASK-001, TASK-009, TASK-012 | TASK-008, TASK-022, TASK-027 |
| TASK-014 | Centralizar transiciones y proyección de candidaturas | HIGH | PHASE-2 | COMPLETED | TASK-001, TASK-009 | TASK-005, TASK-010, TASK-017, TASK-019, TASK-024 |
| TASK-015 | Serializar selección de entrevista por candidatura | HIGH | PHASE-2 | COMPLETED | TASK-001, TASK-009, TASK-014 | TASK-006, TASK-012, TASK-021 |
| TASK-016 | Unificar aprobación de CV y proyección de progreso | HIGH | PHASE-3 | COMPLETED | TASK-001, TASK-009, TASK-011, TASK-012, TASK-014 | TASK-028 |
| TASK-017 | Derivar contador de comunidad desde membresías | HIGH | PHASE-2 | COMPLETED | TASK-001, TASK-009 | TASK-005, TASK-010, TASK-014, TASK-019, TASK-024 |
| TASK-018 | Agrupar consultas de progreso de recursos | HIGH | PHASE-4 | TODO | TASK-001, TASK-016 | TASK-025 |
| TASK-019 | Hacer batch e idempotente la extracción de skills de ofertas | HIGH | PHASE-4 | TODO | TASK-001, TASK-009 | TASK-005, TASK-010, TASK-014, TASK-017, TASK-024 |
| TASK-020 | Sacar scraper de LinkedIn del event loop | HIGH | PHASE-4 | TODO | TASK-001 | TASK-003, TASK-004, TASK-007, TASK-009, TASK-030 |
| TASK-021 | Evitar regeneración de embeddings idénticos | MEDIUM | PHASE-4 | TODO | TASK-001, TASK-009, TASK-019 | TASK-006, TASK-012, TASK-015 |
| TASK-022 | Ejecutar CP-SAT fuera del loop con concurrencia acotada | MEDIUM | PHASE-4 | TODO | TASK-001, TASK-019, TASK-021 | TASK-008, TASK-013, TASK-027 |
| TASK-023 | Dividir Capstone conservando facade y contratos | HIGH | PHASE-5 | TODO | TASK-001, TASK-013, TASK-019, TASK-021, TASK-022, TASK-027 | TASK-011 |
| TASK-024 | Paginar mensajes con cursor estable y migrar inbox | MEDIUM | PHASE-4 | TODO | TASK-001, TASK-009 | TASK-005, TASK-010, TASK-014, TASK-017, TASK-019 |
| TASK-025 | Calcular dashboard en DB y definir transición de listados | MEDIUM | PHASE-4 | TODO | TASK-001, TASK-016 | TASK-018 |
| TASK-026 | Separar API, estado y render de Jobs y Career Lab | HIGH | PHASE-5 | SUPERSEDED | TASK-001, TASK-004, TASK-013, TASK-016, TASK-018, TASK-020, TASK-023, TASK-024, TASK-025 | NONE |
| TASK-027 | Validar rangos, estados y metadata de datos analíticos | MEDIUM | PHASE-2 | TODO | TASK-001, TASK-009, TASK-015, TASK-019, TASK-021 | TASK-008, TASK-013, TASK-022 |
| TASK-028 | Medir flujos críticos y hacer visibles fallos parciales | MEDIUM | PHASE-4 | TODO | TASK-001, TASK-011, TASK-013, TASK-015, TASK-020, TASK-022, TASK-023 | TASK-016 |
| TASK-029 | Consolidar configuración y documentar dependencias activas | LOW | PHASE-6 | TODO | TASK-001, TASK-002, TASK-007, TASK-010, TASK-026, TASK-028, TASK-030 | NONE |
| TASK-030 | Validar respuestas y respetar versión histórica de cuestionario | MEDIUM | PHASE-3 | TODO | TASK-001 | TASK-003, TASK-004, TASK-007, TASK-009, TASK-020 |
| TASK-031 | Verificar compatibilidad integrada y ensayar rollout/restore | HIGH | PHASE-6 | TODO | TASK-003, TASK-005, TASK-008, TASK-009, TASK-010, TASK-011, TASK-012, TASK-013, TASK-014, TASK-015, TASK-016, TASK-017, TASK-018, TASK-019, TASK-020, TASK-021, TASK-022, TASK-023, TASK-024, TASK-025, TASK-027, TASK-028, TASK-029, TASK-030 | NONE |
| TASK-032 | Extender el mapeo de errores públicos a las rutas restantes | HIGH | PHASE-3 | TODO | TASK-011 | TASK-030 |
| TASK-033 | Fijar toolchains y congelar la baseline de la migración | HIGH | PHASE-M0 | COMPLETED | NONE | TASK-034, TASK-036 |
| TASK-034 | Inventariar rutas y construir la matriz legacy → REST | HIGH | PHASE-M0 | COMPLETED | NONE | TASK-033, TASK-036 |
| TASK-035 | Capturar OpenAPI, fixtures y baseline visual de las pantallas actuales | HIGH | PHASE-M0 | COMPLETED | TASK-034 | TASK-036 |
| TASK-036 | Decidir y registrar el patrón de ingreso a Cloud Run | HIGH | PHASE-M0 | COMPLETED | NONE | TASK-033, TASK-034, TASK-035 |
| TASK-037 | Mover el backend a backend/ sin cambiar comportamiento | HIGH | PHASE-M1 | COMPLETED | TASK-033, TASK-035 | TASK-036 |
| TASK-038 | Crear el scaffold React y el compose local con proxy same-origin | HIGH | PHASE-M1 | TODO | TASK-037 | TASK-036 |
| TASK-039 | Separar CI en lanes de backend y frontend | HIGH | PHASE-M1 | TODO | TASK-037, TASK-038 | TASK-036 |
| TASK-040 | Implantar el error model único y el request id en toda la API | HIGH | PHASE-M2 | TODO | TASK-032, TASK-037 | TASK-041, TASK-042, TASK-045 |
| TASK-041 | Estandarizar paginación, límites de colección e idempotencia | HIGH | PHASE-M2 | TODO | TASK-024, TASK-037 | TASK-040, TASK-042, TASK-045 |
| TASK-042 | Exponer sesión, login y logout por actor con CSRF double-submit | CRITICAL | PHASE-M2 | TODO | TASK-010, TASK-037 | TASK-040, TASK-041, TASK-045 |
| TASK-043 | Fijar OpenAPI como contrato y generar tipos TypeScript en CI | HIGH | PHASE-M2 | TODO | TASK-039, TASK-040, TASK-041 | TASK-042, TASK-045 |
| TASK-044 | Construir la capa HTTP, los shells y los guards del frontend | HIGH | PHASE-M2 | TODO | TASK-038, TASK-042, TASK-043 | TASK-045 |
| TASK-045 | Publicar health, readiness y logging estructurado de la API | HIGH | PHASE-M2 | TODO | TASK-028, TASK-037 | TASK-040, TASK-041, TASK-042, TASK-043, TASK-044 |
| TASK-046 | Vertical 1 — Shell público y autenticación en React | HIGH | PHASE-M3 | TODO | TASK-035, TASK-042, TASK-044 | NONE |
| TASK-047 | Vertical 2 — Perfil, cuestionario y CV en React | HIGH | PHASE-M3 | TODO | TASK-006, TASK-030, TASK-041, TASK-046 | TASK-048, TASK-050 |
| TASK-048 | Vertical 3 — Dashboard, recursos y roadmaps en React | HIGH | PHASE-M3 | TODO | TASK-018, TASK-025, TASK-046 | TASK-047, TASK-050 |
| TASK-049 | Vertical 4 — Jobs, análisis de CV y candidaturas en React | HIGH | PHASE-M3 | TODO | TASK-020, TASK-041, TASK-046, TASK-054 | TASK-050, TASK-051 |
| TASK-050 | Vertical 5 — Company: dashboard, postings, applicants, entrevistas y recruiters | HIGH | PHASE-M3 | TODO | TASK-046 | TASK-047, TASK-048, TASK-049 |
| TASK-051 | Vertical 6 — Community, friendships y messages en React | HIGH | PHASE-M3 | TODO | TASK-024, TASK-046 | TASK-049, TASK-052 |
| TASK-052 | Vertical 7 — Career Lab / Capstone en React | HIGH | PHASE-M3 | TODO | TASK-022, TASK-023, TASK-046 | TASK-051 |
| TASK-053 | Vertical 8 — Admin en React | HIGH | PHASE-M3 | TODO | TASK-047, TASK-048, TASK-049, TASK-050, TASK-051, TASK-052 | NONE |
| TASK-054 | Sacar el runner de CV del lifespan con outbox y Cloud Tasks | CRITICAL | PHASE-M4 | TODO | TASK-013, TASK-037 | TASK-055 |
| TASK-055 | Aprovisionar Artifact Registry, WIF y Secret Manager | HIGH | PHASE-M4 | TODO | TASK-002, TASK-036, TASK-039 | TASK-054 |
| TASK-056 | Desplegar los servicios Cloud Run, el Job de migraciones y deploy.yml por SHA | HIGH | PHASE-M4 | TODO | TASK-009, TASK-045, TASK-054, TASK-055 | NONE |
| TASK-057 | Configurar dominio, TLS, alertas, budgets y rollback por revisión | HIGH | PHASE-M4 | TODO | TASK-028, TASK-056 | NONE |
| TASK-058 | Ensayar el cutover y observar la ventana de estabilidad | HIGH | PHASE-M5 | TODO | TASK-031, TASK-053, TASK-057 | NONE |
| TASK-059 | Retirar Jinja, templates, JS/CSS legacy y endpoints deprecados | MEDIUM | PHASE-M5 | TODO | TASK-058 | NONE |

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

Status: COMPLETED
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

- [x] Se implementó el resultado concreto: Cubrir autenticación de compañías y validar proxy confiable.
- [x] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [x] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [x] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [x] Relevant tests pass.
- [x] No unrelated refactor was introduced.

### Validation

Límites efectivos para ambas identidades; pruebas de X-Forwarded-For desde peer no confiable; revisar ingreso real antes de cerrar configuración; login legítimo conserva contrato.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Completion Notes

**Entregado.** Login, registro y recuperación de compañías quedan bajo límite por IP, y "cuál es la IP del cliente" pasa a tener una sola definición gobernada por `TRUSTED_PROXY_IPS`. Documentación de ingreso en [`docs/ingress_and_client_ip.md`](../ingress_and_client_ip.md).

**Cambios**

- `app/config.py`: `env_str_any()` (gemelo de `env_int_any`, para renombrar una variable sin romper despliegues); `TRUSTED_PROXY_IPS` (default `private`, lee todavía `FORWARDED_ALLOW_IPS`); `RECOVERY_RATE_LIMIT_MAX` / `RECOVERY_RATE_LIMIT_WINDOW_SECONDS` (5/3600).
- `app/middleware/rate_limit.py`: `TrustedProxyPolicy` + `resolve_client_ip()`. El *peer* del socket es lo único observable, así que decide si la cadena `X-Forwarded-For` puede leerse; cuando puede, se recorre de derecha a izquierda (cada proxy añade lo que vio, luego la entrada más a la derecha que no sea proxy confiable es el cliente; lo de más a la izquierda lo escribió el llamante y no es evidencia). `private` se define con una lista explícita de rangos (loopback, RFC1918, CGNAT `100.64/10`, link-local, ULA) en vez de `ipaddress.is_private`, que también incluye rangos de documentación. El parseo nunca levanta excepción: un token ilegible se ignora, nunca amplía la confianza.
- `app/middleware/rate_limit.py` (reglas): `auth_login` cubre ahora `/auth/jwt/login` **y** `/api/v1/auth/company/login`; `auth_register_burst` y `auth_register_daily` cubren `/api/v1/auth/register` **y** `/api/v1/auth/company/register`; regla nueva `auth_recovery` para `forgot-password`, `reset-password` y `request-verify-token` de ambas identidades. Bucket compartido entre identidades a propósito: lo que se raciona es "intentos de credenciales desde esta IP" y "cuentas creadas desde esta IP", y una cuenta de compañía es una cuenta. Sin cambios en los límites de estudiante ya existentes.
- `app/services/ai/aiRequestRateLimitService.py`: `get_client_ip()` leía `X-Forwarded-For` **sin condición alguna**, así que ese límite por IP se reseteaba por request con solo mandar la cabecera. Ahora usa `resolve_client_ip()`. Es el mismo defecto de F-09 (IP del cliente falsificable) en el segundo consumidor; se corrige aquí en vez de dejar media corrección, y es el único archivo tocado fuera de la lista de Scope.
- `Dockerfile`: `FORWARDED_ALLOW_IPS=*` → `TRUSTED_PROXY_IPS=private`, y el `CMD` deja de pasar `--proxy-headers --forwarded-allow-ips`. uvicorn reescribía `request.client.host` desde la cabecera para *cualquier* peer antes de que la app viera quién conectó de verdad: eso ponía la decisión de confianza en dos sitios y el externo estaba en "confía en todos". Verificado que nada dependía del manejo de proxy de uvicorn: las URLs públicas salen de `APP_BASE_URL`/`PUBLIC_APP_ORIGIN` (`app/app.py:_get_public_base_url`) y el chequeo de mismo origen de admin lee `X-Forwarded-Proto`/`X-Forwarded-Host` por su cuenta (`app/routes/adminRoute.py:50`).
- `tests/test_auth_rate_limits.py` (nuevo, 21 tests) y `docs/ingress_and_client_ip.md` (nuevo); fila de `FORWARDED_ALLOW_IPS` actualizada en `docs/ai_cost_controls.md`.

**Evidencia anterior/posterior** (mismo probe, `TRUSTED_PROXY_IPS=private`, app sobre transporte ASGI, contador reiniciado por escenario)

| Escenario | Antes | Después |
| --- | --- | --- |
| `POST /api/v1/auth/company/login` ×10 | `400`×10 — **0 rechazos** | `400`×8 + `429`×2 |
| `POST /api/v1/auth/company/register` ×7 | `201`×7 — **7 cuentas** | `201`×5 + `429`×2 |
| `POST /api/v1/auth/company/forgot-password` ×7 | `202`×7 | `202`×5 + `429`×2 |
| `POST /api/v1/auth/company/login` ×10 desde peer público rotando `X-Forwarded-For` | `400`×10 | `400`×8 + `429`×2 |

Bypass por cabecera, medido sobre una regla que **ya existía** (registro de estudiante, 8 intentos desde el peer público `203.0.113.9` rotando `X-Forwarded-For`): con `TRUSTED_PROXY_IPS=*` (el default anterior del Dockerfile) → `201`×8, **8 cuentas, 0 rechazos**; con el default nuevo `private` → `201`×5 + `429`×3. El bypass era real, no hipotético, siempre que el contenedor sea alcanzable de forma directa.

**Validación ejecutada**

- `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/test_auth_rate_limits.py -q` → **21 passed en 3.49 s**. Cubre: peer no confiable no puede declarar su IP; proxy confiable devuelve el cliente que vio; prefijo puesto por el llamante ignorado; CIDR explícito no implica rangos privados; `*` conserva la semántica anterior; `none` no confía en nadie; tokens ilegibles no amplían confianza; sin peer → `unknown`; `FORWARDED_ALLOW_IPS` legado sigue leyéndose; límite efectivo en login/registro/recuperación de compañía; bucket compartido entre identidades; login legítimo de compañía sigue devolviendo 200/204 con cookie; y el control inverso — con peer de loopback (proxy confiable) las IPs distintas **sí** obtienen buckets distintos, que es lo que evita que todos los usuarios detrás del balanceador compartan un solo cubo.
- Suite completa: `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider -q` → **329 passed, 31 skipped en 45.36 s** (los 31 skips son la lane de integración sin sus URLs + 1 preexistente de pgvector).
- Lane PostgreSQL/Redis desechable (`pgvector/pgvector:pg16` en 127.0.0.1:55432, `redis:7-alpine` en 127.0.0.1:56379): `TEST_DATABASE_URL_PG=... TEST_REDIS_URL=... .venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/integration -q` → **31 passed en 29.89 s**. Sin regresión en el counter store compartido que respalda estas ventanas.
- Versiones: Python 3.10.19, pytest 9.0.2, plataforma darwin. Sin llamadas pagadas ni migraciones; esta tarea no toca la DB.

**Límites de la validación**

- **El ingreso real no está verificado y esa parte queda abierta.** `private` es un default seguro, no una configuración cerrada: no se comprobó desde qué dirección alcanza el balanceador de producción al contenedor, ni si el contenedor es alcanzable directamente. Antes de cerrar la configuración hay que hacer los tres pasos de [`docs/ingress_and_client_ip.md`](../ingress_and_client_ip.md#before-closing-the-configuration) y fijar `TRUSTED_PROXY_IPS` al CIDR real. Requiere acceso a la plataforma de despliegue, no disponible desde esta sesión.
- Riesgo asociado y por qué el default es conservador: si el balanceador alcanzara el contenedor desde una IP **pública** no listada, la cabecera se ignoraría y todos los usuarios caerían en un solo bucket (falso 429 masivo). Los rangos privados/CGNAT cubren las plataformas gestionadas habituales; aun así, el primer despliegue debe mirar métricas de 429 antes de darlo por bueno.
- Sin smoke de navegador: el cambio es de red/limitación, sin superficie de frontend. El contrato de login legítimo se cubre con el test de cookie.
- La cadena `X-Forwarded-For` de un proxy que **no** anexa lo que ve (mal configurado) no es recuperable por ninguna política; queda documentado.

### Estimated Impact

Security: HIGH
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM


## TASK-011 — Normalizar errores públicos y recuperación transaccional

Status: COMPLETED
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

- [x] Se implementó el resultado concreto: Normalizar errores públicos y recuperación transaccional.
- [x] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [x] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [x] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [x] Relevant tests pass.
- [x] No unrelated refactor was introduced.

### Validation

Excepción simulada con marcador sensible no aparece en body/log público; 4xx conservados; 500 genérico con correlación; no continuar usando sesión fallida.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Completion Notes

**Entregado.** Las cuatro rutas del Scope dejan de responder con `str(e)`: el cuerpo público lleva código estable, mensaje fijo y referencia corta; la causa real va al log redactada bajo esa misma referencia; y un fallo a mitad de transacción devuelve la sesión limpia.

**Cambios**

- `app/core/errors.py` (nuevo, el "helper error mapping" del Scope): `server_failure()` y `client_failure()` — se usan como `raise await server_failure(exc, ...)` — más `redact()`, `is_safe_client_message()`, `log_cause()` y los códigos estables (`CODE_*`).
  - **Contrato del cuerpo:** `detail` sigue siendo *string* (todo el frontend lo lee así: `admin.js`, `career_lab.js`, `company-candidates.js`…), con la referencia añadida al final: `"The file could not be uploaded. (ref: 02b0b293135e)"`. El código estable y la referencia van además en las cabeceras `X-Error-Code` / `X-Error-Id`, que es lo nuevo que un cliente puede consumir sin parsear texto.
  - **Redacción del log:** el traceback se formatea y se redacta aquí en vez de pasarlo por `exc_info`, porque la credencial suele vivir en el mensaje de la propia excepción y el formateador estándar lo imprimiría intacto. Se enmascaran DSN con credenciales, pares `clave=valor` credenciales (incluido `db_password:`), `Authorization:` hasta fin de línea, `Bearer …` y claves tipo `AKIA…`.
  - **4xx conservados con criterio:** `client_failure()` preserva el mensaje escrito por el autor (`"Video lessons require a valid video URL."`) porque ese es el contrato existente, pero solo tras comprobarlo: el tipo de excepción no dice de dónde salió el texto, y `ValueError` también lo levantan las librerías. Un mensaje con `://`, `[SQL:`, ruta de fichero, nombre de librería, `…Error:` o más de 200 caracteres se sustituye por uno genérico y se registra.
  - **Recuperación transaccional:** ambas funciones hacen `rollback` de la sesión si se les pasa. Tras una sentencia fallida la sesión solo puede levantar `PendingRollbackError`, y la petición **no** ha terminado con ella (dependencias y teardown siguen corriendo).
- `app/routes/questionnaireRoute.py:41`, `app/routes/resourceRoute.py:47,49`, `app/routes/resumeRoute.py:93`, `app/routes/adminRoute.py:320,340,369,371`: todos los `str(e)`/`str(exc)` sustituidos por el mapeo. En `adminRoute` se añadió además `except Exception` en create/update de recursos: antes solo se capturaba `ValueError`, así que cualquier otro fallo salía por el handler por defecto sin rollback.
- **Dos cambios de status deliberados** (el caso defectuoso descrito, no refactor lateral): `GET /api/v1/resources/file` devolvía **400** con `"Resource storage is not configured."` — culpaba al cliente y publicaba estado de configuración; ahora **503** genérico. `_require_resume_storage_location_id()` devolvía **500** con `"Server misconfiguration: missing resume storage configuration"`; ahora **503** genérico con referencia. Ningún cliente del repo depende de esos textos (`admin.js` y `career_lab.js` tienen su propio mensaje de reserva).
- `tests/test_error_redaction.py` (nuevo, 25 tests) y `tests/integration/test_error_recovery_pg.py` (nuevo, 3 tests en la lane PostgreSQL).

**Evidencia anterior/posterior** (misma excepción simulada en las cinco rutas; marcador sensible = DSN con contraseña + `[SQL: SELECT users.hashed_password …]` + `password=…`)

| Endpoint | Antes | Después |
| --- | --- | --- |
| `GET /api/v1/questionnaire/profile` | 500, `detail` = la excepción completa (**DSN, contraseña y SQL en el cuerpo**) | 500, `"We could not load your questionnaire profile right now. (ref: 45e3f67e035c)"` |
| `GET /api/v1/resources/file` | 500, `"Failed to fetch resource file: (psycopg2.OperationalError) … password=…"` | 500, `"The resource file could not be fetched. (ref: 1b4aa9f28444)"` |
| `POST /api/v1/profile/cv/upload` | 500, `"Failed to upload file: … postgresql://app:<contraseña>@10.0.0.4:5432/prod …"` | 500, `"The CV could not be uploaded. Please try again. (ref: afc4f8d96e68)"` |
| `POST /api/v1/admin/resources` (ValueError de librería) | 400 con la excepción completa | 400 genérico con referencia (4xx conservado) |
| `POST /api/v1/admin/resources/upload-file` | 500 con la excepción completa | 500, `"The file could not be uploaded. (ref: …)"` |

En los cinco casos: `leaks_secret=False`, `leaks_sql=False`, y `X-Error-Id` presente en cabecera y cuerpo. El log correspondiente sí conserva el traceback, con `postgresql://app:***@…` y `password=***`.

**Validación ejecutada**

- `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/test_error_redaction.py -q` → **25 passed en 2.46 s**. Cubre: redacción de las formas credenciales habituales; mensajes de validación legítimos que sí se muestran; texto de maquinaria que nunca llega al llamante; las cinco rutas sin filtración con referencia presente en cuerpo y log; 4xx preservado con el mensaje del autor intacto; y la ruta de éxito de subida de CV sin cambios.
- Lane PostgreSQL: `TEST_DATABASE_URL_PG=... TEST_REDIS_URL=... .venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/integration -q` → **34 passed en 21.00 s** (31 previos + 3 nuevos). Los nuevos prueban lo que SQLite no reproduce: PostgreSQL aborta el bloque tras la violación de constraint y rechaza todo hasta el `rollback`; después del handler la misma sesión vuelve a ejecutar `SELECT 1`.
- Suite completa: `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider -q` → **354 passed, 31 skipped en 82.27 s**.
- Versiones: Python 3.10.19, pytest 9.0.2, plataforma darwin. Sin llamadas pagadas ni migraciones.

**Límites de la validación**

- `is_safe_client_message()` es una heurística sobre texto, no una garantía. Es segura por diseño en la dirección que importa (ante la duda sustituye), pero un mensaje de validación futuro escrito con una ruta o un nombre de librería dentro se volverá genérico sin previo aviso. Lo correcto a medio plazo es que la validación levante un tipo propio en vez de `ValueError`; queda fuera del Scope de esta tarea (tocaría el codec de lecciones).
- La redacción del log cubre formas credenciales conocidas. Un secreto sin forma reconocible (un valor suelto sin clave) seguiría en el traceback del log; el cuerpo público nunca lo lleva, porque **no** incluye texto de excepción en ningún caso.
- Sin smoke de navegador: el `detail` sigue siendo string y los clientes ya tienen mensaje de reserva propio; no hay cambio de forma en la respuesta más allá de las dos cabeceras nuevas.
- No se auditaron los servicios que las rutas llaman: si un servicio construye un `HTTPException` con texto interno por su cuenta, esta tarea no lo intercepta.

**Hallazgo registrado, no corregido (fuera de Scope)** → **TASK-032**

`app/routes/dashboardRoute.py:58,82,100` y `app/routes/jobRoute.py:131` siguen devolviendo `str(e)` en el `detail` de un 500, exactamente el mismo defecto en rutas que el Scope de esta tarea no lista. El helper ya existe; falta aplicarlo. Registrado como TASK-032 en vez de ampliar esta tarea en silencio.

### Estimated Impact

Security: HIGH
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM


## TASK-012 — Conciliar ledger IA y completar ciclo de reservas

Status: COMPLETED
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

### Completion Notes

**Entregado.** El ledger es la única autoridad de consumo: cada reserva es una fila con ciclo explícito, un cargo es idempotente por referencia, y la historia previa al ledger se concilió **por identidad** para poder retirar el `max(legacy)`.

**Cambios**

- `app/models/aiUsageModel.py`: `AIUsageStatus` (`reserved` / `committed` / `released` / `expired` / `superseded`) más columnas `status` (server_default `committed`, así las filas históricas siguen contando igual) y `expires_at` (lease de la reserva). Dos índices parciales, declarados en el modelo para que autogenerate no proponga borrarlos: `uq_ai_usage_events_reference` (único sobre `reference_type, reference_id` **solo** donde `reference_id IS NOT NULL AND status='committed'`) e `ix_ai_usage_events_reserved_expiry`.
- `app/services/ai/aiUsageService.py`:
  - `reserve()` escribe además una fila `reserved` con lease de 15 min (`RESERVATION_LEASE_SECONDS`). Contador atómico y ledger dejan de contradecirse: el contador cierra la carrera entre réplicas, la fila hace durable y auditable la reclamación.
  - `get_used_today()` lee **solo** el ledger: `committed` + `reserved` con lease vivo. Una reserva caducada deja de contar por predicado, sin trabajo de reparación en el camino de lectura.
  - `_reclaim_expired_reservations()` corre en transacción propia (`async_sessionmaker(self.session.bind)`), nunca enredada con la del llamante: el UPDATE es el árbitro, y solo quien realmente marcó la fila baja el contador compartido — por eso dos reservas concurrentes no pueden devolver el mismo slot abandonado dos veces. El decremento solo toca una clave existente (un DECRBY sobre clave ausente la crearía sin TTL y el siguiente `reserve_incr` sembraría desde 1 en vez de desde el uso real).
  - `commit_usage()` liquida la fila reservada en vez de añadir otra; ante una referencia ya cargada devuelve la existente y **libera** la reserva duplicada. Llamarlo dos veces sobre la misma reserva devuelve lo ya cobrado.
  - `commit_usage`/`record_usage` escriben con sentencias Core dentro de un SAVEPOINT, no con flush ORM: un flush fallido envenena toda la sesión y el llamante perdería el resultado que iba a confirmar; dentro del savepoint solo se deshace el savepoint. Verificado contra PostgreSQL.
  - `release(reason=...)` marca la fila y distingue `released_no_spend` de `released_after_provider_attempt`. Se apoya en la sesión viva si hay transacción abierta; si la petición que reservó ya terminó (el análisis de CV corre en background con sesión propia) abre una transacción corta sobre el mismo engine; si nada de eso es posible, el lease es el respaldo.
  - `legacy_parity_gaps()`: la evidencia de conciliación, re-ejecutable. `_get_legacy_used_today()` sigue existiendo pero fuera del camino de cuota, como lado "antes" de la comparación.
- `app/services/resumes/resumeCourseAuditService.py`: subida, alta de evaluación y extracción pasan **dentro** del `try` que devuelve la reserva. `_EvaluationAborted` transporta el dato que no se puede adivinar después — si el evaluador llegó a llamar al proveedor — y `_settle_failed_attempt()` cierra las dos mitades (slot y evaluación). El cargo y el resultado siguen confirmándose en la misma transacción (`commit_usage` solo hace flush; `complete_evaluation` confirma ambos).
- `alembic/versions/d1c7e3a95b48_...py` (nueva, sobre `c3e8b1a7d240`): expansión → marcado de duplicados → índices → backfill por lotes reanudable → verificación de paridad. Nada histórico se borra: un cargo duplicado pasa a `superseded` y deja de contar, pero permanece como evidencia.
- `app/db_baseline.py`: baseline actualizado con las dos columnas y los dos índices (si no, `test_bootstrapped_schema_matches_metadata` se niega a estampar).
- `tests/integration/test_migrations.py::test_upgrade_head_commits_on_an_existing_database`: nombraba la tabla que creaba la revisión más reciente, así que fallaba con **cualquier** migración nueva en vez de con el fallo que vigila. Reescrito contra el head genérico (stamp rebobinado, replay, `stamped == head` + cero diferencias de schema).
- Nuevos: `tests/test_ai_reservation_cycle.py` (11), `tests/test_resume_course_audit_recovery.py` (5), `tests/integration/test_ai_ledger_pg.py` (6). `tests/test_ai_usage.py`: el test `..._until_ledger_takes_over` describía el estado previo; sustituido por el contrato nuevo más uno de paridad.
- `docs/ai_cost_controls.md`: sección "The reservation cycle" con la tabla de estados y las tres consecuencias.

**Bug Fix declarado — dos cambios de comportamiento deliberados**

1. **Un `job_analysis` sin cargo ya no consume cuota.** `max(ledger, legacy_count)` contaba *toda* fila de `job_analysis`, incluidas aquellas cuyo slot se había devuelto explícitamente (acierto de caché, CV ilegible). Ahora solo un cargo en el ledger es un cargo. Ninguno de esos casos llama al proveedor, así que no habilita gasto; el techo global de intentos sigue siendo el límite de coste.
2. **Un fallo del proveedor devuelve el slot y lo deja dicho.** El comportamiento (devolver el slot) se conserva; lo nuevo es que la fila registra que hubo intento real, en vez de que sea indistinguible de "no se llamó a nadie".

El backfill preserva la cuota histórica exactamente: cada fila legacy recibe un cargo, así que el total por usuario/feature/día después es el que `max(legacy)` daba antes.

**Evidencia anterior/posterior**

| Escenario | Antes | Después |
| --- | --- | --- |
| Fallo del evaluador tras reservar (5 intentos seguidos) | slot consumido en cada intento: el usuario agota su día con 3 fallos | `used_today == 0`, `remaining_today == 3`; 5 filas `released` con `released_after_provider_attempt` |
| Fallo de subida / CV ilegible | reserva retenida hasta medianoche (la liberación vivía después del `try`) | slot devuelto, evaluación en `FAILED`, fila `released_no_spend` |
| Mismo `job_analysis` confirmado dos veces | dos filas en el ledger: doble cargo | una fila; la segunda reserva se libera como `released_duplicate_reference` |
| Dos sesiones PostgreSQL confirmando el mismo resultado a la vez | ambas insertan | `_committed_count == 1`, `used_today == 1`, sesión perdedora intacta |
| Proceso muerto entre reservar y liquidar | slot retenido el resto del día | deja de contar al vencer el lease; el siguiente `reserve()` lo recupera y acredita el contador una sola vez |
| 3 análisis + 2 auditorías previas al ledger | `used_today` = 3 / 2 vía `max(legacy)` | tras el backfill, 3 / 2 vía ledger, `legacy_parity_gaps() == []`, y re-ejecutar el backfill no cambia nada |

**Validación ejecutada**

- `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider -q` → **371 passed, 40 skipped en 45.40 s** (los 40 skips son las lanes PG/Redis sin variables y el test pgvector).
- Lane PostgreSQL/Redis (`pgvector/pgvector:pg16` + `redis:7-alpine` desechables en 55432/56379): `TEST_DATABASE_URL_PG=... TEST_REDIS_URL=... .venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/integration -q` → **40 passed en 21.56 s** (34 previos + 6 nuevos). Incluye la cadena completa de migraciones sobre la revisión nueva y el bootstrap por baseline.
- Sin llamadas pagadas: el evaluador es un doble en todos los tests nuevos y la lane bloquea sockets salientes. Sin migraciones contra producción.
- Python 3.10.19, pytest 9.0.2, darwin.

**Límites de la validación**

- El lease es de 15 minutos y está fijo en código (`RESERVATION_LEASE_SECONDS`), no en configuración. Si un análisis llegara a tardar más, su reserva dejaría de contar antes de liquidarse y el usuario podría reservar un slot extra. Los análisis actuales tardan segundos; hacerlo configurable pertenece a la tarea que toque `config.py`.
- La corrección de deriva del contador Redis solo ocurre cuando el mismo usuario vuelve a reservar. Un usuario que no reintenta ese día conserva la deriva hasta que la clave con fecha expira; la fila DB, en cambio, se corrige por predicado de inmediato.
- El backfill atribuye una fila de ledger a cada fila legacy porque eso es exactamente lo que la lectura anterior contaba. No intenta reconstruir *qué* llamada al proveedor costó dinero: ese dato nunca se guardó.
- La paridad se **registra**, no se impone, en la migración: corre contra historia real y un operador necesita ver la divergencia, no que el upgrade muera. `legacy_parity_gaps()` permite reejecutarla después del despliegue.
- Sin smoke de navegador: la respuesta de la auditoría conserva forma y claves (`attempts_today`, `daily_limit`, `attempts_remaining`); lo que cambia son los números en los casos de fallo, y eso está cubierto por tests de servicio.
- `cvAnalysisService` sigue llamando a `reservation.release()` sin sesión (su fichero pertenece a TASK-013): funciona por la ruta de sesión propia, y TASK-013 puede darle una liquidación explícita al hacer durable el job.


## TASK-013 — Hacer durable e idempotente el procesamiento CV

Status: COMPLETED
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

### Completion Notes

**Entregado.** `job_analysis` es ahora una cola durable: claim atómico, lease, recuperación tras reinicio y un solo trabajo vivo por CV. La respuesta `job_id`/`status` y el polling no cambian.

**Cambios**

- `app/models/jobAnalysisModel.py`: `attempts`, `lease_expires_at` y `provider_attempted_at`, más dos índices parciales sobre `status IN ('PENDING','PROCESSING')` (las etiquetas que PostgreSQL guarda de verdad, porque SQLAlchemy persiste los *nombres* del Enum): `uq_job_analysis_active_per_resume` (único por `user_id, resume_id` entre trabajos vivos) e `ix_job_analysis_active_lease`.
- `app/services/ai/cvAnalysisService.py`:
  - `create_pending_analysis()` inserta con sentencia Core dentro de un SAVEPOINT y, si pierde la carrera, devuelve el trabajo ganador. Es la corrección directa de "leer si hay uno corriendo" + INSERT como dos sentencias.
  - `claim_job()`: un UPDATE condicional (`PENDING`, o `PROCESSING` con lease vencido) es todo el traspaso. Quien obtiene `rowcount == 1` es el dueño.
  - `recover_stale_jobs()` clasifica por `provider_attempted_at`: sin llamada al proveedor y `attempts < 3` → vuelve a `PENDING`; sin llamada y agotado → `FAILED` explícito; **con llamada ya hecha → `FAILED` explícito, nunca reintento**.
  - `process_job()` empieza reclamando; si no lo consigue, devuelve la reserva y sale. `_process_resume()` sella `provider_attempted_at` y confirma **antes** de llamar a Gemini, y reserva cuota ahí mismo si llegó sin reserva (el caso del trabajo recuperado). Estados terminales limpian el lease.
- `app/services/ai/cvAnalysisRunner.py` (nuevo): barrido con sesión propia por trabajo, `wake()` para latencia, `stop()` limpio; registrado en el lifespan de `app/app.py`. La cola sigue siendo la tabla: meter Redis al lado sería un segundo sitio que puede discrepar sobre el mismo trabajo.
- `app/routes/jobRoute.py`: sigue despachando por `BackgroundTasks` (latencia) y además despierta al runner (durabilidad); es seguro porque el claim es atómico. Si la petición se unió a un trabajo ya en marcha, devuelve su slot y responde "already in progress".
- `alembic/versions/e8b4d2f7a316_...py` (nueva, sobre `d1c7e3a95b48`) y baseline actualizado. Aditiva: los cuatro estados conservan significado. Clasifica lo histórico sin reiniciarlo — las filas atascadas en `PROCESSING` sin lease (imposibles de distinguir de un worker vivo, salvo que ningún worker anterior a esta revisión puede seguir vivo) reciben estado terminal explícito, y los duplicados activos del mismo CV se cierran dejando el más reciente.
- `docs/cv_analysis_jobs.md` (nuevo): cola, claim, recuperación y la regla que manda sobre "recupera".
- Tests nuevos: `tests/test_cv_analysis_queue.py` (10) y `tests/integration/test_cv_analysis_queue_pg.py` (4).

**Evidencia anterior/posterior**

| Escenario | Antes | Después |
| --- | --- | --- |
| Dos POST simultáneos (PostgreSQL, dos conexiones) | dos filas `job_analysis`, dos análisis, dos gastos | una fila; ambos reciben el mismo `job_id` |
| Dos workers reclaman el mismo trabajo | ambos procesaban | `[True, False]`; `attempts == 1` (perder la carrera no consume intento) |
| Reinicio antes de llamar al proveedor | `PROCESSING` para siempre; el CV queda bloqueado | vuelve a `PENDING` al vencer el lease y el runner lo termina sin que nadie repita el POST |
| Reinicio después de llamar al proveedor | igual, bloqueado | `FAILED` con motivo explícito; no se repite el gasto |
| Trabajo que muere siempre igual | reintentos sin límite si algo lo reencolaba | `FAILED` tras 3 intentos |
| Replay del mismo trabajo | segunda llamada al LLM y posible doble cargo | ni llamada ni cargo: no es reclamable y el ledger es idempotente por `job_id` |

**Validación ejecutada**

- `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider -q` → **381 passed, 44 skipped en 47.27 s**.
- Lane PostgreSQL/Redis: `TEST_DATABASE_URL_PG=... TEST_REDIS_URL=... .venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/integration -q` → **44 passed en 22.21 s** (40 + 4 nuevos), incluida la cadena de migraciones sobre la revisión nueva.
- Sin llamadas pagadas: `ask_llm_model` y la descarga del CV son dobles en todos los tests; la lane bloquea sockets salientes.

**Límites de la validación**

- **Sin smoke de navegador.** `app/static/js/jobs.js` aparece en la evidencia pero no en el Scope de edición de esta tarea, así que no se tocó: la respuesta conserva forma (`job_id`, `status`, `keywords`, `error_message`). El cliente sigue rindiéndose a los 60 s; ahora el trabajo termina igualmente y el siguiente `analyze` devuelve el análisis cacheado, pero **el mensaje que ve el usuario sigue diciendo "Analysis timed out"**. Corregir ese texto pertenece a la tarea que toque el frontend de Jobs (TASK-026).
- El runner es por proceso y su intervalo (5 s), el lease (300 s) y el máximo de intentos (3) están fijos en código, no en configuración.
- No se probó un `SIGKILL` real a mitad de análisis: la interrupción se simula venciendo el lease, que es el estado que el proceso muerto deja. Un `kill -9` durante la llamada a Gemini quedaría cubierto por la misma rama (`provider_attempted_at` sellado y confirmado antes de llamar).
- La recuperación de un trabajo adoptado reserva cuota de nuevo: si el usuario agotó su día entre el fallo y la recuperación, el trabajo termina en `FAILED` por cuota en vez de completarse. Es deliberado — el derecho se comprueba en el momento del gasto — pero es un cambio observable respecto a "la reserva original ya estaba hecha".
- El índice único trata `resume_id NULL` como distinto (comportamiento estándar), así que no restringe trabajos sin CV asociado. El código actual siempre lo informa.


## TASK-014 — Centralizar transiciones y proyección de candidaturas

Status: COMPLETED
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

### Completion Notes

**Entregado.** El status de una candidatura cambia por una sola operación, que escribe estado, evento y contadores en la misma transacción. Los agregados se aplican con upsert e incremento en SQL, y los enums existen una vez.

**Cambios**

- `app/services/applications/applicationService.py`:
  - `TransitionActor` (estudiante o recruiter) y `transition_status()`: la única vía por la que cambia el status. Devuelve `False` si ya está en ese estado, así que un comando repetido no genera un segundo evento de un cambio que no ocurrió. `record_application_created()` hace lo propio con el alta.
  - `lock_application()`: bloqueo de fila antes de leer el status actual. Es un `select` del id a secas a propósito: añadir `FOR UPDATE` a la consulta que hidrata relaciones haría que PostgreSQL la rechazara por el outer join.
  - `_apply_daily_aggregate_delta()` pasa a `INSERT ... ON CONFLICT DO UPDATE` con suma en SQL (dialecto PostgreSQL o SQLite). El leer-modificar-escribir perdía incrementos y, peor, dos escritores podían chocar creando la fila del día y convertir una actualización de analítica en una petición fallida.
  - `rebuild_daily_aggregates(company_id, since)`: reconstruye la proyección desde el log de eventos. Explícita y con `since` obligatorio por el punto de corte (abajo).
  - Los tres puntos que escribían status (`create_application`, `update_application`, `update_company_application`) pasan por la operación única, bajo bloqueo.
- `app/services/jobs/interviewService.py`: publicar disponibilidad ya no asigna `application.status = INTERVIEW`; llama a `transition_status()` bajo el mismo bloqueo. Es el defecto concreto de F-11: esa transición no dejaba evento ni contador.
- `app/schemas/applicationSchema.py`: `ApplicationStatus` y `ApplicationMatchStrength` se reexportan desde el modelo en vez de redeclararse. Eran dos enums idénticos, y un valor podía ser válido en el esquema y desconocido para la columna sin que nada fallara hasta llegar a la base.
- `app/services/companies/companyRecruiterService.py`: el ranking de rol se define una vez (`COMPANY_RECRUITER_ROLE_RANK`, `recruiter_role_rank()`, `recruiter_role_rank_case()`) y `applicationService` lo usa. Estaba escrito dos veces, con el mismo orden y distinto valor para "cualquier otro" (3 en SQL, 99 en Python) — mismo orden, que es justo por lo que la duplicación sobrevivió. **Criterio sin cambios.**
- `docs/application_transitions.md` (nuevo): contrato, las tres fuentes y su papel, y el punto de corte.
- Tests nuevos: `tests/test_application_transitions.py` (10) y `tests/integration/test_application_transitions_pg.py` (3).

**Punto de corte y diferencias legacy**

Los eventos son historial autoritativo **desde el despliegue de este cambio**. Antes, las transiciones hechas al publicar disponibilidad no escribían nada, así que el log **subcuenta** entradas a INTERVIEW en ese periodo y los contadores de esos días son *más* correctos que un replay del log. Por eso `rebuild_daily_aggregates()` exige `since` y nunca se ejecuta sola: reconstruir hacia atrás sustituiría números correctos por una subcuenta. No se reconstruyó nada retroactivamente.

**Evidencia anterior/posterior**

| Escenario | Antes | Después |
| --- | --- | --- |
| Publicar disponibilidad de entrevista | status = INTERVIEW, **cero eventos**, contador `entered_interview_count` sin tocar | un evento con `from_status=IN_REVIEW` y actor recruiter, `entered_interview_count = 1` |
| Publicar dos veces | segunda pasada volvía a asignar el mismo status | segunda es no-op: un solo evento, un solo conteo |
| 20 incrementos concurrentes (PostgreSQL, 20 sesiones) | incrementos perdidos por leer-modificar-escribir; posible violación de la constraint al crear la fila del día | `status_change_events_count == 20`, `entered_in_review_count == 20`, **una** fila del día |
| El mismo comando dos veces a la vez (PostgreSQL) | ambos leían "applied" y ambos escribían evento | un evento, un conteo (lo decide el bloqueo de fila) |
| Enum del esquema vs columna | dos clases distintas con los mismos valores | `SchemaStatus is ColumnStatus` |
| Proyección corrupta de un día | sin forma de repararla salvo a mano | `rebuild_daily_aggregates(since=hoy)` la redibuja desde los eventos |

**Validación ejecutada**

- `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider -q` → **391 passed, 47 skipped en 59.91 s**.
- Lane PostgreSQL/Redis: `TEST_DATABASE_URL_PG=... TEST_REDIS_URL=... .venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/integration -q` → **47 passed en 26.89 s** (44 + 3 nuevos).
- Sin migración: el cambio es de comportamiento, no de schema. Sin envío real de email (el servicio de notificaciones sigue encolando mocks). Sin llamadas pagadas.

**Límites de la validación**

- **Sin smoke de navegador.** No se tocó frontend: los payloads conservan forma y los valores de los enums son idénticos (verificado en test). Los clientes leen `status` como string.
- El bloqueo de fila no existe en SQLite, así que en la lane rápida los tests de concurrencia pasarían por construcción; la afirmación real vive en la lane PostgreSQL, que es donde se ejecutó.
- `rebuild_daily_aggregates()` no tiene endpoint ni comando: se invoca desde una sesión de mantenimiento. Exponerlo pertenece a la tarea de dashboard (TASK-025).
- La cuenta `applications_deleted_count` no se ejercita aquí: ninguna ruta emite hoy un evento `DELETED`. El rebuild lo contempla, pero no hay dato con el que probarlo.
- El bloqueo se toma en las tres rutas de transición y en la publicación de entrevista. Cualquier código futuro que escriba `application.status` directamente vuelve a abrir el agujero; no hay constraint que lo impida, solo la operación única y esta documentación.


## TASK-015 — Serializar selección de entrevista por candidatura

Status: COMPLETED
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

### Completion Notes

**Entregado.** Confirmar una entrevista está serializado por candidatura, es idempotente al reintentar el mismo slot, y la base impone como máximo una reserva efectiva por candidatura.

**Cambios**

- `app/models/interviewAvailabilityModel.py`: índice único parcial `uq_interview_availabilities_booked_per_application` sobre `application_id` donde `status = 'booked'` (valor, no nombre: este Enum persiste valores). **No es una agenda global**: los slots pertenecen a una candidatura, así que esto no dice nada sobre el calendario del recruiter.
- `app/services/jobs/interviewService.py`:
  - `select_user_availability()` bloquea la candidatura antes de leer el estado, reutilizando `ApplicationService.lock_application()` de TASK-014.
  - Reintentar **el mismo** slot devuelve el estado existente (200) en vez de 400 "no longer available", y no encola una segunda confirmación.
  - Elegir **otro** slot cuando ya hay uno confirmado responde **409** con mensaje explícito, en vez de sobrescribir en silencio.
  - Tras reservar, pasa por `transition_status(INTERVIEW)`: normalmente no-op, pero garantiza que una confirmación nunca implique un cambio de estado invisible.
  - `_get_booked_slot()` como única lectura de "la hora confirmada".
- `alembic/versions/f4c9a17be205_...py` (nueva, sobre `e8b4d2f7a316`) y baseline actualizado. Primero **inventaria** los duplicados y los registra, luego conserva la confirmación más antigua por candidatura (la que ambas partes conocieron primero) y pasa el resto a `cancelled`. **No elimina disponibilidades.** El downgrade suelta el índice pero no resucita las canceladas: eso recrearía la ambigüedad que la revisión resolvió.
- Tests nuevos: `tests/test_interview_selection.py` (6) y `tests/integration/test_interview_selection_pg.py` (3).

**Evidencia anterior/posterior**

| Escenario | Antes | Después |
| --- | --- | --- |
| Dos sesiones eligiendo slots distintos a la vez (PostgreSQL) | ambas reservaban, cada una cancelaba la elección de la otra, **dos** emails "interview confirmed" | una reserva; la otra recibe 409; **un** email de confirmación |
| Reintentar el mismo slot | 400 "Interview slot is no longer available" sobre la elección propia | 200 con el estado actual, sin segundo email |
| Elegir otro slot después de confirmar | reservaba el segundo y cancelaba el primero | 409 explícito; el primero sigue reservado |
| Escritura directa de un segundo `booked` | permitida | `IntegrityError` del índice parcial |
| Base con dos `booked` en la misma candidatura | indetectable | la migración lo reporta, conserva el más antiguo y cancela el otro; ambas filas siguen en la tabla |

**Validación ejecutada**

- `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider -q` → **397 passed, 50 skipped en 55.27 s**.
- Lane PostgreSQL/Redis: `TEST_DATABASE_URL_PG=... TEST_REDIS_URL=... .venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/integration -q` → **50 passed en 30.48 s** (47 + 3 nuevos), incluida la cadena de migraciones sobre la revisión nueva.
- Emails: siguen siendo el servicio de notificaciones *mock* (se escriben en `email_notification_logs`); el conteo de confirmaciones es precisamente lo que verifica el test de concurrencia. **No se envió correo real.**

**Límites de la validación**

- **Sin smoke de navegador.** `app/static/js/jobs.js` no está en el Scope de esta tarea y no se tocó; su manejador de `interview-selection` muestra el `detail` de cualquier respuesta no-ok, así que el 409 nuevo se renderiza con su texto, y el reintento ahora devuelve 200 y pinta "Interview confirmed". Se verificó leyendo `selectInterviewAvailability()`, no ejecutando el navegador.
- **Cambio de contrato deliberado:** el mismo slot pasa de 400 a 200 y un slot distinto de 400 a 409. Ningún cliente del repo distingue códigos en esa llamada.
- No se ofrece "cambiar de hora": una vez confirmada, elegir otra es 409. Reprogramar es una decisión de producto, no un defecto de concurrencia; si se quiere, es tarea aparte.
- Publicar nuevas disponibilidades cancela las `available` pero no toca una ya `booked`, así que tras confirmar, unos slots nuevos no serían elegibles (409). Es el comportamiento anterior más el índice; cambiarlo sería ampliar el alcance.
- El bloqueo de fila no existe en SQLite: la lane rápida prueba las reglas y el índice, la concurrencia real solo se demuestra en PostgreSQL.


## TASK-016 — Unificar aprobación de CV y proyección de progreso

Status: COMPLETED
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

- [x] Se implementó el resultado concreto: Unificar aprobación de CV y proyección de progreso.
- [x] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [x] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [x] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [x] Relevant tests pass.
- [x] No unrelated refactor was introduced.

### Validation

Mismo usuario obtiene mismos porcentajes en dashboard/recurso; evaluación aprobada sin fila de progreso coherente; score 7.99/8, múltiples evaluaciones y CV borrado; lecturas no escriben stats; parity report legacy antes del switch.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Completion Notes

Dos módulos nuevos concentran lo que estaba repartido:

- `app/services/learning/resumeApproval.py` — la única regla de aprobación.
  `RESUME_APPROVAL_MIN_SCORE` sigue siendo **8.0**; no se tocó el umbral, solo
  dejó de reescribirse. Lo consumen `resume_audit_llm.py` (normalización de
  `pass_status`), `resume_audit_schema.py` (el texto del reporte interpola el
  umbral), `applicationService.list_approved_resumes` (vía
  `approved_evaluation_clauses()`, con `MIN_APPROVED_RESUME_SCORE` conservado
  como atributo derivado), `resumeCourseAuditService.complete_evaluation` y el
  proyector.
- `app/services/learning/courseProgress.py` — `CourseProgressProjector`, una
  sola proyección desde los hechos (`resource_lesson_progress` + evaluación
  aprobada). La usan la página de curso (`ResourceService`) y el dashboard.
  Solo lee: ningún método escribe.

Bug Fixes declarados, todos dentro de F-15:

1. **Recursos aprobaba con `pass_status` solo.** Una fila histórica con
   `pass_status=True` y score 7.5 completaba la lección `resume_upload` aunque
   ese mismo CV no podía adjuntarse a una candidatura. Ahora las tres rutas
   exigen COMPLETED + `pass_status` + score >= 8.
2. **El dashboard no veía la aprobación.** Contaba filas de progreso en SQL
   crudo, así que la lección completada por auditoría aparecía hecha en el curso
   y ausente en el dashboard. Las dos pantallas comparten la proyección.
3. **`pass_status` guardado podía contradecir al score.** `complete_evaluation`
   copiaba el flag del resultado; ahora lo deriva del score con la policy.
4. **Una fila de progreso obsoleta mantenía completa una lección de upload.**
   La auditoría decide ese tipo de lección; la fila explícita ya no la sostiene
   tras borrar el CV aprobado.
5. **GET escribía caches.** `/api/v1/dashboard/stats` insertaba la fila
   `user_stats` del usuario en la primera lectura y la sincronizaba después. Ya
   no. La caracterización `test_dashboard_stats_currently_writes_a_user_stats_row_on_read`
   de TASK-001 anticipaba exactamente esto y decía que se voltearía aquí: pasó a
   `test_dashboard_stats_does_not_write_on_read`.

Identidad estable de cursos core: `resources.core_code` (nullable, índice único
`ix_resources_core_code`), migración `a7d3f81c9e64`. El backfill reclama una fila
por curso **solo si el match por título es inequívoco** (exactamente un recurso
publicado con ese título); títulos ambiguos, ausentes o despublicados quedan sin
asignar y se registran en el log para que un operador decida. No se renombra,
fusiona ni borra nada. Como fallback documentado, un despliegue cuyas filas son
anteriores al backfill se resuelve por título mientras el match sea único;
`core_course_code_inventory()` reporta qué resolvió por código, por título o por
nada. `scripts/seed_resources.py` siembra los códigos. `app/db_baseline.py`
incorpora la columna y el índice, de modo que bootstrap y metadata siguen
coincidiendo.

`user_stats` queda como cache legacy documentado: se lee solo cuando ningún
curso core tiene contenido (despliegue sin seed) y nunca se escribe. No se
eliminó ninguna columna ni tabla. Mantener ese fallback es deliberado: quitarlo
bajaría a 0% un despliegue sin cursos sembrados, que es un cambio de porcentajes
distinto del cambio estructural de esta tarea.

Cache de stage del roadmap: **verificado, no fusionado**. `user_stage_progress`
se escribe solo al actualizar una tarea; `test_reading_a_roadmap_does_not_write_its_stage_cache`
fija que `get_roadmap_detail` no escribe nada.

Parity: `test_parity_with_the_legacy_computation_when_no_audit_is_involved`
reimplementa el cálculo reemplazado (COUNT de filas por título) y exige igualdad
exacta con la proyección cuando no hay lección `resume_upload` — es decir, el
switch no mueve ningún número salvo donde la auditoría es el motivo.
`test_the_legacy_computation_is_the_one_that_was_wrong` documenta esa única
diferencia: legacy 50% vs proyectado 100% con auditoría aprobada.

Validación ejecutada:

```
.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider -q \
  tests/test_course_progress_projection.py
# 25 passed

.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider -q
# 429 passed, 61 skipped in 48.98s

TEST_DATABASE_URL_PG=postgresql+asyncpg://testuser:***@127.0.0.1:55432/studentscompass_test \
TEST_REDIS_URL=redis://127.0.0.1:56379/0 \
.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider -q tests/integration
# 61 passed in 38.30s
```

Casos exigidos por Validation, todos cubiertos: mismos porcentajes en dashboard y
curso; evaluación aprobada sin fila de progreso coherente; 7.99 vs 8.0;
evaluaciones múltiples; CV borrado (las evaluaciones caen por ON DELETE CASCADE y
la lección se descompleta); lecturas sin writes; parity report antes del switch.
En PostgreSQL, `tests/integration/test_core_course_code_migration_pg.py` cubre lo
que SQLite no puede: el índice único rechaza un segundo código igual mientras las
filas sin código quedan libres, el backfill es re-ejecutable, respeta una
asignación hecha a mano y deja intacto el caso ambiguo.

Presupuesto de consultas: proyectar los tres cursos core cuesta un número
constante de SELECTs (<= 6), independiente de cuántos cursos haya; antes eran dos
consultas SQL crudas más una carga completa de outlines para la navegación.

Límites: no se ejecutó smoke de navegador porque la tarea no cambió templates ni
JS — el DTO conserva sus claves (`resume`, `linkedin`, `interview_prep`,
`portfolio`, `overall`) y eso lo fija `tests/test_contract_baseline.py`. El
backfill no se ejecutó contra ningún dato real; en producción hay que revisar el
log de la migración para los códigos que queden sin asignar. No hay lint/typecheck
configurado en el repositorio: N/A.

### Estimated Impact

Security: LOW
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: HIGH


## TASK-017 — Derivar contador de comunidad desde membresías

Status: COMPLETED
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

- [x] Se implementó el resultado concreto: Derivar contador de comunidad desde membresías.
- [x] Todos los casos y métricas específicos de Validation pasan; no quedan errores o validaciones pendientes.
- [x] La evidencia anterior/posterior y límites de la validación están registrados, sin secretos.
- [x] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [x] Relevant tests pass.
- [x] No unrelated refactor was introduced.

### Validation

Altas/bajas simultáneas y eliminación de usuario mantienen count igual a COUNT(*); repetición de join/leave tiene resultado estable; medir consultas/latencia con catálogo representativo.

Ejecutar tests de los componentes indicados mediante `.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider <tests de la tarea>` con dotenv desactivado, DB desechable y proveedores fake. Usar lane PostgreSQL/Redis de TASK-001 para locks, constraints, vector y migraciones; SQLite no los sustituye. Para frontend ejecutar smoke en navegador con backend aislado y comprobar requests/DOM, no solo buscar texto en archivos. Registrar comandos exactos, resultados, métricas y cualquier test omitido. No ejecutar llamadas pagadas ni migraciones de producción como prueba.

### Rollback / Risk Notes

Volver a la implementación anterior solo si conserva las correcciones de seguridad ya integradas y entiende el schema expandido. Conservar datos/backfills; preferir forward fix. Para cambios DB verificar copia/restore y no usar downgrade destructivo. Si no hay cambio DB, revertir solo archivos de la tarea y repetir validación de contratos.

### Completion Notes

`community_members` es la autoridad. `CommunityModel.member_count` es un
`column_property` con subconsulta correlacionada: una sola query para cualquier
número de comunidades, resuelta por la columna líder de `uq_community_member`.
La columna física conserva su nombre en la base (`member_count`) pero el
atributo pasó a llamarse `member_count_cache`, de modo que leer el número viejo
tiene que ser deliberado. No se borró ninguna columna ni tabla.

El caché sigue mantenido, ahora en SQL (`UPDATE ... SET member_count = CASE ...`),
y se puede auditar y reparar explícitamente con `member_count_drift()` y
`reconcile_member_counts()`. Ninguna lectura escribe: un GET que reparara el
caché convertiría cada vista en una escritura y ocultaría la deriva.

Dos defectos aparecieron al ejecutar la validación y se corrigieron dentro del
Scope de esta tarea:

1. **`max()` de dos argumentos no existe en PostgreSQL.** El clamp a 0 del
   decremento se escribía `func.max(col - 1, 0)`, válido en SQLite y agregado en
   PostgreSQL: `leave_community` fallaba con `UndefinedFunctionError` contra la
   base real. Sustituido por `case((moved < 0, 0), else_=moved)`, portable en
   ambos motores. Solo el lane PostgreSQL lo detecta; SQLite lo aceptaba.
2. **Un join duplicado hacía rollback de toda la transacción.** El `IntegrityError`
   del constraint único se manejaba con `session.rollback()`, que expiraba los
   objetos ya cargados por el caller. Ahora el flush ocurre dentro de
   `session.begin_nested()`: el insert rechazado revierte solo su savepoint y el
   resto de la transacción queda intacto. El contrato no cambia — el caller sigue
   recibiendo `AlreadyMemberError` y la ruta sigue devolviendo 409.

Validación ejecutada:

```
.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider -q \
  tests/test_communities.py tests/test_community_member_count.py
# 13 passed

TEST_DATABASE_URL_PG=postgresql+asyncpg://testuser:***@127.0.0.1:55432/studentscompass_test \
TEST_REDIS_URL=redis://127.0.0.1:56379/0 \
.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider -q \
  tests/integration/test_community_member_count_pg.py
# 5 passed

.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider -q
# 404 passed, 55 skipped in 45.87s
```

`tests/integration/test_community_member_count_pg.py` cubre en PostgreSQL real,
con conexiones separadas, lo que SQLite no puede reproducir: seis altas
simultáneas, altas y bajas entrecruzadas, el mismo usuario uniéndose dos veces a
la vez, y el borrado de un usuario que arrastra su membresía por ON DELETE
CASCADE. En los cuatro casos lo que se sirve al lector es igual a `COUNT(*)`.
El caso de cascada además fija que el caché queda obsoleto (2 vs 1), que
`member_count_drift` lo reporta y que `reconcile_member_counts` lo repara y es
idempotente.

Métrica de N+1: listar 8 comunidades ejecuta **1** statement (`counter.total == 1`),
medido en el lane PostgreSQL; antes el conteo venía de una columna por fila, así
que el presupuesto es constante y no crece con el catálogo.

Límites: no se midió latencia con un catálogo de tamaño productivo — el lane usa
datos sintéticos. No se ejecutó backfill ni reconciliación contra ningún dato
real; `reconcile_member_counts` queda disponible como operación explícita. El
retiro de la columna `member_count` es destructivo y pertenece a otra tarea.

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

**Nota de reconciliación (plan 08):** el cursor estable y la paginación siguen siendo de esta tarea, y TASK-041 los generaliza al resto de la API. El consumidor del inbox lo migra TASK-051 en React; no reescribir el JS legacy del inbox aquí.

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

Status: SUPERSEDED

**Reemplazada por TASK-049 y TASK-052 al adoptar el plan 08.** Su Proposed Solution
ordena reorganizar el JS de Jobs y Career Lab «sin cambiar a React», que es lo
contrario del plan vigente: ese JS se retira en TASK-059. La intención —separar
acceso a API, estado y render— la cumplen las verticales sobre React. La división
del backend de Capstone **no** está superseded: sigue siendo TASK-023, vigente y
dependencia de TASK-052. No reclamar esta tarea.
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

**Nota de reconciliación (plan 08):** esta tarea emite las métricas de negocio. TASK-045 añade `/healthz`, `/readyz` y el logging estructurado que Cloud Run consume, y TASK-057 construye las alertas sobre lo que aquí se emite. No crear una segunda fuente de telemetría.

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

**Nota de reconciliación (plan 08):** el alcance pasa a cubrir dependencias y lock de backend **y** de frontend, en el layout de monorepo de TASK-037 y TASK-038.

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

**Nota de reconciliación (plan 08):** esta tarea verifica el sistema actual. TASK-058 hace el mismo ejercicio sobre la topología de dos servicios de Cloud Run y depende de ella. TASK-026 se retiró de sus Dependencies por quedar SUPERSEDED.

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

Depends on: TASK-003, TASK-005, TASK-008, TASK-009, TASK-010, TASK-011, TASK-012, TASK-013, TASK-014, TASK-015, TASK-016, TASK-017, TASK-018, TASK-019, TASK-020, TASK-021, TASK-022, TASK-023, TASK-024, TASK-025, TASK-027, TASK-028, TASK-029, TASK-030

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

## TASK-032 — Extender el mapeo de errores públicos a las rutas restantes

Status: TODO
Priority: HIGH
Phase: PHASE-3
Category: Security / Bug Fix

**Nota de reconciliación (plan 08):** TASK-040 absorbe este trabajo y lo hace ya con la forma final del error model (`code` estable, `request_id`), para no normalizar las mismas rutas dos veces. Coordinar con TASK-040 antes de empezar por separado.

### Objective

Aplicar el mapeo de errores de `app/core/errors.py` a las rutas que quedaron fuera del Scope de TASK-011 y siguen devolviendo `str(e)` al llamante.

### Problem

Hallazgo de TASK-011: `app/routes/dashboardRoute.py:58,82,100` responde `500` con `detail=f"Error fetching dashboard data: {str(e)}"` y `app/routes/jobRoute.py:131` con `detail=f"Job search failed: {str(e)}"`. Es el mismo defecto que F-09/F-10 describen para las cuatro rutas ya corregidas: una excepción de storage, driver o proveedor lleva DSN, SQL y parámetros al cuerpo público. `dashboardRoute.py:57,81` además registra la causa sin redacción.

### Evidence / Location

- `app/routes/dashboardRoute.py:57,58,81,82,100; app/routes/jobRoute.py:131` (Confidence: HIGH).
- Alcance de edición conocido: app/routes/dashboardRoute.py, app/routes/jobRoute.py: manejo de errores; tests de errores redactados.

### Desired State

Ninguna ruta compone el cuerpo público a partir del texto de una excepción. Cuerpo con código estable, mensaje fijo y referencia; causa al log redactada; `rollback` de la sesión donde el fallo la deja inválida.

**Bug Fix declarado:** se corrige únicamente el comportamiento defectuoso descrito; los flujos válidos mantienen contrato.

### Proposed Solution

Usar `server_failure()` / `client_failure()` de `app/core/errors.py` con códigos nuevos para dashboard y búsqueda de empleo. No inventar helper nuevo ni cambiar el contrato de los 2xx.

### Scope

IN SCOPE:

- app/routes/dashboardRoute.py, app/routes/jobRoute.py: manejo de errores; tests de errores redactados.

OUT OF SCOPE:

- Cambiar la forma de las respuestas correctas, la agregación del dashboard o el scraper de empleo.
- Reescribir el helper de errores o su heurística de mensajes.

### Files / Components Likely Affected

- app/routes/dashboardRoute.py, app/routes/jobRoute.py.

### Dependencies

Depends on: TASK-011

### Blocks

Blocks: NONE

### Parallelization

Can run in parallel with: TASK-030

### Implementation Notes

Reutilizar el patrón ya integrado en `app/routes/resourceRoute.py` y `app/routes/adminRoute.py`. `dashboardRoute` recibe `session`: pasarla al helper para el `rollback`.

### Acceptance Criteria

- [ ] Ninguna de las dos rutas compone `detail` con texto de excepción.
- [ ] Excepción simulada con marcador sensible no aparece en cuerpo ni en log público.
- [ ] 2xx y 4xx existentes conservan contrato.
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Mismo patrón de prueba que `tests/test_error_redaction.py`: excepción simulada con marcador sensible por ruta, comprobar cuerpo, cabeceras `X-Error-Code`/`X-Error-Id` y log redactado.

### Rollback / Risk Notes

Cambio acotado a manejo de errores; revertir solo esos archivos y repetir la validación de contratos.

### Estimated Impact

Security: HIGH
Performance: LOW
Maintainability: MEDIUM
Cost: LOW
Risk: LOW

## TASK-033 — Fijar toolchains y congelar la baseline de la migración

Status: COMPLETED
Priority: HIGH
Phase: PHASE-M0
Category: Infrastructure / Testing

### Objective

Dejar fijadas las versiones de Python y Node que usarán las imágenes de producción, y una baseline de tests verde y repetible en esas versiones.

### Problem

Plan 08 §2 registra `403 passed, 50 skipped, 1 failed` el 2026-09-06, con el fallo en `test_a_repeated_join_is_refused_and_changes_nothing`. Ese fallo ya se corrigió en TASK-017, pero la baseline sigue midiéndose con el intérprete local (`.venv`, Python 3.10) y no hay versión de Node declarada en ningún archivo del repositorio.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:44-48` (Confidence: HIGH).
- `.python-version` existía declarando `3.10`, en contradicción directa con `Dockerfile:1` (`python:3.12-slim`) y con las tres lanes de `.github/workflows/tests.yml` (`python-version: "3.12"`). Corregido a `3.12` en esta tarea.
- Ausencia de `.nvmrc` y de campo `engines`; `pyproject.toml` declaraba `requires-python = ">=3.10"`, es decir, no fijaba el intérprete de runtime.
- TASK-017 Completion Notes: el fallo citado por el plan quedó resuelto (savepoint en `join_community`).

### Why this is a problem

Sin toolchain fijada, la suite verde local no dice nada sobre la imagen que se despliega, y la Fase M1 movería código sin poder demostrar que se comporta igual.

### Desired State

Versiones declaradas en archivos que CI y Docker leen, y una ejecución de la suite completa en esas versiones registrada como punto de comparación para todo lo que sigue.

### Proposed Solution

Declarar Python y Node en archivos versionados (`.python-version`, `.nvmrc`, `requires-python`) y confirmar que la suite rápida y la lane PostgreSQL/Redis pasan en el intérprete elegido. Registrar conteos exactos como baseline. No actualizar dependencias ni cambiar código de producción en esta tarea: fijar versiones y medir, nada más. Si la versión elegida rompe algo, documentar el fallo y abrir tarea propia en vez de parchear de lado.

### Scope

IN SCOPE:

- `.python-version`, `.nvmrc`, `pyproject.toml` (`requires-python`), documentación de toolchain.
- Ejecución y registro de la baseline; ningún cambio de comportamiento.

OUT OF SCOPE:

- Actualizar versiones de dependencias o del lock: es TASK-029.
- Mover archivos al layout de monorepo: es TASK-037.
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `.python-version`, `.nvmrc`, `pyproject.toml`, `README.md`.
- Ningún archivo de `app/` cambia de comportamiento en esta tarea.

### Dependencies

Depends on: NONE

### Blocks

Blocks: TASK-037, TASK-039

### Parallelization

Can run in parallel with: TASK-034, TASK-036

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [x] Las versiones de Python y Node están declaradas en archivos versionados que CI y Docker pueden leer.
- [x] La suite rápida y la lane PostgreSQL/Redis pasan en la versión declarada, con conteos registrados.
- [x] El fallo citado en el plan §2 está resuelto o caracterizado explícitamente.
- [x] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [x] Relevant tests pass.
- [x] No unrelated refactor was introduced.

### Validation

Ejecutar la suite completa y la lane de integración en la versión declarada, registrando comandos y conteos exactos. Comparar con los números de este documento. Cualquier test omitido se nombra.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Completion Notes

Ningún archivo de `app/` cambia. La tarea declara versiones, reconstruye el
entorno local sobre la declarada y mide.

**Python 3.12.** No es una elección nueva: `Dockerfile` ya usaba
`python:3.12-slim` y las tres lanes de `.github/workflows/tests.yml` ya pedían
`python-version: "3.12"`.

Corrección a la Evidence de esta ficha, que decía que `.python-version` no
existía: **sí existía, y declaraba `3.10`.** El problema era peor que «falta una
declaración» — había una, y contradecía a la imagen y a CI. Como `uv` la lee,
cada `uv venv` reconstruía el entorno local en 3.10; la baseline se medía en un
intérprete que el repositorio mismo declaraba y que producción no usa. La ficha
quedó corregida arriba. Ahora `.python-version` dice `3.12`, igual que
`requires-python` de `pyproject.toml`, acotado por arriba (`>=3.12,<3.13`) porque
3.12 es la única versión medida; ampliar ese rango exige medir primero, no
suponer.

**Node 24.** En `.nvmrc`. Es la LTS activa y coincide con el `node` local
(v24.20.0). Todavía no la consume nada: no hay `frontend/`. TASK-038 debe leer
`.nvmrc` al crear el scaffold y reflejarla en `engines` de
`frontend/package.json`, en vez de elegir una versión distinta ahí.

**`.venv` reconstruido.** El Problem de esta ficha señala que la baseline se
medía con el intérprete local en 3.10 mientras la imagen desplegada es 3.12. Se
recreó `.venv` con `uv venv` — sin argumento de versión: lo resuelve
`.python-version`, que es la prueba de que la declaración funciona — y se
reinstaló desde `requirements.txt`. El entorno es reproducible y está en
`.gitignore`; no se versionó nada de él.

**`uv.lock`.** `requires-python` cambió, así que el lock quedaba inconsistente
con `pyproject.toml`. Se regeneró con `uv lock` y se verificó paquete por paquete
que **ninguna versión aplicable a 3.12 cambió**: el diff solo elimina la rama de
resolución ≤3.11 (`async-timeout`, `backports-asyncio-runner`, `exceptiongroup`,
`tomli`, y los `numpy` 2.2.6 / `pandas` 2.3.3 / `scipy` 1.15.3 /
`scikit-learn` 1.7.2 / `networkx` 3.4.2 que solo existían para esos intérpretes).
`numpy` 2.4.1, `pandas` 3.0.3, `scipy` 1.17.0, `scikit-learn` 1.8.0 y
`networkx` 3.6.1 siguen idénticos. El relock además añadió `playwright` y `pyee`,
que estaban en el grupo `dev` de `pyproject.toml` desde TASK-001 pero nunca se
habían lockeado: el lock ya venía desincronizado y esto lo corrige. No es un
bump de dependencias — eso sigue siendo TASK-029.

**`requirements.txt` no se tocó.** Es lo que instalan Docker y CI; regenerarlo sí
sería un cambio de dependencias. Que siga trayendo un par de backports inertes en
3.12 es inocuo y no justifica mover el archivo que define la imagen.

Validación ejecutada, CPython 3.12.12, las tres lanes de CI:

```
.venv/bin/python -m pytest -p no:cacheprovider
# 429 passed, 61 skipped in 48.97s

TEST_DATABASE_URL_PG=postgresql+asyncpg://testuser:***@127.0.0.1:55432/studentscompass_test \
TEST_REDIS_URL=redis://127.0.0.1:56379/0 \
.venv/bin/python -m pytest -p no:cacheprovider tests/integration
# 61 passed in 41.86s

.venv/bin/python -m pytest -p no:cacheprovider -m browser
# 14 passed, 476 deselected in 2.51s
```

Cero fallos. La lane rápida se ejecutó dos veces —antes y después de reconstruir
`.venv`— con el mismo resultado, que es lo que hace repetible la baseline.

**El fallo del plan §2 está resuelto, no caracterizado.**
`test_a_repeated_join_is_refused_and_changes_nothing` pasa; lo cerró TASK-017 con
un savepoint en `join_community`.

**Los 61 omitidos, nombrados.** 60 son `tests/integration` sin
`TEST_DATABASE_URL_PG`/`TEST_REDIS_URL` —la lane de integración los ejecuta y
pasan— y el restante es `tests/test_embedding_service.py:139`, que necesita
pgvector. Ninguno se omite por la versión de Python.

**Contraste con el plan §2, que cuadra exacto.** El plan registraba
`403 passed, 50 skipped, 1 failed` el 2026-09-06 sobre `f9ca382` en Python 3.10;
total 454. Ahora 490. Los 36 de diferencia son tests añadidos después por
TASK-016 y TASK-017: pasados `403 + 1` (el que fallaba) `+ 25` de
`test_course_progress_projection.py` = `429`; omitidos `50 + 11` (5 de
`test_community_member_count_pg.py`, 6 de `test_core_course_code_migration_pg.py`)
= `61`. Ninguna diferencia queda sin explicar, así que el salto de 3.10 a 3.12 no
mueve ningún resultado. Esa es la conclusión que la Fase M1 necesita: lo que se
mueva a `backend/` se compara contra estos números.

Baseline y toolchain quedan documentados en
[docs/TESTING.md](../TESTING.md#toolchain-fijada).

**Lint / typecheck: N/A.** Sigue sin haber linter ni type checker configurado, y
esta tarea no introduce uno. Ya está documentado en `docs/TESTING.md`.

Límites: la baseline es funcional, no de rendimiento ni visual —eso es TASK-035—
y se midió en macOS arm64, no en la imagen `python:3.12-slim` de producción. La
paridad de imagen se comprueba cuando exista compose local (TASK-038). `.nvmrc`
no tiene todavía ningún consumidor que lo verifique en CI; hasta TASK-038/TASK-039
la versión de Node es una declaración sin test.

### Estimated Impact

Security: LOW
Performance: LOW
Maintainability: HIGH
Cost: LOW
Risk: LOW

## TASK-034 — Inventariar rutas y construir la matriz legacy → REST

Status: COMPLETED
Priority: HIGH
Phase: PHASE-M0
Category: Documentation / API Contract

### Objective

Producir un inventario machine-readable de los handlers actuales y la matriz completa de correspondencia con el contrato REST objetivo.

### Problem

Plan 08 §2 cuenta 150 handlers entre `app/routes` y `app/views`, de los cuales 23 son vistas. §5.2 propone la normalización pero solo tabula 19 correspondencias: el resto no está mapeado, y sin ese mapa no se puede saber cuándo una vertical terminó.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:33-37` (recuento de handlers).
- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:141-172` (tabla parcial de normalización).
- `app/routes/`, `app/views/views.py` (Confidence: HIGH).

### Why this is a problem

Una migración por verticales necesita saber, por pantalla, qué endpoints la sostienen, quién los consume y qué contrato los reemplaza. Sin inventario, «cero tráfico legacy» no es verificable.

### Desired State

Un artefacto versionado, generado desde el código y no escrito a mano, que liste cada handler con método, ruta, actor requerido, consumidor y destino REST, más la matriz de retiro.

### Proposed Solution

Generar el inventario desde la app FastAPI (rutas registradas, dependencias de auth, response_model) en un script reproducible que escriba JSON o CSV versionado. Cruzarlo con los consumidores reales grepeando templates y JS. Extender §5.2 hasta cubrir los 150 handlers, marcando cada uno como «migra», «se mantiene como interno» o «se retira». No renombrar nada todavía: esta tarea produce el mapa.

### Scope

IN SCOPE:

- Script de inventario en `scripts/`; artefacto versionado bajo `docs/refactor/`.
- Extensión de la tabla de §5.2 del plan 08 hasta cobertura completa.

OUT OF SCOPE:

- Implementar endpoints nuevos o renombrar los existentes: eso ocurre en cada vertical.
- Modificar el comportamiento de cualquier handler.
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `scripts/` (script nuevo), `docs/refactor/` (artefacto e informe).
- Lectura de `app/routes/`, `app/views/`, `app/templates/`, `app/static/js/`.

### Dependencies

Depends on: NONE

### Blocks

Blocks: TASK-035, TASK-040

### Parallelization

Can run in parallel with: TASK-033, TASK-036

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [x] El inventario se genera desde el código, no a mano, y es reejecutable.
- [x] Cada handler tiene actor requerido, consumidor conocido y destino declarado.
- [x] Ningún handler queda sin clasificar; los sin consumidor identificable se listan como tales.
- [x] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [x] Relevant tests pass.
- [x] No unrelated refactor was introduced.

### Validation

Reejecutar el script y comprobar que el artefacto no cambia. Verificar por muestreo que el actor y el consumidor declarados coinciden con el código. Contrastar el total con el recuento del plan §2 y explicar cualquier diferencia.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Completion Notes

Ningún archivo de `app/` cambia. Entrega `scripts/route_inventory.py`,
`docs/refactor/route_inventory.{json,csv}`, `docs/refactor/route_targets.csv` y
el informe [09_ROUTE_MATRIX.md](09_ROUTE_MATRIX.md).

**Lo derivable y lo decidible, separados.** El inventario —método, ruta, actor,
dependencias de auth, `response_model`, módulo, consumidor— se lee de la app en
ejecución. El destino REST no es derivable del código: es diseño, y vive en
`route_targets.csv`, escrito y revisado a mano. El script solo los cruza.
Mezclarlos habría hecho imposible distinguir un hecho de una intención al revisar
el diff.

**El actor se resuelve por identidad de objeto, no por nombre.** El primer
intento clasificó 150 de 175 handlers como `UNKNOWN`: las dependencias que crea
`fastapi_users.current_user(...)` son closures llamados todos
`current_user_dependency`. El script recorre el árbol `route.dependant` que
FastAPI resuelve —dependencias heredadas del router y anidadas incluidas— y
compara contra los objetos declarados en `userService`, `adminService` y
`companyService`. Las siete rutas generadas dentro de fastapi-users
(`/auth/jwt/logout`, `/api/v1/auth/company/logout` y las cinco de
`/api/v1/users`) no tienen objeto alcanzable: se declaran una a una con el actor
leído de `fastapi_users/router/users.py` del paquete instalado, donde `/me` usa
`current_user(active=True)` y `/{id}` añade `superuser=True` —el mismo
`is_superuser` que exige `current_admin_user`. Una dependencia `current_*` o
`require_*` no reconocida hace fallar el script, en vez de contarse como pública.

**El recuento cuadra con §2 del plan.** 127 handlers de `app/routes` + 23 vistas
= **150 exactos**, que es lo que cuenta el plan. Los otros 25 que la app registra
de verdad —18 de fastapi-users, 4 de FastAPI, 3 de `app/app.py`— el plan no los
contaba y también hay que decidirlos: un endpoint generado por una librería se
sirve igual que uno propio.

**Cobertura completa, comprobada y no afirmada.** El script falla si un handler
no tiene decisión o si una decisión apunta a un handler inexistente. 175
handlers, 175 decisiones: 138 `rest`, 31 `retire`, 4 `platform`, 2 `internal`. De
los 138 REST, **108 cambian de contrato**; §5.2 tabulaba 19 de esos 108.

**Atribución de consumidores.** 71 exactas, 86 por prefijo, 18 sin consumidor. El
primer matcher daba 18 falsos «sin consumidor» porque solo buscaba la ruta
entera: `admin.js` construye sus 22 URLs desde `const API = '/api/v1/admin'` y
ninguna aparece literal. Ahora se prueban fragmentos del más específico al más
genérico, con suelo en `/api/v1/<recurso>`, y el artefacto guarda cuál coincidió
(`consumer_match_fragment`) para que cada atribución sea comprobable a mano.

Siete hallazgos que el plan no contemplaba, detallados en el informe:

1. `GET /api/v1/auth/register` es una **vista Jinja bajo `/api/v1`** que comparte
   ruta con el `POST` de la API. Cualquier regla de proxy o CSP que trate
   `/api/v1/*` como JSON está equivocada para esa ruta.
2. **Dos contratos para el perfil de la sesión**: `/api/v1/profile` y
   `/api/v1/users/me`. §5.2 manda el primero justo donde ya está el segundo.
   Igual en admin: `/api/v1/users/{id}` exige superuser y duplica
   `/api/v1/admin/users/{user_id}`.
3. **Colecciones duplicadas por su forma de respuesta** (`posts` vs
   `posts/enriched`, `comments` vs `comments/enriched`).
4. **Cinco handlers de posts legacy sin ningún consumidor**, que siguen
   sirviéndose y escribiendo.
5. `GET /api/v1/dashboard/stats` **no lo llama el frontend** —`dashboard.js:14`
   pide `students_dashboard`—; solo lo ejercitan los tests.
6. **El sitemap depende de las plantillas que TASK-059 borra**:
   `_build_sitemap_xml` saca `lastmod` del mtime de `app/templates/*.html` y
   devolvería `None` sin error y sin test que lo note.
7. `POST /auth/jwt/login` y `/auth/jwt/logout` **quedan fuera de `/api/v1`**, que
   es lo único que el proxy Nginx de §1 enruta junto a `/healthz` y `/readyz`.

Validación ejecutada:

```
.venv/bin/python scripts/route_inventory.py
# handlers: 175
# por destino: internal=2, platform=4, rest=138, retire=31
# por tipo:  api=148, asset=4, view=23
# por actor: admin=25, public=25, recruiter=8, recruiter:job_manager=6,
#            recruiter:optional=3, recruiter:owner=4, student=90, student:optional=14

# reejecución: hash idéntico de route_inventory.json y route_inventory.csv

.venv/bin/python -m pytest -p no:cacheprovider
# 429 passed, 61 skipped
```

Muestreo contra el código de cuatro actores declarados, los cuatro correctos:
`PATCH /api/v1/companies/me/applicants/{id}` → `current_company_job_manager_recruiter`
(`companyRoute.py:376`); `GET /api/v1/resources/file` → `current_active_user`
(`resourceRoute.py:44`); `DELETE /api/v1/admin/users/{id}` → `current_admin_user`
(`adminRoute.py:206`); `POST /api/v1/auth/company/register` → sin dependencia de
identidad, público (`companyRoute.py:206`).

**Hallazgo lateral, no corregido aquí.** `.gitignore:25-26` ignora `scripts/` y
`scripts/*` entero, aunque el directorio ya contiene seis scripts versionados
(`create_superuser.py`, `migrate_sqlite_to_postgres.py`, los tres `seed_*` y
`test_embedding.py`) y tres que no lo están
(`evaluate_resume_skill_extraction.py`, `seed_capstone_analytics.py`,
`sync_capstone_job_skills.py`). `route_inventory.py` se añadió con `git add -f`,
igual que viven los otros seis. Arreglar la regla es un cambio transversal que
destaparía esos tres archivos y no pertenece a esta ficha: queda como finding
para TASK-029, que consolida configuración.

Límites: la atribución de consumidores cubre `app/templates` y `app/static`;
`none` significa «ningún consumidor en este repositorio» y no prueba ausencia de
clientes externos, por lo que los retiros siguen exigiendo comprobar tráfico real
en TASK-059. Los contratos objetivo son propuestas de esta tarea salvo las 19 que
§5.2 ya fijaba, marcadas como tales en la columna `note`. No se añadió un test que
falle si el artefacto queda desactualizado: la verificación es manual, como pide
la sección Validation, y el check automatizado del contrato pertenece a TASK-043,
que fija OpenAPI en CI. No se renombró ni se tocó ningún handler.

### Estimated Impact

Security: LOW
Performance: LOW
Maintainability: HIGH
Cost: LOW
Risk: LOW

## TASK-035 — Capturar OpenAPI, fixtures y baseline visual de las pantallas actuales

Status: COMPLETED
Priority: HIGH
Phase: PHASE-M0
Category: Testing / Documentation

### Objective

Archivar la evidencia contra la que se medirá la paridad de cada vertical: schema, payloads reales y capturas de las pantallas actuales.

### Problem

Plan 08 §9 exige «paridad funcional y visual» por vertical y §13 pide comparación visual de cada pantalla migrada, pero no existe ninguna captura ni fixture archivada. Sin baseline, «se ve igual» es una opinión.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:318-320, 351-353, 445-451` (Confidence: HIGH).
- 27 templates Jinja y 23 archivos JS sin fixtures de referencia (`app/templates/`, `app/static/js/`).

### Why this is a problem

La paridad se declara comparando contra algo. Si la baseline se captura después de empezar a migrar, mide el estado intermedio y deja de servir.

### Desired State

Un directorio versionado con el OpenAPI actual, fixtures JSON por endpoint relevante y capturas desktop/mobile de las pantallas, todo reproducible con un comando.

### Proposed Solution

Exportar el OpenAPI actual como artefacto. Capturar payloads reales por endpoint desde la suite aislada, con datos sintéticos y sin secretos ni PII. Tomar capturas desktop y mobile de las pantallas con el backend aislado, usando la lane de navegador existente. Todo bajo un comando reejecutable; las imágenes se versionan o se publican como artefacto de CI según tamaño, decidido y documentado.

### Scope

IN SCOPE:

- Exportación de OpenAPI; fixtures JSON; capturas por pantalla; comando reproducible.
- Documentar qué pantalla corresponde a qué vertical de §8.

OUT OF SCOPE:

- Cambiar payloads o pantallas para que la captura salga mejor.
- Capturar datos reales de producción o cualquier PII.
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `scripts/`, `docs/refactor/baseline/` (o artefacto de CI equivalente), `tests/` de navegador.
- Sin cambios en `app/`.

### Dependencies

Depends on: TASK-034

### Blocks

Blocks: TASK-037, TASK-046

### Parallelization

Can run in parallel with: TASK-036

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [x] OpenAPI actual archivado como artefacto reproducible.
- [x] Fixtures por endpoint relevante, con datos sintéticos y sin secretos ni PII.
- [x] Capturas desktop y mobile de cada pantalla, asociadas a su vertical.
- [x] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [x] Relevant tests pass.
- [x] No unrelated refactor was introduced.

### Validation

Reejecutar la captura y comprobar que produce el mismo conjunto. Verificar que ninguna fixture contiene credenciales, tokens ni datos personales. Comprobar que cada pantalla del inventario de TASK-034 tiene su captura o una razón registrada para no tenerla.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Completion Notes

Ningún archivo de `app/` cambia. La baseline se captura ejecutando la aplicación
real, no describiéndola.

**Un comando.** `scripts/capture_baseline.py` siembra una SQLite desechable con
datos sintéticos, exporta el OpenAPI, recorre los endpoints GET del inventario
de TASK-034 archivando el payload de cada uno, levanta la app en uvicorn sobre
loopback y fotografía las 22 pantallas en desktop y mobile con Playwright.
`--skip-screens` corta la parte del navegador. La salida vive en
`docs/refactor/baseline/`, con [README.md](baseline/README.md) escrito a mano y
`MANIFEST.md` regenerado.

**Reproducible de verdad, no «se puede volver a correr».** El reloj
(`2026-01-05T12:00:00`) y el namespace de UUID son fijos, así que los ids y las
fechas son función del código. Dos ejecuciones completas seguidas producen
`openapi.json`, las 59 fixtures, `manifest.json` y `MANIFEST.md` byte a byte
idénticos —comprobado con sha256— incluidos los PNG. Los ids sintéticos llevan
forzados los bits de versión 4 porque varios schemas declaran `UUID4`: con un
uuid5 puro la fixture mediría la semilla y no el endpoint.

**Aislamiento, no promesa de aislamiento.** El script reusa
`tests/isolation.apply_isolation()`. Durante la captura el guard bloqueó de
hecho dos salidas a S3 desde las rutas de descarga de CV; esas dos quedaron sin
fixture con su razón registrada, en vez de archivar el fallo del entorno como si
fuera el contrato. El comando termina revisando las fixtures contra patrones de
JWT, `Set-Cookie`, hashes de contraseña, claves de proveedor y correos fuera de
la semilla, y falla sin escribir el manifiesto si encuentra algo.

**Decisión sobre las imágenes (§Proposed Solution la exigía explícita).** Una
captura completa son 44 PNG y ~18 MB. La baseline se reejecuta una vez por
vertical, ocho verticales: versionarlos añadiría del orden de 150 MB de binarios
irreversibles al historial. **No se versionan**: `screens/` entra en
`.gitignore` y el job `baseline` de `.github/workflows/tests.yml` los publica
como artefacto con 30 días de retención. Se versiona el manifiesto, el OpenAPI y
las fixtures (644 KB en total). Los sha256 de los PNG van en
`screens/index.json`, junto a ellos, para no ensuciar un fichero versionado en
cada captura.

**Cobertura contra el inventario de TASK-034.** Las 23 rutas de vista tienen
captura salvo `/roadmap`, que es una redirección 307 a `/roadmaps` y no renderiza
pantalla propia; queda registrada como tal. Cada pantalla y cada fixture lleva su
vertical (`V1-TASK-046` … `V8-TASK-053`) leída del inventario, no de una lista
paralela escrita a mano aquí. De los 65 handlers GET de API, 59 tienen fixture y
6 tienen razón: `/favicon.ico`, `/robots.txt` y `/sitemap.xml` no describen
ninguna pantalla; las dos descargas de CV y
`/api/v1/profile/cv/{resume_id}/similar` no son capturables en este entorno.

Validación ejecutada:

```
.venv/bin/python scripts/capture_baseline.py
# openapi: 144 paths
# fixtures: 59 capturadas, 6 con razón registrada
# screens:  44 capturas (22 pantallas x 2 viewports), todas HTTP 200
# revisión de secretos/PII: sin hallazgos

# reejecución completa: sha256 idéntico de openapi.json, manifest.json,
# MANIFEST.md, las 59 fixtures y los 44 PNG

.venv/bin/python -m pytest -p no:cacheprovider
# 429 passed, 61 skipped
```

**Hallazgo, no corregido aquí.** `GET /api/v1/admin/companies` responde 500
siempre que exista al menos una empresa: `app/routes/adminRoute.py:532` lee
`c.email` y `Company` no tiene esa columna (`app/models/companyModel.py:17-24`).
La fixture archiva el 500 porque es el comportamiento actual; corregirlo es un
Bug Fix rotulado de TASK-053, que es la vertical de admin. Esta tarea captura, no
arregla.

Límites, todos registrados en `manifest.json` y en el README de la carpeta. El
navegador solo puede hablar con el servidor local, así que `/questionnaire` se
captura **sin estilos**: toda su presentación viene de `cdn.tailwindcss.com` en
tiempo de ejecución, lo que es en sí un hallazgo para TASK-047; `/admin` y
`/admin/login` pierden la tipografía Inter que `admin.css` importa de Google
Fonts, pero conservan estructura y color. La comparación sigue siendo válida
porque legacy y React se capturarán con el mismo bloqueo. La baseline corre sobre
SQLite, que no es PostgreSQL: el endpoint pgvector no se puede capturar. Las
fixtures cubren GET; el contrato de las mutaciones lo fija TASK-043 en CI, que es
donde corresponde. No se añadió un test que falle si el artefacto queda
desactualizado: la sección Validation pide reejecutar y comparar, y el gate
automatizado del contrato es de TASK-043.

`scripts/` sigue ignorado en `.gitignore` —el hallazgo lateral que TASK-034 dejó
para TASK-029—, así que `capture_baseline.py` se añadió con `git add -f`, igual
que los otros siete scripts versionados.

### Estimated Impact

Security: MEDIUM
Performance: LOW
Maintainability: HIGH
Cost: LOW
Risk: LOW

## TASK-036 — Decidir y registrar el patrón de ingreso a Cloud Run

Status: COMPLETED
Priority: HIGH
Phase: PHASE-M0
Category: Infrastructure / Security / ADR

### Objective

Cerrar por ADR si la API queda invocable sin autenticación IAM detrás del proxy Nginx, o si se sustituye por un Load Balancer con serverless NEGs.

### Problem

Plan 08 §3 deja la decisión explícitamente abierta y advierte que el proxy Nginx simple no basta si se exige IAM: haría falta un HTTPS LB con serverless NEGs y routing `/api/*`, o un proxy capaz de emitir identity tokens. §14 lista «API directa elude Nginx» como riesgo vivo.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:70-77` (Confidence: HIGH).
- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:466` (riesgo de ingreso directo).

### Why this is a problem

La decisión cambia el coste, la topología de despliegue y qué barreras de seguridad son reales. Tomarla implícitamente al escribir el primer Terraform o el primer workflow la vuelve difícil de revisar.

### Desired State

Un ADR versionado con la opción elegida, su coste, sus implicaciones de seguridad y qué controles quedan como únicos guardianes de los recursos privados.

### Proposed Solution

Escribir el ADR comparando ambas opciones sobre criterios explícitos: coste mensual, complejidad operativa, superficie expuesta y qué ocurre si alguien llama la URL de la API directamente. Dejar constancia de que auth de aplicación, CSRF y rate limits viven en FastAPI en cualquiera de los dos casos, porque IAM no los sustituye. La decisión es un gate: TASK-055 y TASK-056 la implementan, no la re-deciden.

### Scope

IN SCOPE:

- ADR versionado bajo `docs/refactor/`; criterios, coste estimado e implicaciones de seguridad.
- Registro de qué controles siguen siendo responsabilidad de la aplicación.

OUT OF SCOPE:

- Implementar la infraestructura elegida: eso es TASK-055 y TASK-056.
- Aprovisionar recursos en Google Cloud o gastar presupuesto.
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `docs/refactor/` (ADR nuevo).
- Sin cambios de código.

### Dependencies

Depends on: NONE

### Blocks

Blocks: TASK-055

### Parallelization

Can run in parallel with: TASK-033, TASK-034, TASK-035

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [x] El ADR nombra la opción elegida y por qué, con coste e implicaciones de seguridad.
- [x] Queda escrito qué controles de seguridad viven en la aplicación en ambos escenarios.
- [x] La decisión está aprobada antes de que TASK-055 aprovisione nada.
- [x] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [x] Relevant tests pass.
- [x] No unrelated refactor was introduced.

### Validation

Revisión del ADR por quien opera la infraestructura. No hay validación automatizada: es una decisión documentada. Si la aprobación no está disponible, registrar BLOCKED con la evidencia pendiente.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Completion Notes

Entrega [ADR-001-cloud-run-ingress.md](ADR-001-cloud-run-ingress.md). Sin cambios
de código.

**Decisión: opción A** — la API queda invocable sin autenticación IAM, detrás del
proxy Nginx del servicio frontend. Aprobada por el propietario del proyecto el
2026-09-07, que es quien opera la infraestructura; la Validation de esta ficha
pedía justamente esa revisión.

El razonamiento, resumido: IAM no sustituye ninguno de los controles que de
verdad protegen los recursos privados —sesión, CSRF, rate limits y ownership
viven en FastAPI en las dos opciones—, el coste de la opción B es fijo (~$18–25
al mes de forwarding rule y backend services, con independencia del uso) frente a
~$0, y migrar a B más adelante no toca el código de la aplicación, solo la
topología. Decidir A no cierra esa puerta.

**Lo que se acepta explícitamente.** El riesgo «API directa elude Nginx» de §14
queda vivo y aceptado, no mitigado. El ADR lo escribe en esos términos y saca las
consecuencias concretas: ninguna decisión de autorización puede depender de que
el proxy haya pasado por delante; los dos endpoints que
[09_ROUTE_MATRIX.md](09_ROUTE_MATRIX.md) clasifica como `internal` necesitan
autenticación propia y no la suposición de que nadie los encontrará; el endpoint
de Cloud Tasks de TASK-054 exige OIDC verificado en la aplicación porque su URL
será alcanzable desde internet; y `/docs`, `/redoc` y `/openapi.json` quedan
alcanzables por el `run.app`, así que exponerlos o no es una decisión de TASK-056
y no algo que la topología impida.

**Consecuencia que casi se queda implícita: `TRUSTED_PROXY_IPS`.** Todos los
límites por IP se resuelven por `resolve_client_ip()`, que depende de ese ajuste;
hoy vale `private` y lo fija el `Dockerfile`. Con dos servicios la cadena
`X-Forwarded-For` que ve la API es más larga y el peer inmediato cambia, y además
una llamada directa al `run.app` llega por un camino distinto que una que pasa
por el frontend. Demasiado amplio, un cliente directo se inventa su
`X-Forwarded-For` y estrena bucket de rate limit por petición —anulando el
control que esta misma ADR pone como guardián principal—; demasiado estrecho,
todos los clientes cuentan como la IP del frontend y el límite por IP se vuelve
global. El ADR deja como obligación de TASK-056 comprobarlo empíricamente contra
el despliegue real, en los dos caminos, antes de servir tráfico. Es la única
parte de la decisión que no se puede cerrar sobre el papel.

El ADR registra también las condiciones que reabrirían la decisión hacia la
opción B: un requisito de cumplimiento, un incidente de abuso que los rate limits
no contengan, necesidad de WAF/Cloud Armor, o un tercer servicio que deba hablar
con la API sin pasar por el frontend.

Validación: no hay validación automatizada; es una decisión documentada, como
dice la sección Validation. La suite no se toca —ningún archivo de `app/` cambia—
y la última ejecución sigue siendo la de TASK-034: 429 passed, 61 skipped.

Límites: el ADR no aprovisiona nada ni estima tráfico. Las cifras de coste de la
opción B son el orden de magnitud del precio de lista de un HTTPS Load Balancer
con serverless NEGs, suficientes para comparar, no un presupuesto. TASK-055 y
TASK-056 implementan esta decisión y no la re-deciden.

### Estimated Impact

Security: HIGH
Performance: LOW
Maintainability: MEDIUM
Cost: HIGH
Risk: MEDIUM

## TASK-037 — Mover el backend a backend/ sin cambiar comportamiento

Status: COMPLETED
Priority: HIGH
Phase: PHASE-M1
Category: Refactor / Structure

### Objective

Reubicar el código Python bajo `backend/` con `git mv`, en un PR puramente mecánico que no altera comportamiento.

### Problem

El repositorio tiene el backend en la raíz (`app/`, `alembic/`, `tests/`, `main.py`), incompatible con el layout de monorepo de §4, que separa `backend/` y `frontend/` con Dockerfile y CI propios.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:78-118` (layout objetivo, Confidence: HIGH).
- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:114-118`: el movimiento debe hacerse con `git mv` y sin refactorizar imports o comportamiento en el mismo PR.
- Raíz actual: `app/`, `alembic/`, `alembic.ini`, `tests/`, `main.py`, `pyproject.toml`, `requirements.txt`, `pytest.ini`, `Dockerfile`.

### Why this is a problem

Mezclar el movimiento con cambios de arquitectura interna hace ilegible el diff y vuelve imposible atribuir una regresión al movimiento o al refactor.

### Desired State

El mismo código, en `backend/`, pasando exactamente la misma suite con los mismos conteos, sin un solo cambio de lógica.

### Proposed Solution

Un PR con `git mv` y solo los ajustes de ruta imprescindibles: `alembic.ini` (`script_location`), `pytest.ini`, `Dockerfile`, workflows y cualquier ruta relativa que la suite use. No tocar imports internos, no reorganizar `app/`, no renombrar módulos. Preservar el historial: verificar que `git log --follow` sigue funcionando sobre archivos movidos. Las claves de storage y los IDs no cambian (§12).

### Scope

IN SCOPE:

- `git mv` de `app/`, `alembic/`, `tests/`, `main.py`, `scripts/`, configuración Python y `Dockerfile`.
- Ajuste de rutas en configuración y CI, estrictamente el mínimo para que la suite corra.

OUT OF SCOPE:

- Reorganizar `app/` en `api/v1`, `repositories`, etc.: eso ocurre por vertical.
- Cambiar imports, renombrar módulos o tocar comportamiento en este PR.
- Cambiar IDs o claves de storage al mover carpetas.
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- Todo el árbol Python movido bajo `backend/`; `alembic.ini`, `pytest.ini`, `Dockerfile`, workflows.
- Sin cambios de lógica en ningún módulo.

### Dependencies

Depends on: TASK-033, TASK-035

### Blocks

Blocks: TASK-038, TASK-039, TASK-040, TASK-041, TASK-042, TASK-045, TASK-054

### Parallelization

Can run in parallel with: TASK-036

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [x] El backend vive bajo `backend/` y la suite pasa con los mismos conteos que la baseline de TASK-033.
- [x] El diff no contiene cambios de lógica: solo movimientos y ajustes de ruta.
- [x] `git log --follow` sigue el historial de los archivos movidos.
- [x] Ninguna clave de storage ni ID cambió como efecto del movimiento.
- [x] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [x] Relevant tests pass.
- [x] No unrelated refactor was introduced.

### Completion Notes

Movimiento mecánico: 360 ficheros renombrados con `git mv`, de los cuales **358
son renombres puros** —ni un byte de contenido cambia en `app/`, `tests/`,
`alembic/`, `main.py`, `Dockerfile`, `pytest.ini` ni `pyproject.toml`—. El diff
de contenido se limita a dos ficheros y a configuración y documentación.

**Los dos scripts que sí cambian.** `scripts/route_inventory.py` y
`scripts/capture_baseline.py` usaban `parent.parent` para dos cosas a la vez:
como raíz de importación de `app` y como raíz desde la que escribir en
`docs/refactor/`. Tras el movimiento esas dos raíces dejan de coincidir, porque
`docs/` documenta el monorepo entero y se queda arriba. Ahora declaran
`BACKEND_ROOT` y `REPO_ROOT` por separado. Es el ajuste de ruta que la ficha
autoriza, no un refactor.

**Regresión de `.gitignore` detectada y corregida.** `app/credentials/` lleva
barra interna, así que git ancla el patrón al directorio del propio
`.gitignore`: tras mover el árbol habría dejado de cubrir
`backend/app/credentials/` y unas credenciales podrían haberse commiteado sin
aviso. Reanclado y verificado con `git check-ignore -v`. El caso contrario
también se comprobó: `scripts/` no lleva barra interna, sigue cubriendo
`backend/scripts/` y por eso esos ficheros siguen necesitando `git add -f`,
exactamente como antes del movimiento.

**Dónde corre ahora.** Desde `backend/`. No es una preferencia: `pytest.ini`
declara `testpaths = tests` y algún módulo resuelve rutas contra el directorio
de trabajo —`questionnaireService.py` abre `app/data/questionnaires/v1/v2.json`
como ruta relativa—. CI declara `working-directory: backend` en las cuatro
lanes; la subida de artefactos no lleva ese default porque no es un paso `run`
y su ruta sigue siendo la raíz del repo. El entorno virtual se queda arriba
mientras el monorepo tenga un solo lenguaje instalado, así que el intérprete
documentado es `../.venv/bin/python`; TASK-038 y TASK-039 fijarán la forma
definitiva al añadir el compose y separar las lanes.

El `.env` local se movió junto al código: `app/app.py` lo resuelve como
`parents[1]/.env`, así que moverlo mantiene la resolución intacta sin tocar el
módulo. `.env` no lleva barra en `.gitignore` y sigue ignorado en su nueva
ubicación.

**Qué demuestra que no cambió el comportamiento.** Tres pruebas independientes:

| Prueba | Antes | Después |
| --- | --- | --- |
| Lane rápida | 429 passed, 61 skipped | 429 passed, 61 skipped |
| Lane PostgreSQL + Redis | 61 passed | 61 passed |
| Lane navegador | 14 passed, 476 deselected | 14 passed, 476 deselected |
| Baseline TASK-035 | `openapi.json` + 59 fixtures | byte a byte idénticos |
| Imagen Docker | — | construye, arranca, sirve los mismos 144 paths |

Las fixtures idénticas son la evidencia de que ningún id ni clave de storage
cambió como efecto del movimiento: se generan a partir de payloads reales de la
aplicación levantada. Lo único que cambia en los artefactos regenerados es el
campo `generated_by`, que ahora es relativo a la raíz del repositorio para que
no quede ambiguo a qué `scripts/` se refiere.

`git log --follow` sigue el historial a través del movimiento:
`backend/app/app.py` conserva sus 38 commits hasta el primero del repositorio.

**Documentación.** `docs/TESTING.md` gana una sección «Dónde se ejecutan»;
`docs/DATABASE_CONFIG.md`, `docs/refactor/09_ROUTE_MATRIX.md` y
`docs/refactor/baseline/README.md` actualizan sus comandos.
`PROJECT_STRUCTURE.md` lleva una nota de layout en vez de una reescritura: su
árbol y sus descripciones siguen siendo exactos leyendo cada ruta con
`backend/` delante, y reescribirlo entero ahora sería adelantar la
reorganización interna de `app/`, que ocurre por vertical y no aquí.

**No incluido, deliberadamente.** No se reorganizó `app/` en `api/v1`,
`repositories`, etc.; no se tocó ningún import interno; no se renombró ningún
módulo. `docs/`, `.github/` y `.nvmrc` se quedan en la raíz porque son del
monorepo, no del backend.

**Hallazgo registrado, no corregido aquí.** `questionnaireService.py:12` fija
`QUESTIONNAIRE_PATH = Path("app/data/questionnaires/v1/v2.json")`, una ruta
relativa al directorio de trabajo del proceso. Funciona en la imagen porque el
`Dockerfile` fija `WORKDIR /app` y copia `app` dentro, y funciona en la suite
porque ahora corre desde `backend/`, pero ata el arranque al `cwd` en vez de al
módulo. Es un cambio de comportamiento potencial y por tanto queda fuera de
esta ficha; le corresponde a la vertical que toque el cuestionario (TASK-047).

### Validation

Ejecutar suite rápida y lane PostgreSQL/Redis antes y después del movimiento y comparar conteos exactos. Revisar el diff completo confirmando que no hay cambios de comportamiento. Construir la imagen Docker desde la nueva ubicación y arrancar la app.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: LOW
Performance: LOW
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM

## TASK-038 — Crear el scaffold React y el compose local con proxy same-origin

Status: TODO
Priority: HIGH
Phase: PHASE-M1
Category: Frontend / Infrastructure

### Objective

Levantar `frontend/` (React + TypeScript + Vite + Nginx) y un `docker-compose.yml` que reproduzca localmente la topología de producción.

### Problem

No existe frontend React: el producto se sirve desde 27 templates Jinja y 23 archivos JS. Tampoco hay compose local equivalente a producción (§2), así que nadie puede probar el patrón de un solo origen antes de desplegarlo.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:38-40, 88-104, 245-293` (Confidence: HIGH).
- Repositorio sin `frontend/`, `package.json`, `vite.config.ts` ni `docker-compose.yml`.

### Why this is a problem

Si el frontend nace sin proxy same-origin, cookies, CSRF y navegación se diseñan contra CORS cross-site y hay que rehacerlos al desplegar.

### Desired State

Un `npm run dev` y un `docker compose up` que sirvan la SPA y proxeen `/api`, `/healthz` y `/readyz` al backend, con el navegador viendo un solo origen.

### Proposed Solution

Scaffold con el stack de §7 (React 19, TypeScript estricto, Vite, React Router, TanStack Query, React Hook Form + Zod, Vitest + Testing Library) y la estructura de carpetas de §7. `nginx.conf` proxea `/api`, `/healthz` y `/readyz`; `API_ORIGIN` se inyecta en Nginx, nunca en el bundle (§11). Compose con `migrate`, `api`, `worker` local y `web`. Elegir **una** estrategia de estilos y dejarla escrita: no convivir indefinidamente con 23 hojas CSS por pantalla. Una sola página de humo; las pantallas reales llegan por vertical.

### Scope

IN SCOPE:

- `frontend/` completo (scaffold, Dockerfile, nginx.conf, package.json, vite.config.ts), `docker-compose.yml`.
- Decisión escrita de estrategia de estilos e i18n.

OUT OF SCOPE:

- Migrar cualquier pantalla real: eso es TASK-046 en adelante.
- Incluir secretos en la imagen del frontend o en el bundle.
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `frontend/**`, `docker-compose.yml`, documentación de arranque local.
- Sin cambios en el backend salvo lo que el compose necesite para arrancar.

### Dependencies

Depends on: TASK-037

### Blocks

Blocks: TASK-039, TASK-044

### Parallelization

Can run in parallel with: TASK-036

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] `docker compose up` levanta migrate, api, worker y web, y el navegador ve un solo origen.
- [ ] El frontend hace lint, typecheck, test y build en limpio.
- [ ] El bundle no contiene secretos; `API_ORIGIN` se resuelve en Nginx.
- [ ] La estrategia de estilos e i18n está elegida y escrita, no pendiente.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Smoke local a través de Nginx: cargar la SPA y comprobar en el navegador que una llamada a `/api` sale al mismo origen, revisando requests y DOM, no solo el contenido de los archivos. Ejecutar lint, `tsc --noEmit`, Vitest y build. Verificar que la imagen del frontend no contiene secretos.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: MEDIUM
Performance: LOW
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM

## TASK-039 — Separar CI en lanes de backend y frontend

Status: TODO
Priority: HIGH
Phase: PHASE-M1
Category: Infrastructure / Testing

### Objective

Dejar `ci.yml` cubriendo backend y frontend por separado, con las lanes que describe §10.

### Problem

La CI actual cubre Python, PostgreSQL/Redis y navegador, pero no existe pipeline de frontend ni de despliegue (§2). Un monorepo con dos aplicaciones necesita que cada una falle por su cuenta.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:41-42, 383-395` (Confidence: HIGH).
- Workflows actuales bajo `.github/workflows/`.

### Why this is a problem

Sin lane de frontend, un error de tipos o un bundle roto llega a producción sin que nada lo detecte; y sin export de OpenAPI en CI no hay cómo comparar contratos.

### Desired State

CI que ejecuta backend (lock verificado, lint, tests rápidos, integración PostgreSQL/pgvector + Redis, export de OpenAPI) y frontend (install limpio, lint, typecheck, tests, build) en jobs separados.

### Proposed Solution

Reescribir `ci.yml` con jobs independientes y caché por lane. Backend: instalación desde lock con verificación de que el lock está al día, Ruff, pytest rápido, lane de integración y export de OpenAPI como artefacto. Frontend: `npm ci`, lint, `tsc --noEmit`, Vitest, validación de i18n y build. Añadir escaneo de secretos y dependencias. No imprimir variables sensibles en los logs.

### Scope

IN SCOPE:

- `.github/workflows/ci.yml` y configuración de lint/format que la CI necesite.
- Artefacto de OpenAPI publicado por CI.

OUT OF SCOPE:

- `deploy.yml` y cualquier credencial de nube: eso es TASK-055 y TASK-056.
- E2E con Playwright: llega con las verticales.
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `.github/workflows/ci.yml`, configuración de herramientas de lint/typecheck.
- Sin cambios de comportamiento en la aplicación.

### Dependencies

Depends on: TASK-037, TASK-038

### Blocks

Blocks: TASK-043, TASK-055

### Parallelization

Can run in parallel with: TASK-036

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] Backend y frontend fallan de forma independiente y con mensajes accionables.
- [ ] El lock del backend se verifica; una dependencia añadida sin actualizar el lock rompe CI.
- [ ] CI publica el OpenAPI del SHA como artefacto.
- [ ] Ningún job imprime variables sensibles.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Provocar deliberadamente un fallo en cada lane (test roto, error de tipos, lock desactualizado) y comprobar que CI falla en la lane correcta y no en la otra. Revisar los logs de un run completo buscando fugas de variables sensibles.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: MEDIUM
Performance: LOW
Maintainability: HIGH
Cost: LOW
Risk: LOW

## TASK-040 — Implantar el error model único y el request id en toda la API

Status: TODO
Priority: HIGH
Phase: PHASE-M2
Category: API Contract / Security

### Objective

Que toda respuesta de error de `/api/v1` tenga la forma `{"error":{"code","message","details","request_id"}}`, con códigos estables y sin texto de excepción.

### Problem

§5.1 fija un error único y prohíbe devolver `str(exception)`. TASK-011 normalizó los errores de un subconjunto de rutas y TASK-032 quedó pendiente de extenderlo al resto; ninguna de las dos introduce `code` estable ni `request_id`, que es lo que el cliente React necesita para decidir sin parsear prosa.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:128-131, 236-240` (Confidence: HIGH).
- TASK-011 (COMPLETED) y TASK-032 (pendiente) en este documento.
- F-10 en [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md): errores de infraestructura retornados al cliente.

### Why this is a problem

Sin código estable, el frontend distingue errores por el texto del mensaje, que es traducible y cambia; sin `request_id`, un fallo reportado por un usuario no se puede correlacionar con el log que lo explica.

### Desired State

Un handler de errores central, un catálogo de códigos estables versionado, y un `request_id` propagado desde el middleware hasta el log y la respuesta.

### Proposed Solution

Absorber TASK-032 dentro de esta tarea: extender el mapeo a las rutas restantes ya con la forma final, en vez de normalizar dos veces. Middleware que genera o propaga `request_id` y lo pone en el log estructurado y en la respuesta. Catálogo de códigos como enum versionado, no strings sueltos. Los detalles de validación van en `details`; nunca se filtra `str(exception)` ni rastro de infraestructura. Mantener el shape actual como adapter donde un consumidor legacy todavía lo lea.

### Scope

IN SCOPE:

- Handler de errores central, middleware de request id, catálogo de códigos, mapeo de las rutas restantes.
- Tests de contrato de error por familia de status.

OUT OF SCOPE:

- Cambiar qué operaciones fallan o con qué status: solo cambia la forma de la respuesta.
- Traducir mensajes: la UI decide el idioma a partir del código.
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `backend/app/core/` (errores, middleware), routers de `backend/app/`, tests de contrato.
- Consumidores legacy que lean el shape anterior, mediante adapter.

### Dependencies

Depends on: TASK-032, TASK-037

### Blocks

Blocks: TASK-043, TASK-044

### Parallelization

Can run in parallel with: TASK-041, TASK-042, TASK-045

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] Toda respuesta de error de `/api/v1` tiene la forma única, con código estable y `request_id`.
- [ ] Ninguna respuesta contiene `str(exception)` ni detalle de infraestructura.
- [ ] El `request_id` de la respuesta aparece en el log estructurado de esa misma petición.
- [ ] TASK-032 queda cubierta: no quedan rutas con el mapeo anterior sin adapter declarado.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Test de contrato por cada familia de status (400/401/403/404/409/422/429/5xx) comprobando forma, código y ausencia de texto de excepción. Inyectar un fallo de infraestructura y verificar que el cliente recibe un mensaje seguro mientras el log conserva el detalle con el mismo `request_id`.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: HIGH
Performance: LOW
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM

## TASK-041 — Estandarizar paginación, límites de colección e idempotencia

Status: TODO
Priority: HIGH
Phase: PHASE-M2
Category: API Contract / Performance

### Objective

Dar a toda colección un límite máximo de servidor y una forma de paginación declarada, y exigir `Idempotency-Key` donde una repetición cuesta dinero o crea duplicados.

### Problem

§5.1 exige `{items, page, page_size, total}` para colecciones paginadas, cursor en mensajes y feed, límite máximo en toda colección, e `Idempotency-Key` en candidaturas, uploads que disparan IA y creación de jobs. Hoy los listados cargan historial completo (F-22) y no existe cabecera de idempotencia.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:132-138` (Confidence: HIGH).
- F-22 en [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md); TASK-024 y TASK-025 en este documento.

### Why this is a problem

Una colección sin límite de servidor es una denegación de servicio latente, y un reintento de red sobre un upload que dispara IA gasta cuota dos veces por la misma intención del usuario.

### Desired State

Helpers compartidos de paginación por página y por cursor, un límite máximo que el cliente no puede exceder, y un registro de idempotencia que devuelva el mismo resultado ante la misma clave.

### Proposed Solution

Construir sobre el cursor estable de TASK-024 en vez de inventar otro. Helpers compartidos para ambas formas de paginación, con `page_size` acotado en servidor. Registro de idempotencia persistido y con retención definida: misma clave y mismo actor devuelven el resultado original; misma clave con cuerpo distinto es `409`. Aplicarlo primero a candidaturas, uploads con IA y creación de jobs, que es donde el plan lo exige. No convertir toda la API en idempotente por defecto.

### Scope

IN SCOPE:

- Helpers de paginación, límites de servidor, registro de idempotencia y su migración si persiste en DB.
- Aplicación a candidaturas, uploads que disparan IA y creación de jobs.

OUT OF SCOPE:

- Cambiar el orden o la semántica de los listados existentes más allá de acotarlos.
- Hacer idempotentes operaciones donde repetir es semánticamente correcto.
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `backend/app/core/` o `schemas/` (helpers), routers de colecciones, migración del registro de idempotencia.
- Tests de paginación, límites y replay.

### Dependencies

Depends on: TASK-024, TASK-037

### Blocks

Blocks: TASK-043, TASK-049

### Parallelization

Can run in parallel with: TASK-040, TASK-042, TASK-045

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] Ninguna colección puede devolver más filas que el límite de servidor, pida el cliente lo que pida.
- [ ] Las colecciones paginadas responden con la forma declarada en §5.1.
- [ ] La misma `Idempotency-Key` con el mismo cuerpo devuelve el resultado original sin volver a gastar IA.
- [ ] La misma clave con cuerpo distinto responde `409`.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Pedir `page_size` por encima del máximo y comprobar que el servidor acota. Replay de una creación con la misma clave verificando que no hay segundo cargo ni fila duplicada, en la lane PostgreSQL con peticiones concurrentes. Medir consultas por página con catálogo representativo.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: MEDIUM
Performance: HIGH
Maintainability: HIGH
Cost: MEDIUM
Risk: MEDIUM

## TASK-042 — Exponer sesión, login y logout por actor con CSRF double-submit

Status: TODO
Priority: CRITICAL
Phase: PHASE-M2
Category: Security / API Contract

### Objective

Añadir `GET /api/v1/auth/session`, endpoints de login/logout consistentes por actor y protección CSRF double-submit en todos los métodos mutantes.

### Problem

§6.2 exige un endpoint que devuelva el actor efectivo y su tipo, CSRF double-submit y rotación de sesión explícita. Hoy hay dos identidades con cookies separadas y ningún endpoint que le diga a un cliente quién es; la SPA no puede decidir su navegación sin adivinar.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:202-215` (Confidence: HIGH).
- TASK-010 (COMPLETED): autenticación de compañías cubierta y proxy confiable validado.
- Dos identidades autenticables con cookies separadas (`docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:39`).

### Why this is a problem

Sin endpoint de sesión, el guard de React inventa el estado de autenticación; sin CSRF, un formulario de otro origen puede ejecutar mutaciones con la cookie del usuario.

### Desired State

Un contrato de sesión explícito por actor, cookies httpOnly `SameSite=Lax` y `Secure` en producción, y un token CSRF que el cliente reenvía en `X-CSRF-Token` y el backend valida junto con `Origin`.

### Proposed Solution

Conservar cookies separadas para estudiante y recruiter: mezclar modelos de identidad durante la migración es un riesgo que el plan pide no correr. `GET /auth/session` devuelve actor y tipo, o `401` limpio. CSRF double-submit más validación de `Origin`. Rotación de sesión explícita; el cliente reintenta un `401` una sola vez. La autorización se decide en backend: los guards de React solo controlan navegación y nunca son la barrera.

### Scope

IN SCOPE:

- Endpoints de sesión/login/logout por actor, emisión y validación de token CSRF, rotación de sesión.
- Tests de CSRF, de actor cruzado y de expiración.

OUT OF SCOPE:

- Unificar las dos identidades en un solo modelo de usuario.
- Cambiar el proveedor de autenticación o el esquema de contraseñas.
- Tratar CORS como barrera de seguridad.
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `backend/app/` rutas y dependencias de auth, middleware CSRF, configuración de cookies.
- Tests de seguridad propios.

### Dependencies

Depends on: TASK-010, TASK-037

### Blocks

Blocks: TASK-044, TASK-046

### Parallelization

Can run in parallel with: TASK-040, TASK-041, TASK-045

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] `GET /auth/session` devuelve el actor efectivo y su tipo, o `401` sin filtrar existencia de cuentas.
- [ ] Todo método mutante exige token CSRF válido; sin él responde `403`.
- [ ] Las cookies son httpOnly, `SameSite=Lax` y `Secure` en producción.
- [ ] Un actor no puede operar sobre recursos del otro tipo de identidad.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Casos negativos y positivos: mutación sin token, con token de otra sesión, con `Origin` ajeno y tras rotación. Verificar en la lane de navegador, a través del proxy, que la cookie viaja same-origin y que el cliente reintenta un `401` exactamente una vez. Comprobar que el `403` no distingue entre «no autenticado» y «no autorizado» más de lo que el contrato declara.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: HIGH
Performance: LOW
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM

## TASK-043 — Fijar OpenAPI como contrato y generar tipos TypeScript en CI

Status: TODO
Priority: HIGH
Phase: PHASE-M2
Category: API Contract / Infrastructure

### Objective

Hacer del schema OpenAPI la fuente de verdad del contrato, con tipos TypeScript generados y un diff incompatible que rompe CI.

### Problem

§5.1 declara OpenAPI como fuente de verdad y exige que CI exporte el schema, genere o verifique los tipos y falle ante un diff incompatible salvo cambio versionado. Hoy no existe ni la generación ni la comparación.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:139-140, 386-391` (Confidence: HIGH).
- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:462` (riesgo: contrato cambia sin detectar).

### Why this is a problem

Si el frontend escribe sus propios tipos a mano, un cambio de backend rompe la SPA en producción en vez de en CI, y el contrato deja de ser verificable.

### Desired State

Tipos generados desde el OpenAPI del mismo SHA, consumidos por el cliente HTTP, y un check de compatibilidad que distingue un cambio aditivo de uno que rompe.

### Proposed Solution

Estabilizar `operationId` y nombres de schema antes de generar, o los tipos cambiarán de nombre en cada build. Generar tipos en `frontend/src/api/generated/` como artefacto reproducible, no editado a mano. Comparar el OpenAPI del PR contra el de la rama base y fallar ante cambios incompatibles; un cambio deliberado se acompaña de versión o de deprecación explícita según §5.3.

### Scope

IN SCOPE:

- Export estable de OpenAPI, generación de tipos, check de compatibilidad en CI.
- Estabilización de `operationId` y nombres de schema.

OUT OF SCOPE:

- Renombrar endpoints: eso ocurre en cada vertical siguiendo la matriz de TASK-034.
- Publicar el OpenAPI públicamente en producción sin decidirlo (§6.4).
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `.github/workflows/ci.yml`, `backend/app/` (metadatos de OpenAPI), `frontend/src/api/generated/`.
- Script de generación y comparación.

### Dependencies

Depends on: TASK-039, TASK-040, TASK-041

### Blocks

Blocks: TASK-044

### Parallelization

Can run in parallel with: TASK-042, TASK-045

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] Los tipos del frontend se generan desde el OpenAPI del mismo SHA y no se editan a mano.
- [ ] Un cambio incompatible de contrato rompe CI; uno aditivo, no.
- [ ] Los `operationId` son estables entre builds sin cambios de código.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Introducir a propósito un cambio incompatible (campo requerido eliminado, enum reducido) y comprobar que CI falla; introducir uno aditivo y comprobar que pasa. Regenerar los tipos dos veces sin cambios y verificar que el resultado es idéntico.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: LOW
Performance: LOW
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM

## TASK-044 — Construir la capa HTTP, los shells y los guards del frontend

Status: TODO
Priority: HIGH
Phase: PHASE-M2
Category: Frontend

### Objective

Dejar lista la base sobre la que se monta cada vertical: cliente HTTP único, tokens de diseño, shells por actor, router, guards y boundaries.

### Problem

§7 fija que ningún componente llama `fetch` directamente, que la lógica de red vive en hooks de feature y que los datos remotos no se duplican en stores globales. Sin esa base, la primera vertical improvisa y las siete siguientes copian la improvisación.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:245-293` (Confidence: HIGH).
- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:341-344` (entregables de Fase 2).

### Why this is a problem

La capa HTTP concentra credenciales, CSRF, reintento acotado, `ApiError` y `request_id`. Repartirla entre componentes es exactamente el problema que F-19 describe en el JS actual.

### Desired State

`client.ts` como único punto de red, `queryKeys.ts` como convención de cache, shells `Public/Student/Company/Admin`, guards de navegación y boundaries de carga y error.

### Proposed Solution

Cliente con credenciales, `X-CSRF-Token`, un solo reintento ante `401`, `ApiError` tipado con el código estable de TASK-040 y propagación de `request_id`. TanStack Query como única cache de estado servidor. Componentes primitivos y patrones (`EmptyState`, `AsyncBoundary`, `DataTable`) antes de las pantallas. Los guards controlan navegación, nunca permisos: la autorización la decide el backend. Todo HTML de usuario se renderiza como texto salvo sanitización explícita, que es la lección de F-03.

### Scope

IN SCOPE:

- `frontend/src/api/`, `components/primitives`, `components/patterns`, `components/layout`, `app/` (router, providers, guards).
- Tests de la capa HTTP y de los componentes base.

OUT OF SCOPE:

- Pantallas de producto: cada una llega con su vertical.
- Recalcular reglas de negocio, elegibilidad o permisos en el cliente.
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `frontend/src/**`.
- Sin cambios en el backend.

### Dependencies

Depends on: TASK-038, TASK-042, TASK-043

### Blocks

Blocks: TASK-046

### Parallelization

Can run in parallel with: TASK-045

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] No existe `fetch` fuera del cliente autorizado; una regla de lint lo impide.
- [ ] El cliente envía CSRF automáticamente y reintenta un `401` exactamente una vez.
- [ ] `ApiError` expone el código estable y el `request_id` de la respuesta.
- [ ] Los guards controlan navegación y no sustituyen ninguna decisión de autorización del backend.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Tests de la capa HTTP con Mock Service Worker o fixtures validadas contra los tipos generados: reintento, CSRF, forma de error y propagación de `request_id`. Smoke en navegador de un shell con guard, comprobando requests y DOM. Verificar que la regla de lint contra `fetch` suelto falla cuando se introduce uno.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: HIGH
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM

## TASK-045 — Publicar health, readiness y logging estructurado de la API

Status: TODO
Priority: HIGH
Phase: PHASE-M2
Category: Observability / Infrastructure

### Objective

Exponer `/healthz` y `/readyz` con la semántica de §6.4 y emitir logs JSON con `request_id`, actor anonimizado, ruta, status, latencia y job id.

### Problem

§6.4 separa liveness de readiness y exige logs estructurados y métricas concretas. Cloud Run necesita esa distinción para decidir si enruta tráfico a una revisión, y hoy no existe.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:235-244` (Confidence: HIGH).
- TASK-028 en este documento (medir flujos críticos y hacer visibles fallos parciales).
- F-24 en [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md): observabilidad limitada.

### Why this is a problem

Un `/healthz` que toca la base de datos convierte una caída de DB en un reinicio en bucle; un `/readyz` que no la toca deja entrar tráfico a una réplica que no puede responder.

### Desired State

Liveness que solo prueba que el proceso vive, readiness que prueba DB y dependencias indispensables con timeout corto, y logs correlacionables por `request_id`.

### Proposed Solution

Complementar TASK-028 en vez de duplicarla: esta tarea aporta los endpoints y el formato de log que Cloud Run consume, y TASK-028 aporta las métricas de negocio. Sin PII en los logs: el actor se identifica de forma anonimizada. `request_id` compartido con el error model de TASK-040. Las migraciones no corren al arrancar la réplica: eso es responsabilidad del Job de TASK-056.

### Scope

IN SCOPE:

- Endpoints `/healthz` y `/readyz`, middleware y formato de logging estructurado.
- Tests de readiness con dependencia caída.

OUT OF SCOPE:

- Dashboards y alertas: TASK-057.
- Métricas de negocio y de gasto IA: TASK-028.
- Registrar PII o secretos en los logs.
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `backend/app/core/` (observabilidad), `backend/app/main.py` o equivalente, tests propios.

### Dependencies

Depends on: TASK-028, TASK-037

### Blocks

Blocks: TASK-056

### Parallelization

Can run in parallel with: TASK-040, TASK-041, TASK-042, TASK-043, TASK-044

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] `/healthz` responde sin tocar DB ni proveedores externos.
- [ ] `/readyz` falla con timeout corto cuando la DB no está disponible, y lo dice sin filtrar detalle de infraestructura.
- [ ] Los logs son JSON con `request_id`, actor anonimizado, ruta, status, latencia y job id cuando aplica.
- [ ] Ningún log contiene PII ni secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Bajar la DB en la lane de integración y comprobar que `/readyz` falla mientras `/healthz` sigue respondiendo. Verificar que el `request_id` de una respuesta de error aparece en su log. Revisar una muestra de logs buscando PII y secretos.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: MEDIUM
Performance: LOW
Maintainability: HIGH
Cost: LOW
Risk: LOW

## TASK-046 — Vertical 1 — Shell público y autenticación en React

Status: TODO
Priority: HIGH
Phase: PHASE-M3
Category: Frontend / API Contract / Migration

### Objective

Migrar home, about, login, registro, sesión y logout a React, sobre el contrato de sesión de TASK-042.

### Problem

§8 pone esta vertical primero porque es la de menor riesgo y la que fija el patrón para las siete siguientes: si el ingreso, la cookie y el CSRF no funcionan a través del proxy, nada de lo demás puede migrarse.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:296-297` (orden de verticales, Confidence: HIGH).
- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:334-336` (exit gate de Fase 2: registro/login/session/logout y una mutación CSRF a través del proxy).
- Pantallas actuales en `app/templates/` y `app/views/views.py`; SEO existente (sitemap, structured data).

### Why this is a problem

Una vertical migrada a medias deja dos consumidores para el mismo dominio y obliga a mantener dos implementaciones de sus reglas. El plan §13 es explícito: un dominio no está migrado si solo «se ve» — debe conservar permisos, estados de error, navegación profunda, refresh, uploads, reintentos y accesibilidad.

### Desired State

Las pantallas de la vertical servidas por React contra el contrato REST nuevo, con paridad funcional y visual demostrada contra la baseline de TASK-035, y cero tráfico del frontend al contrato legacy.

### Proposed Solution

Montar las páginas públicas y el flujo de autenticación de ambos actores sobre los shells de TASK-044. Conservar el SEO de las páginas públicas: sitemap y datos estructurados existen hoy y una SPA los pierde si nadie se ocupa; decidir y documentar cómo se preservan. Mantener el adapter legacy mientras el template Jinja siga sirviendo la misma pantalla a usuarios que no pasan por React.

### Scope

IN SCOPE:

- Pantallas públicas y de auth en `frontend/src/features/auth/` y layout público.
- Endpoints REST de la vertical según la matriz de TASK-034; adapters legacy de compatibilidad.
- Preservación de SEO de las páginas públicas.

OUT OF SCOPE:

- Migrar pantallas de otra vertical: cada una tiene su propia tarea y su propio gate de paridad.
- Retirar el template, el JS o el endpoint legacy en esta tarea: el retiro es TASK-059, tras comprobar cero tráfico.
- Reimplementar en React reglas que decide el backend (elegibilidad, permisos, umbrales, progreso).
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `frontend/src/features/auth/**`, `frontend/src/app/**`, `backend/app/` rutas de auth y públicas.
- Tests E2E de registro, login, sesión, logout y acceso anónimo.

### Dependencies

Depends on: TASK-035, TASK-042, TASK-044

### Blocks

Blocks: TASK-047, TASK-048, TASK-049, TASK-050, TASK-051, TASK-052, TASK-053

### Parallelization

Can run in parallel with: NONE

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] Las pantallas de la vertical funcionan en React contra el contrato REST, a través del proxy same-origin.
- [ ] Paridad funcional y visual demostrada contra la baseline de TASK-035, incluidas versiones desktop y mobile.
- [ ] Tests de permisos y de errores por rol: el acceso prohibido sigue prohibido y responde igual.
- [ ] Cero tráfico del frontend al contrato legacy de esta vertical, medido y registrado.
- [ ] Los hallazgos de auditoría del dominio están corregidos, no portados al código nuevo.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Playwright sobre compose para los flujos de la vertical, incluidos casos de acceso prohibido. Comparación visual contra las capturas de TASK-035 en desktop y mobile. Tests de contrato de los endpoints nuevos (status, JSON, enums, nulls, ownership, errores e idempotencia). Medir llamadas al endpoint legacy durante al menos un ciclo antes de declarar la vertical cerrada. Registrar comandos, resultados y cualquier test omitido.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: HIGH
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM

## TASK-047 — Vertical 2 — Perfil, cuestionario y CV en React

Status: TODO
Priority: HIGH
Phase: PHASE-M3
Category: Frontend / API Contract / Migration

### Objective

Migrar perfil, cuestionario y gestión de CV, incluidos uploads multipart y la auditoría de CV.

### Problem

§8 sitúa esta vertical segunda porque «cubre uploads, permisos y base del resto». Concentra los hallazgos de seguridad ya corregidos (F-03 HTML no escapado, F-04 identidad de objetos, F-05 límites de upload) y el contrato de CV que §5.2 renombra a `/resumes` y `/resume-course-audits`.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:298` (Confidence: HIGH).
- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:148-153` (correspondencias de perfil y CV).
- TASK-004, TASK-005, TASK-006 (COMPLETED): escapado, identidad de objetos y límites de upload.
- TASK-030 (pendiente): validación de respuestas y versión histórica del cuestionario.

### Why this is a problem

Una vertical migrada a medias deja dos consumidores para el mismo dominio y obliga a mantener dos implementaciones de sus reglas. El plan §13 es explícito: un dominio no está migrado si solo «se ve» — debe conservar permisos, estados de error, navegación profunda, refresh, uploads, reintentos y accesibilidad.

### Desired State

Las pantallas de la vertical servidas por React contra el contrato REST nuevo, con paridad funcional y visual demostrada contra la baseline de TASK-035, y cero tráfico del frontend al contrato legacy.

### Proposed Solution

Renombrar según §5.2: `GET/PATCH /users/me`, `GET/POST/DELETE /resumes`, `POST/GET /resume-course-audits`. El upload multipart conserva los límites de TASK-006 y la identidad de objeto de TASK-005; el nombre de archivo se renderiza como texto, que es la corrección de F-03 y no se puede perder al reescribir la pantalla. La auditoría de CV usa `Idempotency-Key` (TASK-041) porque dispara gasto de IA. El umbral de aprobación lo decide el backend con la policy de TASK-016: React muestra la decisión y el umbral como texto descriptivo.

### Scope

IN SCOPE:

- Pantallas de perfil, cuestionario y CV; endpoints REST renombrados con adapter legacy.
- Uploads multipart con límites, idempotencia y autorización por entidad.

OUT OF SCOPE:

- Migrar pantallas de otra vertical: cada una tiene su propia tarea y su propio gate de paridad.
- Retirar el template, el JS o el endpoint legacy en esta tarea: el retiro es TASK-059, tras comprobar cero tráfico.
- Reimplementar en React reglas que decide el backend (elegibilidad, permisos, umbrales, progreso).
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `frontend/src/features/profile-resumes/**`, `backend/app/` rutas de perfil, resumes y auditoría.
- Tests de upload, ownership, límites y renderizado seguro de nombres de archivo.

### Dependencies

Depends on: TASK-006, TASK-030, TASK-041, TASK-046

### Blocks

Blocks: TASK-053

### Parallelization

Can run in parallel with: TASK-048, TASK-050

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] Las pantallas de la vertical funcionan en React contra el contrato REST, a través del proxy same-origin.
- [ ] Paridad funcional y visual demostrada contra la baseline de TASK-035, incluidas versiones desktop y mobile.
- [ ] Tests de permisos y de errores por rol: el acceso prohibido sigue prohibido y responde igual.
- [ ] Cero tráfico del frontend al contrato legacy de esta vertical, medido y registrado.
- [ ] Los hallazgos de auditoría del dominio están corregidos, no portados al código nuevo.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Playwright sobre compose para los flujos de la vertical, incluidos casos de acceso prohibido. Comparación visual contra las capturas de TASK-035 en desktop y mobile. Tests de contrato de los endpoints nuevos (status, JSON, enums, nulls, ownership, errores e idempotencia). Medir llamadas al endpoint legacy durante al menos un ciclo antes de declarar la vertical cerrada. Registrar comandos, resultados y cualquier test omitido.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: HIGH
Performance: MEDIUM
Maintainability: HIGH
Cost: MEDIUM
Risk: HIGH

## TASK-048 — Vertical 3 — Dashboard, recursos y roadmaps en React

Status: TODO
Priority: HIGH
Phase: PHASE-M3
Category: Frontend / API Contract / Migration

### Objective

Migrar el dashboard del estudiante, el hub de recursos y los roadmaps, sobre la proyección de progreso unificada.

### Problem

§8 pone esta vertical tercera porque «resuelve progreso compartido». TASK-016 ya dejó una sola policy de aprobación y un solo proyector de progreso, así que las pantallas nuevas pueden consumir la misma respuesta en vez de recalcular porcentajes en el cliente.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:299` (Confidence: HIGH).
- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:144-145` (`GET /dashboard/student`), `:161-162` (`PUT/DELETE /roadmaps/{slug}/saves/me`).
- TASK-016 (COMPLETED): `CourseProgressProjector` y `resources.core_code`.
- TASK-018 y TASK-025 (pendientes): agrupación de consultas y cálculo del dashboard en DB.

### Why this is a problem

Una vertical migrada a medias deja dos consumidores para el mismo dominio y obliga a mantener dos implementaciones de sus reglas. El plan §13 es explícito: un dominio no está migrado si solo «se ve» — debe conservar permisos, estados de error, navegación profunda, refresh, uploads, reintentos y accesibilidad.

### Desired State

Las pantallas de la vertical servidas por React contra el contrato REST nuevo, con paridad funcional y visual demostrada contra la baseline de TASK-035, y cero tráfico del frontend al contrato legacy.

### Proposed Solution

Renombrar `GET /students_dashboard` a `GET /dashboard/student` y convertir save de roadmap en la relación idempotente `PUT/DELETE /roadmaps/{slug}/saves/me`. El progreso lo proyecta el backend: React no vuelve a calcular porcentajes ni a decidir si una lección está completa. Ninguna pantalla de esta vertical puede escribir caches al leer, que es la propiedad que TASK-016 acaba de establecer y que un GET nuevo podría reintroducir sin querer.

### Scope

IN SCOPE:

- Dashboard de estudiante, hub de recursos y roadmaps; endpoints REST renombrados con adapter legacy.
- Consumo de la proyección de progreso; ningún cálculo de progreso en el cliente.

OUT OF SCOPE:

- Migrar pantallas de otra vertical: cada una tiene su propia tarea y su propio gate de paridad.
- Retirar el template, el JS o el endpoint legacy en esta tarea: el retiro es TASK-059, tras comprobar cero tráfico.
- Reimplementar en React reglas que decide el backend (elegibilidad, permisos, umbrales, progreso).
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `frontend/src/features/dashboard/**`, `features/resources-roadmaps/**`, `backend/app/` rutas correspondientes.
- Tests de paridad de porcentajes contra la proyección y de ausencia de escrituras en GET.

### Dependencies

Depends on: TASK-018, TASK-025, TASK-046

### Blocks

Blocks: TASK-053

### Parallelization

Can run in parallel with: TASK-047, TASK-050

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] Las pantallas de la vertical funcionan en React contra el contrato REST, a través del proxy same-origin.
- [ ] Paridad funcional y visual demostrada contra la baseline de TASK-035, incluidas versiones desktop y mobile.
- [ ] Tests de permisos y de errores por rol: el acceso prohibido sigue prohibido y responde igual.
- [ ] Cero tráfico del frontend al contrato legacy de esta vertical, medido y registrado.
- [ ] Los hallazgos de auditoría del dominio están corregidos, no portados al código nuevo.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Playwright sobre compose para los flujos de la vertical, incluidos casos de acceso prohibido. Comparación visual contra las capturas de TASK-035 en desktop y mobile. Tests de contrato de los endpoints nuevos (status, JSON, enums, nulls, ownership, errores e idempotencia). Medir llamadas al endpoint legacy durante al menos un ciclo antes de declarar la vertical cerrada. Registrar comandos, resultados y cualquier test omitido.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: MEDIUM
Performance: HIGH
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM

## TASK-049 — Vertical 4 — Jobs, análisis de CV y candidaturas en React

Status: TODO
Priority: HIGH
Phase: PHASE-M3
Category: Frontend / API Contract / Migration

### Objective

Migrar el tablero de empleos, el análisis de CV y las candidaturas, con polling de jobs durables sobre Cloud Tasks.

### Problem

§8 dice que esta vertical «introduce Cloud Tasks y polling durable». Es la primera que depende de que el runner haya salido del lifespan: mientras el job viva dentro de la réplica web, una instancia a cero deja el análisis sin ejecutar.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:300` (Confidence: HIGH).
- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:154-157` (`POST /cv-analyses`, `GET /cv-analyses/{id}`, `POST /job-searches`), `:166-167` (`PUT /applications/{id}/selected-interview`).
- TASK-013, TASK-014 (COMPLETED): job de CV durable e idempotente, transiciones centralizadas.
- TASK-020 (pendiente): scraper de LinkedIn fuera del event loop.

### Why this is a problem

Una vertical migrada a medias deja dos consumidores para el mismo dominio y obliga a mantener dos implementaciones de sus reglas. El plan §13 es explícito: un dominio no está migrado si solo «se ve» — debe conservar permisos, estados de error, navegación profunda, refresh, uploads, reintentos y accesibilidad.

### Desired State

Las pantallas de la vertical servidas por React contra el contrato REST nuevo, con paridad funcional y visual demostrada contra la baseline de TASK-035, y cero tráfico del frontend al contrato legacy.

### Proposed Solution

`POST /cv-analyses` responde `202` con el recurso job; `GET /cv-analyses/{id}` expone estado y resultados. El polling vive en TanStack Query y respeta backoff: no se convierte la SPA en un generador de tráfico. Las candidaturas usan `Idempotency-Key`. La selección de entrevista se expresa como relación idempotente `PUT /applications/{id}/selected-interview`, apoyada en la unicidad que TASK-015 ya garantiza en DB. El estado de candidatura lo decide la transición única de TASK-014; React no lo recalcula.

### Scope

IN SCOPE:

- Tablero de empleos, análisis de CV y candidaturas; endpoints REST con `202` y polling.
- Idempotencia en creación de candidaturas y de jobs; selección de entrevista idempotente.

OUT OF SCOPE:

- Migrar pantallas de otra vertical: cada una tiene su propia tarea y su propio gate de paridad.
- Retirar el template, el JS o el endpoint legacy en esta tarea: el retiro es TASK-059, tras comprobar cero tráfico.
- Reimplementar en React reglas que decide el backend (elegibilidad, permisos, umbrales, progreso).
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `frontend/src/features/jobs-applications/**`, `backend/app/` rutas de jobs, análisis y candidaturas.
- Tests E2E de candidatura y de análisis con replay; tests de polling acotado.

### Dependencies

Depends on: TASK-020, TASK-041, TASK-046, TASK-054

### Blocks

Blocks: TASK-053

### Parallelization

Can run in parallel with: TASK-050, TASK-051

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] Las pantallas de la vertical funcionan en React contra el contrato REST, a través del proxy same-origin.
- [ ] Paridad funcional y visual demostrada contra la baseline de TASK-035, incluidas versiones desktop y mobile.
- [ ] Tests de permisos y de errores por rol: el acceso prohibido sigue prohibido y responde igual.
- [ ] Cero tráfico del frontend al contrato legacy de esta vertical, medido y registrado.
- [ ] Los hallazgos de auditoría del dominio están corregidos, no portados al código nuevo.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Playwright sobre compose para los flujos de la vertical, incluidos casos de acceso prohibido. Comparación visual contra las capturas de TASK-035 en desktop y mobile. Tests de contrato de los endpoints nuevos (status, JSON, enums, nulls, ownership, errores e idempotencia). Medir llamadas al endpoint legacy durante al menos un ciclo antes de declarar la vertical cerrada. Registrar comandos, resultados y cualquier test omitido.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: HIGH
Performance: HIGH
Maintainability: HIGH
Cost: HIGH
Risk: HIGH

## TASK-050 — Vertical 5 — Company: dashboard, postings, applicants, entrevistas y recruiters

Status: TODO
Priority: HIGH
Phase: PHASE-M3
Category: Frontend / API Contract / Migration

### Objective

Migrar todas las pantallas del actor recruiter, conservando su identidad separada y sus permisos por rol.

### Problem

§8 agrupa la vertical de compañía como un bloque porque comparte identidad, permisos y navegación. §6.2 pide conservar cookies separadas para estudiante y recruiter durante la migración, así que esta vertical prueba que dos actores conviven en la misma SPA sin mezclarse.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:301` (Confidence: HIGH).
- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:146` (`GET /companies/me/dashboard`), `:205-207` (cookies separadas).
- TASK-010 (COMPLETED): autenticación de compañías cubierta.
- TASK-015 (COMPLETED): una sola reserva de entrevista efectiva por candidatura.

### Why this is a problem

Una vertical migrada a medias deja dos consumidores para el mismo dominio y obliga a mantener dos implementaciones de sus reglas. El plan §13 es explícito: un dominio no está migrado si solo «se ve» — debe conservar permisos, estados de error, navegación profunda, refresh, uploads, reintentos y accesibilidad.

### Desired State

Las pantallas de la vertical servidas por React contra el contrato REST nuevo, con paridad funcional y visual demostrada contra la baseline de TASK-035, y cero tráfico del frontend al contrato legacy.

### Proposed Solution

Renombrar `GET /company_dashboard` a `GET /companies/me/dashboard`. Los rangos de rol de recruiter los decide el backend: la UI no reimplementa quién puede asignar a quién. La reserva de entrevista se apoya en la unicidad de TASK-015; dos recruiters confirmando a la vez siguen produciendo una sola reserva efectiva y la UI muestra el conflicto en vez de inventar un segundo estado.

### Scope

IN SCOPE:

- Pantallas de compañía en `frontend/src/features/company/`; endpoints REST renombrados con adapter legacy.
- Guards de shell de compañía; permisos decididos en backend.

OUT OF SCOPE:

- Migrar pantallas de otra vertical: cada una tiene su propia tarea y su propio gate de paridad.
- Retirar el template, el JS o el endpoint legacy en esta tarea: el retiro es TASK-059, tras comprobar cero tráfico.
- Reimplementar en React reglas que decide el backend (elegibilidad, permisos, umbrales, progreso).
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `frontend/src/features/company/**`, `backend/app/` rutas de compañía, postings, applicants y recruiters.
- Tests E2E de recruiter y de acceso prohibido cruzado entre actores.

### Dependencies

Depends on: TASK-046

### Blocks

Blocks: TASK-053

### Parallelization

Can run in parallel with: TASK-047, TASK-048, TASK-049

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] Las pantallas de la vertical funcionan en React contra el contrato REST, a través del proxy same-origin.
- [ ] Paridad funcional y visual demostrada contra la baseline de TASK-035, incluidas versiones desktop y mobile.
- [ ] Tests de permisos y de errores por rol: el acceso prohibido sigue prohibido y responde igual.
- [ ] Cero tráfico del frontend al contrato legacy de esta vertical, medido y registrado.
- [ ] Los hallazgos de auditoría del dominio están corregidos, no portados al código nuevo.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Playwright sobre compose para los flujos de la vertical, incluidos casos de acceso prohibido. Comparación visual contra las capturas de TASK-035 en desktop y mobile. Tests de contrato de los endpoints nuevos (status, JSON, enums, nulls, ownership, errores e idempotencia). Medir llamadas al endpoint legacy durante al menos un ciclo antes de declarar la vertical cerrada. Registrar comandos, resultados y cualquier test omitido.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: HIGH
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: HIGH

## TASK-051 — Vertical 6 — Community, friendships y messages en React

Status: TODO
Priority: HIGH
Phase: PHASE-M3
Category: Frontend / API Contract / Migration

### Objective

Migrar comunidades, amistades y mensajería, con paginación por cursor y estado optimista donde aporte.

### Problem

§8 pide paginación y estado optimista aquí, y advierte explícitamente: tiempo real solo si hay requerimiento, no introducir WebSockets por defecto. §5.2 convierte join/leave de comunidad en la relación idempotente `PUT/DELETE /communities/{id}/members/me`.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:302-303` (Confidence: HIGH).
- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:158-160, 163-164` (relaciones idempotentes y `PATCH /friend-requests/{id}`).
- TASK-017 (COMPLETED): contador de comunidad derivado de membresías.
- TASK-024 (pendiente): paginación de mensajes con cursor estable.

### Why this is a problem

Una vertical migrada a medias deja dos consumidores para el mismo dominio y obliga a mantener dos implementaciones de sus reglas. El plan §13 es explícito: un dominio no está migrado si solo «se ve» — debe conservar permisos, estados de error, navegación profunda, refresh, uploads, reintentos y accesibilidad.

### Desired State

Las pantallas de la vertical servidas por React contra el contrato REST nuevo, con paridad funcional y visual demostrada contra la baseline de TASK-035, y cero tráfico del frontend al contrato legacy.

### Proposed Solution

`PUT /communities/{id}/members/me` y su `DELETE` sustituyen a join/leave: la relación es idempotente y un doble clic deja de ser un `409` sorpresa. Aceptar una solicitud de amistad pasa a `PATCH /friend-requests/{id}` con `{status: accepted}`. Los mensajes usan el cursor estable de TASK-024, no offset. El contador de miembros viene derivado del backend (TASK-017); la UI no lo incrementa por su cuenta al unirse. Estado optimista solo donde la operación es idempotente y la reversión es visible.

### Scope

IN SCOPE:

- Comunidades, amistades y mensajería; endpoints REST idempotentes; paginación por cursor.
- Estado optimista acotado a operaciones idempotentes.

OUT OF SCOPE:

- Migrar pantallas de otra vertical: cada una tiene su propia tarea y su propio gate de paridad.
- Retirar el template, el JS o el endpoint legacy en esta tarea: el retiro es TASK-059, tras comprobar cero tráfico.
- Reimplementar en React reglas que decide el backend (elegibilidad, permisos, umbrales, progreso).
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `frontend/src/features/community-messages/**`, `backend/app/` rutas de comunidad, amistades y mensajes.
- Tests de paginación por cursor, de idempotencia de join/leave y de estado optimista revertido.

### Dependencies

Depends on: TASK-024, TASK-046

### Blocks

Blocks: TASK-053

### Parallelization

Can run in parallel with: TASK-049, TASK-052

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] Las pantallas de la vertical funcionan en React contra el contrato REST, a través del proxy same-origin.
- [ ] Paridad funcional y visual demostrada contra la baseline de TASK-035, incluidas versiones desktop y mobile.
- [ ] Tests de permisos y de errores por rol: el acceso prohibido sigue prohibido y responde igual.
- [ ] Cero tráfico del frontend al contrato legacy de esta vertical, medido y registrado.
- [ ] Los hallazgos de auditoría del dominio están corregidos, no portados al código nuevo.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Playwright sobre compose para los flujos de la vertical, incluidos casos de acceso prohibido. Comparación visual contra las capturas de TASK-035 en desktop y mobile. Tests de contrato de los endpoints nuevos (status, JSON, enums, nulls, ownership, errores e idempotencia). Medir llamadas al endpoint legacy durante al menos un ciclo antes de declarar la vertical cerrada. Registrar comandos, resultados y cualquier test omitido.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: MEDIUM
Performance: HIGH
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM

## TASK-052 — Vertical 7 — Career Lab / Capstone en React

Status: TODO
Priority: HIGH
Phase: PHASE-M3
Category: Frontend / API Contract / Migration

### Objective

Migrar Career Lab conservando versiones, provenance y snapshots de las ejecuciones analíticas.

### Problem

§8 exige conservar versiones, provenance y snapshots. §5.2 añade que las operaciones analíticas (`extract`, `sync`, `optimize`, `evaluate`) deben devolver un recurso `run` con identidad, estado y versión, no un efecto anónimo. Esta vertical sustituye el trabajo que TASK-026 iba a hacer sobre el JS legacy.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:304, 170-173` (Confidence: HIGH).
- TASK-023 (pendiente): dividir Capstone conservando facade y contratos.
- TASK-026 (SUPERSEDED por esta tarea): separaba API, estado y render del JS de Jobs y Career Lab sin cambiar a React.
- F-19 en [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md): Capstone concentra demasiadas responsabilidades.

### Why this is a problem

Una vertical migrada a medias deja dos consumidores para el mismo dominio y obliga a mantener dos implementaciones de sus reglas. El plan §13 es explícito: un dominio no está migrado si solo «se ve» — debe conservar permisos, estados de error, navegación profunda, refresh, uploads, reintentos y accesibilidad.

### Desired State

Las pantallas de la vertical servidas por React contra el contrato REST nuevo, con paridad funcional y visual demostrada contra la baseline de TASK-035, y cero tráfico del frontend al contrato legacy.

### Proposed Solution

Cada operación analítica devuelve un `run` identificable con estado y versión de objetivo, de modo que un resultado histórico siga siendo explicable. No se recalculan snapshots antiguos ni se cambian pesos, heurísticas o thresholds: eso sigue fuera de alcance igual que lo estaba en TASK-023. El backend ya dividido por TASK-023 expone casos de uso; esta tarea consume esos contratos desde React y retira la necesidad de reorganizar el JS legacy.

### Scope

IN SCOPE:

- Pantallas de Career Lab; endpoints de operaciones analíticas como recursos `run`.
- Consumo de los casos de uso extraídos por TASK-023.

OUT OF SCOPE:

- Migrar pantallas de otra vertical: cada una tiene su propia tarea y su propio gate de paridad.
- Retirar el template, el JS o el endpoint legacy en esta tarea: el retiro es TASK-059, tras comprobar cero tráfico.
- Reimplementar en React reglas que decide el backend (elegibilidad, permisos, umbrales, progreso).
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `frontend/src/features/career-lab/**`, `backend/app/` rutas de Capstone y analítica.
- Tests de contrato de `run` (identidad, estado, versión) y de reproducibilidad de snapshots.

### Dependencies

Depends on: TASK-022, TASK-023, TASK-046

### Blocks

Blocks: TASK-053

### Parallelization

Can run in parallel with: TASK-051

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] Las pantallas de la vertical funcionan en React contra el contrato REST, a través del proxy same-origin.
- [ ] Paridad funcional y visual demostrada contra la baseline de TASK-035, incluidas versiones desktop y mobile.
- [ ] Tests de permisos y de errores por rol: el acceso prohibido sigue prohibido y responde igual.
- [ ] Cero tráfico del frontend al contrato legacy de esta vertical, medido y registrado.
- [ ] Los hallazgos de auditoría del dominio están corregidos, no portados al código nuevo.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Playwright sobre compose para los flujos de la vertical, incluidos casos de acceso prohibido. Comparación visual contra las capturas de TASK-035 en desktop y mobile. Tests de contrato de los endpoints nuevos (status, JSON, enums, nulls, ownership, errores e idempotencia). Medir llamadas al endpoint legacy durante al menos un ciclo antes de declarar la vertical cerrada. Registrar comandos, resultados y cualquier test omitido.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: MEDIUM
Performance: HIGH
Maintainability: HIGH
Cost: MEDIUM
Risk: HIGH

## TASK-053 — Vertical 8 — Admin en React

Status: TODO
Priority: HIGH
Phase: PHASE-M3
Category: Frontend / API Contract / Migration

### Objective

Migrar el panel de administración, último consumidor del contrato legacy.

### Problem

§8 pone admin al final porque «elimina toggles y uploads legacy». §5.2 convierte `PATCH /admin/users/{id}/toggle-active` en `PATCH /admin/users/{id}` con `{is_active: bool}`: un verbo que describe la intención en vez del efecto.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:305, 168-169` (Confidence: HIGH).
- `app/routes/adminRoute.py` (lectura de contadores y toggles).

### Why this is a problem

Una vertical migrada a medias deja dos consumidores para el mismo dominio y obliga a mantener dos implementaciones de sus reglas. El plan §13 es explícito: un dominio no está migrado si solo «se ve» — debe conservar permisos, estados de error, navegación profunda, refresh, uploads, reintentos y accesibilidad.

### Desired State

Las pantallas de la vertical servidas por React contra el contrato REST nuevo, con paridad funcional y visual demostrada contra la baseline de TASK-035, y cero tráfico del frontend al contrato legacy.

### Proposed Solution

Sustituir los toggles por `PATCH` con el estado deseado, que es idempotente y auditable. Al ser el último consumidor, esta tarea cierra el inventario de TASK-034: cualquier endpoint legacy que siga con tráfico después de aquí es un hallazgo, no un pendiente. Los permisos de administración los decide el backend; el shell de admin solo controla navegación.

### Scope

IN SCOPE:

- Panel de administración en React; endpoints REST de admin con adapter legacy.
- Cierre del inventario de consumidores legacy.

OUT OF SCOPE:

- Migrar pantallas de otra vertical: cada una tiene su propia tarea y su propio gate de paridad.
- Retirar el template, el JS o el endpoint legacy en esta tarea: el retiro es TASK-059, tras comprobar cero tráfico.
- Reimplementar en React reglas que decide el backend (elegibilidad, permisos, umbrales, progreso).
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `frontend/src/features/admin/**`, `backend/app/routes/adminRoute.py` y equivalentes.
- Tests E2E de admin y de acceso prohibido para no administradores.

### Dependencies

Depends on: TASK-047, TASK-048, TASK-049, TASK-050, TASK-051, TASK-052

### Blocks

Blocks: TASK-058

### Parallelization

Can run in parallel with: NONE

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] Las pantallas de la vertical funcionan en React contra el contrato REST, a través del proxy same-origin.
- [ ] Paridad funcional y visual demostrada contra la baseline de TASK-035, incluidas versiones desktop y mobile.
- [ ] Tests de permisos y de errores por rol: el acceso prohibido sigue prohibido y responde igual.
- [ ] Cero tráfico del frontend al contrato legacy de esta vertical, medido y registrado.
- [ ] Los hallazgos de auditoría del dominio están corregidos, no portados al código nuevo.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Playwright sobre compose para los flujos de la vertical, incluidos casos de acceso prohibido. Comparación visual contra las capturas de TASK-035 en desktop y mobile. Tests de contrato de los endpoints nuevos (status, JSON, enums, nulls, ownership, errores e idempotencia). Medir llamadas al endpoint legacy durante al menos un ciclo antes de declarar la vertical cerrada. Registrar comandos, resultados y cualquier test omitido.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: HIGH
Performance: LOW
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM

## TASK-054 — Sacar el runner de CV del lifespan con outbox y Cloud Tasks

Status: TODO
Priority: CRITICAL
Phase: PHASE-M4
Category: Infrastructure / Reliability

### Objective

Que un análisis de CV encolado sobreviva a un deploy, a la escala a cero y a un replay, sin gastar IA dos veces.

### Problem

§6.3 es explícito: el runner dentro del lifespan no debe ser el mecanismo principal en producción porque escala con cada réplica y una instancia a cero no ejecuta polling. Hoy el runner arranca dentro de cada proceso web (§2).

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:216-234` (Confidence: HIGH).
- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:463-464` (riesgos: jobs perdidos al escalar a cero; dos runners gastan IA).
- TASK-013 (COMPLETED): `job_analysis` durable con claim, lease e idempotencia.

### Why this is a problem

Con el runner en la réplica web, escalar a cero deja jobs sin ejecutar y escalar a N hace que varias réplicas compitan por el mismo job, con gasto de IA duplicado si el claim falla.

### Desired State

La API persiste el job y encola una Cloud Task después del commit; un endpoint interno con OIDC reclama el lease atómicamente y responde éxito ante un replay terminal.

### Proposed Solution

Tabla outbox para no perder el dispatch entre el commit de DB y Cloud Tasks: encolar dentro de la transacción es imposible y encolar antes del commit pierde jobs. `job_analysis` sigue siendo la fuente durable de estado, lease e idempotencia (TASK-013); esta tarea solo cambia quién dispara el trabajo. Cloud Tasks llama `/internal/tasks/cv-analyses/{id}` con OIDC y retry acotado. Un Cloud Scheduler reencola vencidos y no procesa IA. En local, un servicio `worker` de compose consume la misma outbox para no depender de Google Cloud. Si Cloud Tasks no se aprueba, la alternativa es un tercer Cloud Run worker con `min-instances=1`, presupuestado explícitamente; lo que no se hace es dejar un loop oculto en todas las réplicas web.

### Scope

IN SCOPE:

- Tabla outbox y su migración, endpoint interno autenticado por OIDC, worker local de compose.
- Retiro del arranque del runner en el lifespan de la réplica web.

OUT OF SCOPE:

- Cambiar el modelo de estados de `job_analysis` o su lease: eso lo fijó TASK-013.
- Procesar IA desde el scheduler de reconciliación.
- Mantener un loop de polling en las réplicas web como respaldo permanente.
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `backend/app/` (outbox, endpoint interno, lifespan), migración nueva, `docker-compose.yml` (worker).
- Tests de dispatch, replay y reconciliación.

### Dependencies

Depends on: TASK-013, TASK-037

### Blocks

Blocks: TASK-049, TASK-056

### Parallelization

Can run in parallel with: TASK-055

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] Un job encolado sobrevive al reinicio del proceso y a la escala a cero.
- [ ] Un replay del mismo task no produce un segundo gasto de IA efectivo.
- [ ] El endpoint interno rechaza llamadas sin OIDC válido.
- [ ] Ninguna réplica web ejecuta un loop de polling de IA.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

En la lane PostgreSQL: encolar, matar el proceso antes de procesar y comprobar que el job se recupera. Disparar el mismo task dos veces en paralelo y verificar un solo consumo en el ledger de IA. Llamar el endpoint interno sin credenciales y comprobar el rechazo. No ejecutar llamadas pagadas: proveedor fake.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: HIGH
Performance: HIGH
Maintainability: HIGH
Cost: HIGH
Risk: HIGH

## TASK-055 — Aprovisionar Artifact Registry, WIF y Secret Manager

Status: TODO
Priority: HIGH
Phase: PHASE-M4
Category: Infrastructure / Security

### Objective

Dejar CI capaz de publicar imágenes y desplegar sin claves JSON persistentes, y los secretos fuera del repositorio y de las imágenes.

### Problem

§4 de Fase 4 pide Artifact Registry con dos imágenes, Workload Identity Federation para GitHub sin JSON keys, Secret Manager para DB, Redis, JWT, storage, Gemini y proveedores, y service accounts distintas con mínimo privilegio. Nada de eso existe.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:357-365` (Confidence: HIGH).
- TASK-002 (COMPLETED): secretos versionados retirados y rotación documentada.
- TASK-036: el ADR de ingreso condiciona la topología que se aprovisiona aquí.

### Why this is a problem

Una clave JSON de service account en los secretos de GitHub es una credencial de larga vida que no caduca ni se puede acotar por repositorio; WIF la sustituye por una identidad federada y efímera.

### Desired State

Dos repositorios de imágenes, identidad federada para el workflow, secretos en Secret Manager y una service account distinta por servicio con el mínimo privilegio necesario.

### Proposed Solution

Implementar la opción que TASK-036 decidió; esta tarea no re-decide el patrón de ingreso. Service accounts separadas para API, frontend, job de migraciones y Cloud Tasks, cada una con los permisos que necesita y ninguno más. Los secretos se inyectan como referencias de Secret Manager, nunca como variables literales en la definición del servicio ni horneados en la imagen. La imagen del frontend no contiene secretos: solo configuración pública (§11).

### Scope

IN SCOPE:

- Artifact Registry, WIF, Secret Manager, service accounts y sus permisos; documentación del aprovisionamiento.
- Referencias de secretos en la configuración de despliegue.

OUT OF SCOPE:

- Desplegar los servicios: eso es TASK-056.
- Rotar secretos de producción sin la autorización correspondiente.
- Imprimir valores de secretos en logs de CI.
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- Infraestructura como código o runbook versionado bajo `docs/refactor/`; `.github/workflows/`.
- Sin cambios de comportamiento en la aplicación.

### Dependencies

Depends on: TASK-002, TASK-036, TASK-039

### Blocks

Blocks: TASK-056

### Parallelization

Can run in parallel with: TASK-054

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] CI se autentica por WIF; no existe ninguna clave JSON de service account almacenada.
- [ ] Cada servicio tiene su propia service account con permisos mínimos justificados.
- [ ] Los secretos se resuelven desde Secret Manager y no aparecen en la imagen ni en los logs.
- [ ] La imagen del frontend no contiene secretos.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Ejecutar el workflow y comprobar que publica sin credenciales estáticas. Inspeccionar las imágenes construidas buscando secretos. Revisar los permisos efectivos de cada service account y justificar cada uno. Si el acceso a la consola de Google Cloud no está disponible, registrar BLOCKED con la evidencia pendiente en vez de declarar la tarea completa.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: HIGH
Performance: LOW
Maintainability: HIGH
Cost: MEDIUM
Risk: HIGH

## TASK-056 — Desplegar los servicios Cloud Run, el Job de migraciones y deploy.yml por SHA

Status: TODO
Priority: HIGH
Phase: PHASE-M4
Category: Infrastructure

### Objective

Poner en pie `studentscompass-api`, `studentscompass-front` y el Job `studentscompass-migrate`, desplegados por SHA desde CI con el orden y los gates de §10.

### Problem

§10 define una secuencia concreta —migrate, API sin tráfico, smoke, promoción, frontend— y §11 la configuración inicial de cada recurso. Hoy no hay pipeline de despliegue (§2) y las migraciones no corren como Job.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:397-410` (secuencia de deploy, Confidence: HIGH).
- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:411-427` (configuración de Cloud Run).
- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:243-244`: migraciones solo mediante Job, nunca al arrancar cada réplica.
- TASK-009 (COMPLETED): baseline y convergencia de schemas.

### Why this is a problem

Desplegar la API antes de migrar, o migrar al arrancar cada réplica, produce carreras de schema entre revisiones y hace imposible el rollback por revisión.

### Desired State

Un `deploy.yml` disparado solo tras CI verde del mismo SHA, que migra, despliega la API sin tráfico, ejecuta smoke, promueve y solo entonces despliega el frontend.

### Proposed Solution

Nunca desplegar por `:latest`: Cloud Run recibe tag SHA o digest. El Job de migraciones usa exactamente la imagen de API del mismo SHA, de modo que el código y el schema no se separan. Presupuesto global de conexiones: `pool_size × max_instances` por debajo del límite real de PostgreSQL o PgBouncer (§11), o el primer pico agota el pool. Ante fallo de smoke no se promueve, y el rollback de código exige que las migraciones sean backward-compatible, que es lo que el patrón expand/contract de §12 garantiza.

### Scope

IN SCOPE:

- `.github/workflows/deploy.yml`, definición de los servicios y del Job, configuración inicial de §11.
- Smoke de readiness contra la revisión sin tráfico antes de promover.

OUT OF SCOPE:

- Dominio, TLS, alertas y budgets: eso es TASK-057.
- Desplegar a producción antes de que staging esté verde.
- Usar `:latest` como referencia efectiva de despliegue.
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `.github/workflows/deploy.yml`, definiciones de servicio y job, `backend/Dockerfile`, `frontend/Dockerfile`.

### Dependencies

Depends on: TASK-009, TASK-045, TASK-054, TASK-055

### Blocks

Blocks: TASK-057

### Parallelization

Can run in parallel with: NONE

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] El despliegue va por SHA o digest; `:latest` no es la referencia efectiva.
- [ ] Las migraciones corren como Job bloqueante antes de que la API reciba tráfico, y nunca al arrancar una réplica.
- [ ] Una revisión que falla el smoke no se promueve.
- [ ] El presupuesto de conexiones (`pool_size × max_instances`) está por debajo del límite real de la base.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Desplegar a staging desde CI y comprobar la secuencia completa. Forzar un fallo de smoke y verificar que no hay promoción. Probar rollback a la revisión previa. Medir conexiones bajo carga y contrastar con el límite real. No usar producción como banco de pruebas.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: HIGH
Performance: MEDIUM
Maintainability: HIGH
Cost: HIGH
Risk: HIGH

## TASK-057 — Configurar dominio, TLS, alertas, budgets y rollback por revisión

Status: TODO
Priority: HIGH
Phase: PHASE-M4
Category: Infrastructure / Observability

### Objective

Dejar el servicio observable y reversible: dominio y TLS en el frontend, alertas sobre las métricas de §6.4 y rollback por revisión probado.

### Problem

§4 de Fase 4 cierra con dominio, TLS, alertas, budgets y rollback por revisión. Sin alertas, un fallo parcial —jobs atascados, gasto de IA disparado, pool agotado— se descubre por el reporte de un usuario.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:366` (Confidence: HIGH).
- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:239-241` (métricas: 5xx, p95, pool DB, 429, jobs por estado y edad, gasto IA, reintentos, errores de storage).
- TASK-028 (pendiente): medir flujos críticos y hacer visibles fallos parciales.

### Why this is a problem

El frontend es el único servicio con dominio público (§3): si el dominio apunta a otro sitio, cookies y CSRF dejan de ser same-origin y la seguridad del diseño se cae.

### Desired State

Dominio y TLS sobre el frontend, dashboards y alertas con umbrales accionables, budget de gasto con aviso, y un rollback por revisión ensayado y documentado.

### Proposed Solution

Las alertas cubren lo que §6.4 nombra y usan las métricas que TASK-028 emite: no inventar una segunda fuente de telemetría. Cada alerta tiene un umbral justificado y un runbook, o es ruido. Budget de gasto de IA con aviso antes del techo, apoyado en el guard de TASK-007 y el ledger de TASK-012. El rollback se ensaya de verdad, no se documenta como intención.

### Scope

IN SCOPE:

- Mapeo de dominio y TLS, dashboards, alertas con runbook, budgets, procedimiento de rollback ensayado.

OUT OF SCOPE:

- Cambiar los límites de gasto de IA o el techo de cuota: eso lo fijaron TASK-007 y TASK-012.
- Alertas sin umbral justificado ni runbook.
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- Configuración de observabilidad y alertas; runbooks bajo `docs/refactor/`.

### Dependencies

Depends on: TASK-028, TASK-056

### Blocks

Blocks: TASK-058

### Parallelization

Can run in parallel with: NONE

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] El dominio público apunta al frontend y el navegador ve un solo origen.
- [ ] Existen alertas con umbral justificado y runbook para 5xx, p95, pool DB, 429, jobs vencidos y gasto IA.
- [ ] El rollback por revisión fue ejecutado en staging, no solo documentado.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Provocar cada condición de alerta en staging y comprobar que dispara y que el runbook resuelve. Ejecutar un rollback real y medir el tiempo hasta servicio restablecido. Verificar TLS y same-origin desde el navegador.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: HIGH
Performance: MEDIUM
Maintainability: HIGH
Cost: MEDIUM
Risk: MEDIUM

## TASK-058 — Ensayar el cutover y observar la ventana de estabilidad

Status: TODO
Priority: HIGH
Phase: PHASE-M5
Category: Infrastructure / Release

### Objective

Ensayar el cambio completo sobre una copia anonimizada o staging equivalente, ejecutarlo y observar el sistema antes de retirar nada.

### Problem

§5 de Fase 5 pide ensayo con copia anonimizada, congelación de cambios incompatibles, despliegue en orden migrate → API → frontend, canary si la configuración lo permite, y observación de autenticación, 4xx/5xx, latencia, jobs, cuotas IA y storage.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:370-381` (Confidence: HIGH).
- TASK-031 (pendiente): verificar compatibilidad integrada y ensayar rollout/restore.

### Why this is a problem

Un cutover que se ejecuta por primera vez en producción convierte cualquier supuesto equivocado en incidente. El ensayo es la única forma de descubrirlos con red debajo.

### Desired State

Un ensayo completo documentado, el cutover ejecutado en orden, y una ventana de observación con métricas sanas antes de autorizar el retiro de TASK-059.

### Proposed Solution

Extender TASK-031 en vez de duplicarla: aquella verifica compatibilidad integrada y ensaya rollout/restore sobre el monolito; esta lo hace sobre la topología de dos servicios. La copia es anonimizada; no se ensaya con PII real. Congelar cambios incompatibles durante la ventana. El canary es opcional según lo que la configuración permita, y su ausencia se documenta en vez de asumirse.

### Scope

IN SCOPE:

- Ensayo de cutover, ejecución en orden, ventana de observación y su informe.
- Congelación de cambios incompatibles durante la ventana.

OUT OF SCOPE:

- Retirar templates, JS legacy o endpoints deprecados: eso es TASK-059, después de esta observación.
- Ensayar con datos personales reales.
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- Runbooks e informe de cutover bajo `docs/refactor/`.
- Sin cambios de código salvo correcciones que el ensayo revele.

### Dependencies

Depends on: TASK-031, TASK-053, TASK-057

### Blocks

Blocks: TASK-059

### Parallelization

Can run in parallel with: NONE

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] El ensayo se ejecutó sobre copia anonimizada o staging equivalente y está documentado.
- [ ] El cutover siguió el orden migrate → API → frontend.
- [ ] La ventana de observación cerró con autenticación, 4xx/5xx, latencia, jobs, cuotas IA y storage sanos.
- [ ] El rollback siguió siendo posible durante toda la ventana.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Informe de la ventana con métricas antes y después. Verificar que el rollback fue posible en cada punto. Registrar cualquier incidente y su resolución. No declarar la ventana cerrada sin datos.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: HIGH
Performance: MEDIUM
Maintainability: MEDIUM
Cost: MEDIUM
Risk: HIGH

## TASK-059 — Retirar Jinja, templates, JS/CSS legacy y endpoints deprecados

Status: TODO
Priority: MEDIUM
Phase: PHASE-M5
Category: Cleanup / Structure

### Objective

Eliminar `app/views`, templates, JS y CSS legacy, la dependencia de Jinja, el montaje de StaticFiles y los endpoints deprecados, solo tras comprobar cero tráfico.

### Problem

§15 exige que FastAPI no importe Jinja, no monte `/static` y no sirva pantallas, y que el retiro ocurra después de comprobar cero tráfico. Mientras conviven las dos implementaciones, cada regla tiene dos hogares.

### Evidence / Location

- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:377-379, 484-486` (Confidence: HIGH).
- `docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md:174-185` (procedimiento de compatibilidad y retiro).
- 27 templates y 23 archivos JS en el snapshot inicial.

### Why this is a problem

Un retiro por apariencia de desuso borra código todavía servido a alguien. La medición de tráfico es la única evidencia que autoriza el borrado.

### Desired State

El repositorio sin la capa de presentación legacy, con la evidencia de cero tráfico archivada por endpoint retirado.

### Proposed Solution

Seguir el procedimiento de §5.3 endpoint por endpoint: deprecar en OpenAPI con cabeceras `Deprecation`/`Sunset`, medir durante al menos un ciclo de release, y solo entonces retirar. Los templates y el JS se borran por pantalla, no en bloque, y cada borrado cita la vertical que la sustituyó. Ningún DROP de tablas ni de columnas entra aquí: esto retira presentación y endpoints, no datos. Lo que no tenga evidencia de cero tráfico se queda y se registra como pendiente.

### Scope

IN SCOPE:

- Borrado de `app/views`, `app/templates`, `app/static` legacy, dependencia de Jinja y montaje de StaticFiles.
- Retiro de endpoints deprecados con evidencia de cero tráfico por endpoint.

OUT OF SCOPE:

- Eliminar tablas, columnas o datos: esto retira presentación y endpoints, nada más.
- Retirar cualquier cosa sin la medición de tráfico que la autoriza.
- Retirar `user_stats`, `communities.member_count` u otras columnas legacy documentadas: requieren tarea destructiva propia.
- Cambiar reglas de negocio, umbrales, pesos de scoring o permisos: la migración no autoriza cambios de producto.
- Inventar historia de datos, recalcular resultados históricos o activar pagos/envío real de email.
- Borrar tablas, columnas, objetos de storage o endpoints legacy sin comprobar cero tráfico y sin tarea de retiro específica.

### Files / Components Likely Affected

- `backend/app/views/`, `backend/app/templates/`, `backend/app/static/`, dependencias de Jinja, routers deprecados.

### Dependencies

Depends on: TASK-058

### Blocks

Blocks: NONE

### Parallelization

Can run in parallel with: NONE

### Implementation Notes

Leer [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) y la sección citada antes de editar. La paridad se demuestra contra la baseline capturada en TASK-035, no de memoria. Los hallazgos de [02_AUDIT_FINDINGS.md](02_AUDIT_FINDINGS.md) que toquen este dominio se corrigen aquí; no se portan bugs conocidos al código nuevo como si fueran diseño. Un cambio de comportamiento va rotulado Bug Fix y separado del movimiento estructural.

### Acceptance Criteria

- [ ] FastAPI no importa Jinja, no monta `/static` y no sirve pantallas.
- [ ] Cada endpoint retirado tiene su evidencia de cero tráfico archivada.
- [ ] Ninguna tabla, columna ni objeto de storage se eliminó en esta tarea.
- [ ] Lo que no pudo retirarse quedó registrado con su motivo.
- [ ] Existing behavior remains compatible (salvo Bug Fix explícito de esta tarea).
- [ ] Relevant tests pass.
- [ ] No unrelated refactor was introduced.

### Validation

Comprobar que la suite completa pasa tras cada borrado. Verificar por métricas que cada endpoint retirado tenía cero tráfico durante la ventana medida. Arrancar la aplicación y confirmar que no hay import de Jinja ni montaje de StaticFiles.

### Rollback / Risk Notes

Revertir solo los archivos de la tarea. Las correcciones de seguridad y los backfills ya integrados se conservan; preferir forward fix. Para cambios DB, expand/contract y restore verificado, nunca downgrade destructivo. Mientras el adapter legacy siga en pie, revertir el consumidor nuevo debe dejar la pantalla anterior funcionando.

### Estimated Impact

Security: MEDIUM
Performance: MEDIUM
Maintainability: HIGH
Cost: LOW
Risk: MEDIUM

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
- TASK-032 — Extender el mapeo de errores públicos a las rutas restantes; depends on TASK-011.

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

## PARALLEL EXECUTION GROUPS — plan 08 (fases M)

Los grupos anteriores (A–J) siguen describiendo las tareas TASK-001 a TASK-032 y no se renumeran.
Como allí, el grupo es una combinación conservadora: no hay barrera global, solo Dependencies y
exclusión de archivos.

### Parallel Group M0 — Baseline y decisiones

Can start when each task's concrete dependencies are COMPLETED (no barrera global del grupo previo):

- TASK-033 — Fijar toolchains y congelar la baseline de la migración; depends on NONE.
- TASK-034 — Inventariar rutas y construir la matriz legacy → REST; depends on NONE.
- TASK-035 — Capturar OpenAPI, fixtures y baseline visual de las pantallas actuales; depends on TASK-034.
- TASK-036 — Decidir y registrar el patrón de ingreso a Cloud Run; depends on NONE.

Nada de esto toca código de producción: se puede arrancar en paralelo con cualquier tarea de backend pendiente del plan anterior.

### Parallel Group M1 — Monorepo

Can start when each task's concrete dependencies are COMPLETED (no barrera global del grupo previo):

- TASK-037 — Mover el backend a backend/ sin cambiar comportamiento; depends on TASK-033, TASK-035.
- TASK-038 — Crear el scaffold React y el compose local con proxy same-origin; depends on TASK-037.
- TASK-039 — Separar CI en lanes de backend y frontend; depends on TASK-037, TASK-038.

TASK-037 reserva prácticamente todo el árbol Python: mientras esté IN PROGRESS no debe haber otra tarea editando `app/`. Serializar contra las tareas de backend pendientes en vez de mergear a ciegas.

### Parallel Group M2 — Plataforma REST y frontend

Can start when each task's concrete dependencies are COMPLETED (no barrera global del grupo previo):

- TASK-040 — Implantar el error model único y el request id en toda la API; depends on TASK-032, TASK-037.
- TASK-041 — Estandarizar paginación, límites de colección e idempotencia; depends on TASK-024, TASK-037.
- TASK-042 — Exponer sesión, login y logout por actor con CSRF double-submit; depends on TASK-010, TASK-037.
- TASK-043 — Fijar OpenAPI como contrato y generar tipos TypeScript en CI; depends on TASK-039, TASK-040, TASK-041.
- TASK-044 — Construir la capa HTTP, los shells y los guards del frontend; depends on TASK-038, TASK-042, TASK-043.
- TASK-045 — Publicar health, readiness y logging estructurado de la API; depends on TASK-028, TASK-037.

TASK-040, TASK-041, TASK-042 y TASK-045 tocan capas distintas del backend y pueden ir en paralelo. TASK-043 necesita que el contrato esté estable; TASK-044 consume sus tipos.

### Parallel Group M3 — Verticales

Can start when each task's concrete dependencies are COMPLETED (no barrera global del grupo previo):

- TASK-046 — Vertical 1 — Shell público y autenticación en React; depends on TASK-035, TASK-042, TASK-044.
- TASK-047 — Vertical 2 — Perfil, cuestionario y CV en React; depends on TASK-006, TASK-030, TASK-041, TASK-046.
- TASK-048 — Vertical 3 — Dashboard, recursos y roadmaps en React; depends on TASK-018, TASK-025, TASK-046.
- TASK-049 — Vertical 4 — Jobs, análisis de CV y candidaturas en React; depends on TASK-020, TASK-041, TASK-046, TASK-054.
- TASK-050 — Vertical 5 — Company: dashboard, postings, applicants, entrevistas y recruiters; depends on TASK-046.
- TASK-051 — Vertical 6 — Community, friendships y messages en React; depends on TASK-024, TASK-046.
- TASK-052 — Vertical 7 — Career Lab / Capstone en React; depends on TASK-022, TASK-023, TASK-046.
- TASK-053 — Vertical 8 — Admin en React; depends on TASK-047, TASK-048, TASK-049, TASK-050, TASK-051, TASK-052.

TASK-046 va primero y sola: fija el patrón. Después, las verticales pueden solaparse siempre que no compartan archivos de backend; TASK-053 cierra porque es el último consumidor legacy.

### Parallel Group M4 — Infraestructura Cloud Run

Can start when each task's concrete dependencies are COMPLETED (no barrera global del grupo previo):

- TASK-054 — Sacar el runner de CV del lifespan con outbox y Cloud Tasks; depends on TASK-013, TASK-037.
- TASK-055 — Aprovisionar Artifact Registry, WIF y Secret Manager; depends on TASK-002, TASK-036, TASK-039.
- TASK-056 — Desplegar los servicios Cloud Run, el Job de migraciones y deploy.yml por SHA; depends on TASK-009, TASK-045, TASK-054, TASK-055.
- TASK-057 — Configurar dominio, TLS, alertas, budgets y rollback por revisión; depends on TASK-028, TASK-056.

TASK-054 y TASK-055 son independientes entre sí y pueden adelantarse desde M2. TASK-056 y TASK-057 se serializan.

### Parallel Group M5 — Cutover y retiro

Can start when each task's concrete dependencies are COMPLETED (no barrera global del grupo previo):

- TASK-058 — Ensayar el cutover y observar la ventana de estabilidad; depends on TASK-031, TASK-053, TASK-057.
- TASK-059 — Retirar Jinja, templates, JS/CSS legacy y endpoints deprecados; depends on TASK-058.

Estrictamente secuencial. TASK-059 no empieza hasta que la ventana de observación de TASK-058 cerró con métricas sanas.

## DEPENDENCY GRAPH

Generado desde la Summary Table; si difieren, la tabla manda. `PHASE-0` a `PHASE-6` son el plan
anterior; `PHASE-M0` a `PHASE-M5`, la migración del plan 08. TASK-026 aparece como nodo por tener
ID estable, pero está SUPERSEDED y nadie debe reclamarla.

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
    T032["TASK-032"]
    T033["TASK-033"]
    T034["TASK-034"]
    T035["TASK-035"]
    T036["TASK-036"]
    T037["TASK-037"]
    T038["TASK-038"]
    T039["TASK-039"]
    T040["TASK-040"]
    T041["TASK-041"]
    T042["TASK-042"]
    T043["TASK-043"]
    T044["TASK-044"]
    T045["TASK-045"]
    T046["TASK-046"]
    T047["TASK-047"]
    T048["TASK-048"]
    T049["TASK-049"]
    T050["TASK-050"]
    T051["TASK-051"]
    T052["TASK-052"]
    T053["TASK-053"]
    T054["TASK-054"]
    T055["TASK-055"]
    T056["TASK-056"]
    T057["TASK-057"]
    T058["TASK-058"]
    T059["TASK-059"]
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
    T027 --> T031
    T028 --> T031
    T029 --> T031
    T030 --> T031
    T011 --> T032
    T034 --> T035
    T033 --> T037
    T035 --> T037
    T037 --> T038
    T037 --> T039
    T038 --> T039
    T032 --> T040
    T037 --> T040
    T024 --> T041
    T037 --> T041
    T010 --> T042
    T037 --> T042
    T039 --> T043
    T040 --> T043
    T041 --> T043
    T038 --> T044
    T042 --> T044
    T043 --> T044
    T028 --> T045
    T037 --> T045
    T035 --> T046
    T042 --> T046
    T044 --> T046
    T006 --> T047
    T030 --> T047
    T041 --> T047
    T046 --> T047
    T018 --> T048
    T025 --> T048
    T046 --> T048
    T020 --> T049
    T041 --> T049
    T046 --> T049
    T054 --> T049
    T046 --> T050
    T024 --> T051
    T046 --> T051
    T022 --> T052
    T023 --> T052
    T046 --> T052
    T047 --> T053
    T048 --> T053
    T049 --> T053
    T050 --> T053
    T051 --> T053
    T052 --> T053
    T013 --> T054
    T037 --> T054
    T002 --> T055
    T036 --> T055
    T039 --> T055
    T009 --> T056
    T045 --> T056
    T054 --> T056
    T055 --> T056
    T028 --> T057
    T056 --> T057
    T031 --> T058
    T053 --> T058
    T057 --> T058
    T058 --> T059
```
