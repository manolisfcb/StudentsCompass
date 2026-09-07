# Plan de refactorización incremental

Fecha: 2026-09-05. Revisión local: `6a2ea29`. Auditoría estática y pruebas aisladas; no se conectó a producción ni se modificó código productivo. Las líneas son referencias al snapshot y pueden desplazarse.

> **Nota (2026-09-07): la decisión de conservar Jinja de este plan fue reemplazada.**
> [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md) es el plan vigente para la
> arquitectura y la capa de presentación: monorepo `backend/` + `frontend/`, API JSON bajo `/api/v1`,
> SPA React y despliegue en Cloud Run. Las fases PHASE-0 a PHASE-6 de este documento siguen describiendo
> el trabajo de backend, que continúa siendo necesario; las fases PHASE-M0 a PHASE-M5 de
> [TASKS.md](TASKS.md) describen la migración. PHASE-5 de este plan quedó parcialmente afectada:
> TASK-026 está SUPERSEDED, TASK-023 sigue vigente.

## Cómo ejecutar

[TASKS.md](TASKS.md) es la única fuente de verdad de estados/dependencias. Esta narrativa no sustituye la ficha de cada tarea. No hay implementación productiva en esta entrega. La seguridad se corrige en PRs pequeñas tan pronto como su preparación esté lista; las fases no son barreras globales. Se conserva el comportamiento válido y cada corrección funcional está rotulada Bug Fix.

## PHASE-0 — Red mínima de seguridad y baseline DB

**Objetivo:** TASK-001 y TASK-009 crean pruebas aisladas y una estrategia de schema reproducible. TASK-002 es requisito de configuración segura de TASK-009, aunque pertenece al frente de seguridad.

**Por qué ahora:** SQLite/create_all no detecta migraciones destructivas ni carreras PostgreSQL. Una migración aplicada al destino equivocado sería más grave que el refactor que prepara.

**Prerequisitos:** repositorio y acceso a infraestructura de prueba; inventario de revisión/schema de despliegues antes de ejecutar su ruta de actualización. No se conecta a producción por defecto.

**Riesgos:** baseline ficticia que omite estado histórico; aplicar un stamp sin comprobar tablas; sobrescribir índices útiles por metadata incompleta.

**Terminado:** suite rápida reproducible, lane PostgreSQL/Redis, bootstrap vacío y upgrades desde estados documentados preservan datos; restore probado. No se marca la base real como migrada por haber probado una copia.

## PHASE-1 — Seguridad, gasto y ciclo de archivos

**Objetivo:** TASK-002 a TASK-008, TASK-010 y TASK-011 cierran secretos, IDOR, HTML inseguro, objetos colisionables, uploads, límites de IA, descargas de recursos, login compañía y exposición de errores.

**Por qué ahora:** son fronteras de confianza y riesgo de pérdida/coste. Ownership/HTML/guard pueden corregirse independientemente de refactors grandes.

**Prerequisitos:** TASK-001 para pruebas; TASK-005 espera baseline DB por intención durable de cleanup. TASK-007 antecede al ajuste de reglas de rate limit; TASK-011 espera los cambios de rutas de uploads/recursos.

**Riesgos:** bloquear uploads legítimos, invalidar configuración de proxy, romper enlaces legacy o confundir requests IA con gasto monetario.

**Terminado:** casos negativos y positivos cubiertos; secretos retirados y revocación documentada; no llamadas externas al rechazar; claves únicas; no gasto habilitado por fallback de configuración; tests de intento/retry exactos. Correcciones de seguridad no se revierten por un rollback genérico.

## PHASE-2 — Integridad y autoridades persistidas

**Objetivo:** TASK-012/TASK-013 formalizan ledger y jobs; TASK-014/TASK-015 centralizan estado e entrevistas; TASK-017 corrige contador de membresías; TASK-027 valida constraints/metadata después de las migraciones específicas que necesita.

**Por qué ahora:** antes de extraer servicios o acelerar escrituras debe estar claro qué operación es atómica y qué dato manda.

**Prerequisitos:** baseline y guard de gasto; dependencias concretas en tablero. TASK-027 puede acabar después de alguna optimización preparatoria: evita modificar el mismo model en paralelo.

**Riesgos:** atribuir historia sin evidencia, doble consumo por replay, interpretar dos rows legacy como duplicado eliminable, ampliar semántica de slots a agenda global.

**Terminado:** concurrencia PostgreSQL e inyección de fallos pasan; backfills idempotentes con parity y provenance; job recuperable tras reinicio; exactamente una reserva efectiva por candidatura y conteo coherente. Estado incierto del proveedor se trata explícitamente.

## PHASE-3 — Políticas canónicas de aprendizaje y cuestionario

**Objetivo:** TASK-016 unifica aprobación/progreso y códigos de recursos core; TASK-030 valida respuestas y versión histórica del cuestionario.

**Por qué ahora:** evita que UI/dashboard se conviertan en autoridad y protege scores válidos antes de reorganizar frontend.

**Prerequisitos:** reglas actuales caracterizadas, schema compatible y tareas de error/ledger/transiciones pertinentes completas.

**Riesgos:** confundir hecho manual con lección virtualmente aprobada, elegir recursos por título ambiguo o recalcular historia con pesos nuevos.

**Terminado:** mismos hechos producen mismo progreso en pantallas; umbral 8 conservado; GET no escribe caches; definición versionada respeta historia. Las diferencias antiguas se registran como Bug Fix, no se ocultan como refactor.

## PHASE-4 — Queries, event loop y medición

**Objetivo:** TASK-018/019 batching; TASK-020 scraper; TASK-021 cache embedding; TASK-022 solver; TASK-024 mensajes; TASK-025 dashboard; TASK-028 observabilidad.

**Por qué ahora:** políticas y contratos ya estables, así que se puede comparar resultados y costes. Algunas tareas independientes pueden adelantarse cuando el DAG lo permite.

**Prerequisitos:** baseline métrica, datos representativos sintéticos y tests de contrato. No usar tráfico real ni consultas de escritura en producción como benchmark.

**Riesgos:** paralelizar AsyncSession, crear colas sin límites, cache stale, cambiar orden/cursors o degradar recall vectorial.

**Terminado:** budgets verificables de SELECT/batch, calls por resultado, memoria/payload y lag; segundo análisis idéntico no regenera embedding; otras peticiones no se frenan por I/O/solver. Los listados no priorizados tienen medición y tareas específicas si exceden presupuesto; no se considera resuelta toda paginación solo por arreglar dashboard.

## PHASE-5 — Límites de responsabilidades

**Objetivo:** TASK-023 divide Capstone conservando facade; TASK-026 divide Jobs/Career Lab en API, estado y render.

**Por qué ahora:** mover archivos antes de corregir causas raíz trasladaría la complejidad sin reducirla y complicaría merges.

**Prerequisitos:** extracción/solver/jobs/progreso estables y contratos fijados; backend primero, consumers después.

**Riesgos:** duplicar implementaciones en facade/nuevo servicio, introducir framework innecesario o cambiar scoring/DOM en la misma PR.

**Terminado:** contratos/goldens/smokes compatibles, una implementación por regla, dependencias claras y sin nueva capa universal. Estado servidor invalidado tras mutación; navegación no acumula fetch/polling.

## PHASE-6 — Consolidación y verificación integrada

**Objetivo:** TASK-029 documenta/configura dependencias y limpia solo evidencia comprobada; TASK-031 ensaya integración/rollout/restore.

**Por qué al final:** los consumidores migrados permiten distinguir legacy de código todavía necesario. Las vulnerabilidades nuevas descubiertas en dependencias se elevan a tarea propia inmediatamente, no esperan al cleanup.

**Prerequisitos:** DAG completo de cambios pertinentes; versiones exactas de locks y acceso a advisory oficial al ejecutar ese análisis.

**Riesgos:** eliminar tablas/aliases por aparente desuso, actualizar todo el lock sin revisar compatibilidad, asumir que una prueba equivale a deploy real.

**Terminado:** suite rápida/integración, smokes por rol, parity y restore documentados; todas las tareas tienen Completion Notes reales o estado BLOCKED con evidencia pendiente. Ningún DROP genérico. El despliegue real es una operación posterior bajo el alcance autorizado de su ejecución.

## Medición y rollback común

Fijar input, versión de código, dataset y condiciones iguales. Registrar queries/request, latencia p50/p95, RAM pico, bytes, calls/resultado, commits/batch y job age según tarea. No imponer porcentaje arbitrario de mejora sin baseline. Criterios verificables como consultas constantes por lote o cero regeneraciones en warm path sí son exigibles. Para DB, expansión compatible y backfills reanudables; para código, revertir solo implementación mientras reader soporta datos nuevos. Secretos revocados y controles de autorización se preservan.

## Correspondencia hallazgos → tareas

| Finding | Tareas responsables |
| --- | --- |
| F-01 — Credenciales persistidas en archivos versionados | TASK-002 |
| F-02 — IDOR en borrado de publicaciones | TASK-003 |
| F-03 — HTML no escapado en lista de CV | TASK-004 |
| F-04 — Colisiones de objetos y borrado antes de confirmar DB | TASK-005 |
| F-05 — Límites de uploads incompletos | TASK-006 |
| F-06 — Techo global de IA no equivale a llamadas reales | TASK-007 |
| F-07 — Descarga de recursos autoriza por prefijo, no por publicación | TASK-008 |
| F-08 — Migraciones históricas destruyen datos y no arrancan desde vacío | TASK-009, TASK-031 |
| F-09 — Cobertura de rate limiting y confianza de proxy incompletas | TASK-010 |
| F-10 — Errores de infraestructura retornados al cliente | TASK-011 |
| F-11 — Estado de candidatura e historial divergen bajo rutas distintas y concurrencia | TASK-014 |
| F-12 — Reserva de entrevista vulnerable a carreras | TASK-015 |
| F-13 — Cuotas repartidas entre ledger, datos legacy y reservas efímeras | TASK-012 |
| F-14 — Jobs de CV efímeros y deduplicación check-then-insert | TASK-013 |
| F-15 — Progreso y aprobación tienen varias fuentes de verdad | TASK-016 |
| F-16 — member_count es un contador manual expuesto a desincronización | TASK-017 |
| F-17 — N+1 en progreso de recursos y extracción de skills por ofertas | TASK-018, TASK-019 |
| F-18 — I/O y solver síncronos en rutas async | TASK-020, TASK-022 |
| F-19 — Capstone concentra demasiadas responsabilidades | TASK-023, TASK-026 |
| F-20 — Deriva entre migraciones, metadata y tablas legacy | TASK-009, TASK-027 |
| F-21 — Embeddings recalculados aunque no cambie el contenido | TASK-021 |
| F-22 — Listados cargan historial completo | TASK-024, TASK-025 |
| F-23 — Constraints y reglas de dominio no siempre llegan a DB | TASK-019, TASK-027 |
| F-24 — Observabilidad limitada y pruebas no equivalentes a PostgreSQL | TASK-001, TASK-028, TASK-031 |
| F-25 — Cuestionario acepta respuestas desconocidas/duplicadas y lectura no versionada | TASK-030 |
| F-26 — Deuda documental, configuración duplicada y dependencias por verificar | TASK-029 |

Los grupos de ejecución paralela y DAG completos están al final de [TASKS.md](TASKS.md). Cada tarea contiene Evidence, Scope, Dependencies, Blocks, criterios de aceptación, validación y rollback; un agente puede comenzar por su ficha sin una explicación oral adicional.
