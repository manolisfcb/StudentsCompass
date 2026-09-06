# Hallazgos de auditoría

Fecha: 2026-09-05. Revisión local: `6a2ea29`. Auditoría estática y pruebas aisladas; no se conectó a producción ni se modificó código productivo. Las líneas son referencias al snapshot y pueden desplazarse.

Prioridad y confianza son ejes distintos. HIGH en confianza indica evidencia en código; no implica explotación observada. Costes/volúmenes de producción no medidos. Cada ID conserva una única prioridad.

## CRITICAL

### F-01 — Credenciales persistidas en archivos versionados

Priority: CRITICAL

Confidence: HIGH

**WHERE / Evidence:** `alembic.ini:90; scripts/migrate_sqlite_to_postgres.py:26; alembic/env.py:85`

**WHY / Síntoma y causa raíz:** SECRET DETECTED. La configuración de Alembic contiene una URL remota con usuario y contraseña; otro candidato aparece en el script de migración versionado. No se comprobó su vigencia. Además, Alembic usa sqlalchemy.url mientras la aplicación usa DATABASE_URL: pueden apuntar a bases distintas.

**WHAT / HOW:** Retirar literales, resolver explícitamente la URL de migración desde configuración segura y fallar si falta. Rotar/revocar las credenciales afectadas mediante el responsable de infraestructura; verificar consumidores antes del cambio. Revisar historial con salida redactada. No imprimir valores ni reescribir el historial automáticamente.

**Validación requerida:** Escaneo redactado sin coincidencias en el árbol; conexión exclusivamente a PostgreSQL desechable; comprobación de URL ausente y configuración app/migrador consistente; evidencia de revocación sin valores.

### F-02 — IDOR en borrado de publicaciones

Priority: CRITICAL

Confidence: HIGH

**WHERE / Evidence:** `app/routes/postRoute.py:83 delete_post; app/services/community/postService.py:36 delete_post`

**WHY / Síntoma y causa raíz:** La ruta exige autenticación pero no pasa user.id al servicio. El servicio busca solamente por post_id y borra el registro: cualquier usuario autenticado con un ID puede borrar publicaciones ajenas.

**WHAT / HOW:** Pasar el actor explícitamente y filtrar por post_id y user_id; responder 404 para ajeno/inexistente. Definir por separado el tratamiento de posts legacy con user_id nulo; no conceder privilegios administrativos implícitos.

**Validación requerida:** Prueba A crea, B intenta borrar y recibe 404 sin cambios; A borra; anónimo rechazado; registro inexistente no produce 500.

### F-03 — HTML no escapado en lista de CV

Priority: CRITICAL

Confidence: HIGH

**WHERE / Evidence:** `app/static/js/userProfile.js:433; app/routes/resumeRoute.py:80; app/services/resumes/resumeService.py:61`

**WHY / Síntoma y causa raíz:** original_filename procede del upload y se inserta directamente en tbody.innerHTML junto con view_url. Existe un sumidero de XSS almacenado; el listado comprobado pertenece al propio usuario, por lo que no se afirma explotación entre cuentas.

**WHAT / HOW:** Construir nodos con textContent, validar esquemas de URL http/https y usar atributos DOM seguros. Revisar los sumideros de URLs de jobs.js y resource_detail.js sin asumir que escapeHtml valida protocolos.

**Validación requerida:** Nombres con etiquetas, comillas y caracteres internacionales se muestran literalmente; enlaces javascript/data rechazados; flujo subir/listar/borrar conservado en navegador.

### F-04 — Colisiones de objetos y borrado antes de confirmar DB

Priority: CRITICAL

Confidence: HIGH

**WHERE / Evidence:** `app/services/resumes/resumeService.py:166,202; app/services/storage/s3Service.py:54; app/services/storage/mediaStorageService.py:75; app/models/resumeModel.py:14`

**WHY / Síntoma y causa raíz:** Los CV usan timestamp con precisión de segundos + nombre, sin usuario/UUID. S3 usa esa clave y put_object; media S3 usa directamente el nombre saneado. Dos cargas pueden compartir objeto. delete_resume borra almacenamiento antes del commit DB y no exige éxito del proveedor: un rollback puede dejar un registro cuyo archivo ya no existe.

**WHAT / HOW:** Claves nuevas opacas y únicas por objeto, con identidad del propietario o UUID. Mantener resolución de claves legacy. Implementar intención durable de borrado y reintentos idempotentes después de confirmar la decisión DB; compensar uploads cuyo alta DB falla. Inventariar referencias compartidas antes de eliminar cualquier objeto.

**Validación requerida:** Dos uploads con mismo nombre/instante tienen claves distintas; borrar uno no afecta al otro; inyección de fallo DB/storage no pierde archivos referenciados; reintento de borrado converge; comprobar referencias legacy.

### F-05 — Límites de uploads incompletos

Priority: CRITICAL

Confidence: HIGH

**WHERE / Evidence:** `app/routes/resumeRoute.py:31; app/routes/postRoute.py:58; app/services/storage/mediaStorageService.py:39,75; app/core/resume_analyzer/resume_text_extractor.py:32`

**WHY / Síntoma y causa raíz:** CV comprueba tamaño después de await cv.read(); Content-Length puede faltar y el parser multipart ya se ejecutó. Posts no aplica cota de bytes/tipo antes de leer o copiar a disco y enviar a terceros. Un límite de archivo comprimido tampoco limita DOCX descomprimido. Impacto potencial: RAM, disco y almacenamiento pagado.

**WHAT / HOW:** Definir presupuestos por ruta, lectura incremental hasta límite+1, límite de cuerpo en ingreso/ASGI antes del multipart, tipos y firmas permitidos y límites de expansión DOCX. Mantener MIME admitidos por el producto y respuestas 413/400 explícitas.

**Validación requerida:** Con/sin Content-Length y multipart chunked sobredimensionado se rechaza antes del proveedor; memoria acotada; archivo pequeño válido funciona; DOCX con expansión excesiva falla de forma controlada.

### F-06 — Techo global de IA no equivale a llamadas reales

Priority: CRITICAL

Confidence: HIGH

**WHERE / Evidence:** `app/services/ratelimit/counterStore.py:257 get_counter_store; app/services/ai/aiBudgetGuard.py:51; app/services/ai/cvAnalysisService.py:254; app/core/resume_analyzer/llm_model.py:116; app/core/resume_analyzer/resume_audit_llm.py:99`

**WHY / Síntoma y causa raíz:** Sin REDIS_URL o si falla la inicialización, se usa memoria incluso en producción: el presupuesto se multiplica por procesos y reinicios. El guard se llama una vez antes de evaluadores que reintentan: ask_llm_model permite hasta tres intentos por reserva global. El fail-closed sí existe para errores del store después de inicializarse.

**WHAT / HOW:** Exigir store compartido para gasto en producción o desactivar IA de forma segura; aplicar guard inmediatamente antes de cada intento del proveedor, con una sola ubicación y sin doble contabilización. Separar unidades de usuario, intentos y consumo monetario; no llamar a un número de requests un límite de dinero.

**Validación requerida:** Dos procesos comparten techo; Redis ausente/fallo de inicialización no habilita gasto; tres intentos consumen tres unidades globales; kill switch y fallos transitorios/no reintentables preservan respuestas compatibles.

### F-07 — Descarga de recursos autoriza por prefijo, no por publicación

Priority: CRITICAL

Confidence: HIGH

**WHERE / Evidence:** `app/routes/resourceRoute.py:33; app/services/resources/resourceService.py:253 download_resource_file; app/services/resources/resourceService.py:118 get_published_resource`

**WHY / Síntoma y causa raíz:** /resources/file acepta cualquier key bajo resources/ para un usuario activo y no resuelve recurso/lección ni verifica is_published/is_locked. En contraste, el acceso al recurso sí usa esas restricciones. Conocer una clave permite saltarse el control del catálogo; acceso real depende de objetos existentes.

**WHAT / HOW:** Resolver la clave a una lección/recurso permitido antes de leer storage, o introducir endpoint por lesson_id con compatibilidad controlada para enlaces previos. La mera pertenencia al prefijo no concede acceso.

**Validación requerida:** Archivos de recurso publicado y desbloqueado accesibles; bloqueado/no publicado/clave sin asociación devuelve 404; ninguna descarga al proveedor en rechazo; conservar enlaces autorizados.

### F-08 — Migraciones históricas destruyen datos y no arrancan desde vacío

Priority: CRITICAL

Confidence: HIGH

**WHERE / Evidence:** `alembic/versions/025e4d7c446f_add_first_name_last_name_nickname_to_.py:21; alembic/versions/4897b7743b34_add_companies_table.py:24; alembic/versions/73a6e7c411b9_add_job_postings_and_update_.py:45`

**WHY / Síntoma y causa raíz:** La raíz añade columnas a users sin crearlo. Un upgrade elimina job_analysis; otro elimina y recrea applications. No se afirma que producción haya perdido datos, pero ejecutar esta cadena sobre una base heredada o vacía es inseguro/no reproducible.

**WHAT / HOW:** Diseñar baseline verificable para instalaciones nuevas y ruta forward-only para estados existentes, inventariando alembic_version y schema primero. No editar/reaplicar revisiones desplegadas ni ejecutar upgrade/downgrade real durante la auditoría. Proteger restores y pruebas de preservación antes de migrar.

**Validación requerida:** Restaurar copia desechable, verificar conteos/checksums y FKs antes/después; probar bootstrap vacío y upgrades desde estados soportados; dry-run de rollback/restore documentado sin DROP accidental.

### F-09 — Cobertura de rate limiting y confianza de proxy incompletas

Priority: CRITICAL

Confidence: HIGH

**WHERE / Evidence:** `app/middleware/rate_limit.py:111 from_env; app/routes/companyRoute.py:199,205; Dockerfile:8`

**WHY / Síntoma y causa raíz:** El limitador cubre login/registro de estudiantes pero no /api/v1/auth/company/login ni registro de compañía. Docker confía en cualquier proxy mediante FORWARDED_ALLOW_IPS=*. El bypass de IP depende de que el contenedor sea alcanzable directamente, algo no verificado.

**WHAT / HOW:** Añadir reglas explícitas para autenticación de compañías y flujos de recuperación; declarar proxies permitidos según despliegue y probar IP resuelta. Conservar cookies HttpOnly/SameSite actuales; centralizar solo configuración realmente compartida.

**Validación requerida:** Límites efectivos para ambas identidades; pruebas de X-Forwarded-For desde peer no confiable; revisar ingreso real antes de cerrar configuración; login legítimo conserva contrato.

### F-10 — Errores de infraestructura retornados al cliente

Priority: CRITICAL

Confidence: HIGH

**WHERE / Evidence:** `app/routes/resumeRoute.py:93; app/routes/questionnaireRoute.py:41; app/routes/resourceRoute.py:46; app/routes/adminRoute.py:369`

**WHY / Síntoma y causa raíz:** Varias rutas retornan str(e), incluyendo excepciones de storage/DB. Pueden revelar nombres internos, queries o parámetros; no se observó un error real que expusiera una credencial.

**WHAT / HOW:** Mapear errores esperados a códigos estables y mensaje público seguro; registrar causa con identificador de correlación y redacción. Añadir rollback donde un fallo deja la sesión transaccional inválida.

**Validación requerida:** Excepción simulada con marcador sensible no aparece en body/log público; 4xx conservados; 500 genérico con correlación; no continuar usando sesión fallida.

## HIGH

### F-11 — Estado de candidatura e historial divergen bajo rutas distintas y concurrencia

Priority: HIGH

Confidence: HIGH

**WHERE / Evidence:** `app/services/applications/applicationService.py:168,390; app/services/jobs/interviewService.py:67; app/models/applicationAnalyticsModel.py:46; app/schemas/applicationSchema.py:11`

**WHY / Síntoma y causa raíz:** ApplicationService registra eventos y agregados, pero InterviewService escribe INTERVIEW directamente. El agregado usa leer-modificar-escribir sin bloqueo/upsert y puede perder incrementos o chocar al crearse. Model y schema duplican enums.

**WHAT / HOW:** Crear una operación de transición de estado reutilizable con actor, evento y delta en la misma transacción; usar incremento SQL atómico/upsert y bloqueo/versionado del estado. Mantener applications.status como estado actual y eventos como historial autoritativo desde un punto de corte documentado.

**Validación requerida:** Publicar entrevista genera exactamente un evento coherente; 20 transiciones concurrentes conservan conteos; replay de comando no duplica eventos; snapshots de enums/payloads compatibles.

### F-12 — Reserva de entrevista vulnerable a carreras

Priority: HIGH

Confidence: HIGH

**WHERE / Evidence:** `app/services/jobs/interviewService.py:113 select_user_availability; app/models/interviewAvailabilityModel.py:18`

**WHY / Síntoma y causa raíz:** Se lee AVAILABLE, se marca BOOKED y se cancelan alternativas sin serializar por candidatura. Dos selecciones concurrentes pueden producir conflicto, más de una confirmación o logs duplicados; la DB no impone una única reserva por candidatura.

**WHAT / HOW:** Bloquear candidatura antes de publicar/seleccionar, imponer unicidad parcial de BOOKED por application_id tras revisar duplicados y hacer idempotente elegir de nuevo el mismo slot. No introducir agenda global: los slots actuales pertenecen a candidaturas.

**Validación requerida:** Dos sesiones seleccionando slots distintos dejan exactamente uno BOOKED y una transición efectiva; reintento mismo slot devuelve estado existente; migración detecta conflictos sin descartarlos.

### F-13 — Cuotas repartidas entre ledger, datos legacy y reservas efímeras

Priority: HIGH

Confidence: HIGH

**WHERE / Evidence:** `app/services/ai/aiUsageService.py:124,167,208,240; app/services/resumes/resumeCourseAuditService.py:120; app/models/aiUsageModel.py:12`

**WHY / Síntoma y causa raíz:** get_used_today usa max(ledger_count, legacy_count), no conciliación por identidad. La reserva vive en Redis/memoria y commit_usage solo agrega/flush; no existe clave única por referencia. Upload, alta de evaluación y extracción suceden fuera del try que libera reserva. Puede haber cuota retenida, estados parciales y contabilidad ambigua.

**WHAT / HOW:** Definir ledger autoritativo con referencia idempotente, ciclo de reserva durable y conciliación explícita legacy. Diferenciar gasto del proveedor y derecho de usuario; liberar solo cuando la política lo permite. Transacción coherente para resultado y consumo; cubrir todos los fallos previos y posteriores.

**Validación requerida:** Fallo en upload/extracción/flush/commit/cancelación deja estado recuperable; replay no duplica ledger; backfill por referencia con conteos por usuario/feature/día; no cambiar cuota histórica sin evidencia.

### F-14 — Jobs de CV efímeros y deduplicación check-then-insert

Priority: HIGH

Confidence: HIGH

**WHERE / Evidence:** `app/routes/jobRoute.py:275,302; app/services/ai/cvAnalysisService.py:103,115,179,339; app/models/jobAnalysisModel.py:18; app/static/js/jobs.js:800`

**WHY / Síntoma y causa raíz:** get_running_analysis seguido de create_pending_analysis no es atómico; BackgroundTasks no sobrevive al proceso. Un job PROCESSING sin recuperación bloquea nuevos análisis y el frontend deja de consultar tras 20 intentos de 3 s. El fallo de sesión puede impedir marcar FAILED sin rollback.

**WHAT / HOW:** Usar job_analysis como cola durable pequeña con claim atómico, lease y recuperación; evitar Redis como segunda cola si DB basta. Índice parcial para job activo por usuario/CV, reintentos acotados y consulta de estado tras recarga. Separar reejecución idempotente de repetir gasto externo.

**Validación requerida:** Dos POST simultáneos devuelven el mismo trabajo efectivo; reinicio tras claim recupera o falla explícitamente; probar antes/después de gasto; no duplicar llamadas confirmadas; mantener respuesta job_id/status.

### F-15 — Progreso y aprobación tienen varias fuentes de verdad

Priority: HIGH

Confidence: HIGH

**WHERE / Evidence:** `app/services/resources/resourceService.py:149,174; app/services/applications/dashboardService.py:277,307,387,512; app/core/resume_analyzer/resume_audit_llm.py:121; app/services/applications/applicationService.py:43; app/services/roadmaps/roadmapService.py:246`

**WHY / Síntoma y causa raíz:** ResourceService completa virtualmente lecciones de CV por evaluación aprobada; dashboard cuenta solo filas de progress y sincroniza user_stats durante lecturas. El fallback usa porcentajes fijos. Aprobación de score >=8 se repite y recursos solo consulta pass_status. user_stage_progress también es derivado de tareas.

**WHAT / HOW:** Centralizar elegibilidad de CV y proyección de progreso; distinguir resource_lesson_progress y evaluaciones como hechos, user_stats/user_stage_progress como proyecciones. Identificar cursos core por código estable, no título editable. Preservar DTO y separar corrección de porcentajes de extracción estructural.

**Validación requerida:** Mismo usuario obtiene mismos porcentajes en dashboard/recurso; evaluación aprobada sin fila de progreso coherente; score 7.99/8, múltiples evaluaciones y CV borrado; lecturas no escriben stats; parity report legacy antes del switch.

### F-16 — member_count es un contador manual expuesto a desincronización

Priority: HIGH

Confidence: HIGH

**WHERE / Evidence:** `app/models/communityModel.py:22; app/services/community/communityService.py:96,124,152`

**WHY / Síntoma y causa raíz:** La membresía tiene unique(community_id,user_id) pero member_count usa incrementos/decrementos Python; las altas/bajas simultáneas pueden perder cambios. Cascadas de usuarios también alteran miembros sin actualizar el contador.

**WHAT / HOW:** community_members será autoritativa. Preferir COUNT agrupado con índice existente si benchmark lo permite; de conservar caché, actualización atómica y reconstrucción/reconciliación explícita. No fusionar tabla de membresías con comunidades.

**Validación requerida:** Altas/bajas simultáneas y eliminación de usuario mantienen count igual a COUNT(*); repetición de join/leave tiene resultado estable; medir consultas/latencia con catálogo representativo.

### F-17 — N+1 en progreso de recursos y extracción de skills por ofertas

Priority: HIGH

Confidence: HIGH

**WHERE / Evidence:** `app/services/resources/resourceService.py:267; app/services/resources/resourceService.py:149; app/services/analytics/capstoneAnalyticsService.py:185,238`

**WHY / Síntoma y causa raíz:** list_user_enrollment_progress consulta completados y lecciones por cada recurso, con otra query si hay lección de CV. Extracción batch comparte lookup, pero consulta links y hace commit por oferta. No atribuir N+1 a messageService: allí ya hay batching.

**WHAT / HOW:** Cargar progreso de todos los resource_ids en consultas agrupadas, evaluación aprobada una vez; para ofertas prefetch de links y escritura por lotes acotados. Conservar orden y conteos semánticos existentes.

**Validación requerida:** Instrumentar 1/10/100 recursos: consultas de lectura constantes por batch. Para ofertas 10/100/500, commits por batch, no por oferta, misma salida y reejecución sin links duplicados.

### F-18 — I/O y solver síncronos en rutas async

Priority: HIGH

Confidence: HIGH

**WHERE / Evidence:** `app/services/jobs/jobSearchService.py:69,84; app/core/JobsScraper/linkedin_scraper.py fetch_linkedin_jobs; app/services/analytics/learningRouteOptimizerService.py:409,571`

**WHY / Síntoma y causa raíz:** search async llama requests.get y time.sleep directamente por el scraper. CP-SAT Solve también se ejecuta en el event loop (con límite real de 1 s y un worker, que conviene conservar). Una petición puede frenar otras del mismo worker.

**WHAT / HOW:** Ejecutar scraper y solver sobre ejecutores acotados o cliente HTTP async; no compartir AsyncSession entre threads. Mantener tiempos/límites, incorporar timeout total/cancelación y medir antes de añadir caché de búsquedas.

**Validación requerida:** Con proveedor falso lento, endpoint liviano sigue respondiendo y lag del loop queda acotado; misma lista/orden/fallback; no más de N trabajos activos y cola limitada; benchmark solver sin DB en thread.

### F-19 — Capstone concentra demasiadas responsabilidades

Priority: HIGH

Confidence: HIGH

**WHERE / Evidence:** `app/services/analytics/capstoneAnalyticsService.py:1; app/static/js/career_lab.js:1; app/static/js/jobs.js:1; app/routes/companyRoute.py:48`

**WHY / Síntoma y causa raíz:** CapstoneAnalyticsService tiene 1393 líneas y mezcla extracción, revisión, catálogo, métricas, embeddings, recomendaciones, optimización y persistencia. career_lab.js 1304 y jobs.js 1284 combinan fetch, estado, reglas/presentación y eventos. Longitud es indicio acompañado por esas responsabilidades, no criterio aislado.

**WHAT / HOW:** Mantener facade y rutas; extraer use cases de skills, catálogo y análisis/optimización con contratos concretos. En JS separar acceso API, estado del flujo y rendering por pantalla, sin cambiar a React ni introducir repositorios universales.

**Validación requerida:** Characterization de gap/optimización/revisión conserva JSON y resultados deterministas; smoke de Career Lab y Jobs mantiene estado, errores y navegación; imports unidireccionales sin nuevos ciclos.

### F-20 — Deriva entre migraciones, metadata y tablas legacy

Priority: HIGH

Confidence: HIGH

**WHERE / Evidence:** `alembic/env.py:9; alembic/versions/6e4bc7a18f21_add_resource_enrollment_and_progress_tables.py:49; alembic/versions/8c1d4a2b9f77_add_resource_lesson_progress_table.py; app/models/resourceModel.py:83`

**WHY / Síntoma y causa raíz:** Dos ramas crean resource_lesson_progress con shapes diferentes; una incluye resource_id NOT NULL y otra no. CREATE condicional no reconcilia columnas. resource_enrollments existe en migración sin model/caller actual. Alembic no importa explícitamente roadmapModel; autogenerate puede omitirlo. Hay índices en migraciones ausentes en metadata.

**WHAT / HOW:** Con baseline de F-08, comparar schema real con metadata completa, crear migración de convergencia sin pérdida y manifest de import de modelos. resource_id puede derivarse de lesson→module; rellenar/verificar antes de retirarlo en fase posterior. Mantener enrollments hasta conocer consumidores/datos.

**Validación requerida:** Comparación PostgreSQL introspectada; ambas shapes convergen; insertar progreso con código actual funciona; autogenerate tras upgrade no propone DROP de tablas activas ni elimina índices funcionales.

## MEDIUM

### F-21 — Embeddings recalculados aunque no cambie el contenido

Priority: MEDIUM

Confidence: HIGH

**WHERE / Evidence:** `app/services/analytics/capstoneAnalyticsService.py:476,694; app/services/analytics/embeddingService.py:128,156`

**WHY / Síntoma y causa raíz:** analyze_gap sincroniza embedding de resumen; upsert genera antes de consultar y hace commit incluso si texto/modelo no cambiaron. El default es hash local; no se demostró gasto en API de embeddings. Con modelo local el coste CPU/RAM es mayor.

**WHAT / HOW:** Persistir fingerprint de texto normalizado+modelo+versión; saltar generación y write si coincide. Guardar explícitamente modelo efectivo; conservar separación hash-v1/modelo semántico y no prometer equivalencia de calidad.

**Validación requerida:** Segunda petición idéntica: cero regeneraciones/writes; cambio de texto/modelo invalida; fallback no mezcla espacios; medir CPU, RSS, writes y p95 con ambos proveedores.

### F-22 — Listados cargan historial completo

Priority: MEDIUM

Confidence: HIGH

**WHERE / Evidence:** `app/services/community/messageService.py:171; app/services/community/postService.py:30; app/services/resumes/resumeService.py:105; app/services/applications/applicationService.py:127; app/services/applications/dashboardService.py:266; app/services/resources/resourceService.py:85`

**WHY / Síntoma y causa raíz:** Mensajes/posts/CV/candidaturas sin paginación; dashboard materializa candidaturas y cuenta/ordena en Python. Recursos filtra catálogo en memoria. Impacto crece con historial; no hay volúmenes ni EXPLAIN de producción para afirmar scans lentos.

**WHAT / HOW:** Empezar por mensajes con cursor (created_at,id); endpoints/consumidores compatibles durante transición. Dashboard usar agregados SQL y LIMIT para recientes. No añadir cachés a PII. Paginar otros listados tras medir y migrar todos sus callers.

**Validación requerida:** Datos 100/10000 filas: payload por página acotado, sin duplicados/omisiones entre fechas iguales; totales y top5 iguales; memoria y consultas antes/después documentadas.

### F-23 — Constraints y reglas de dominio no siempre llegan a DB

Priority: MEDIUM

Confidence: HIGH

**WHERE / Evidence:** `app/models/skillModel.py:64,85,114; app/models/interviewAvailabilityModel.py:18; app/models/resourceModel.py:42; app/services/analytics/capstoneAnalyticsService.py:207`

**WHY / Síntoma y causa raíz:** job_skills no tiene unicidad por oferta/skill/método; check-then-insert permite duplicados concurrentes. Estados de resume_skills son strings sin CHECK; rangos de score/cost/duration y orden de módulos/lecciones no están protegidos por constraints equivalentes. Float es aproximado para costes de optimización, no un libro de pagos.

**WHAT / HOW:** Priorizar unicidad de links de oferta y CHECK de estados/rangos tras inventario. Definir índices diferentes para requisitos por rol con job_posting_id NULL. No deduplicar evidencia de métodos distintos ni convertir Float monetario sin parity de solver.

**Validación requerida:** Queries de duplicados/NULL/rangos en copia; backfill conserva provenance; inserciones inválidas rechazadas y válidas pasan; EXPLAIN antes/después para índices adicionales; no marcar índices unused sin estadísticas.

### F-24 — Observabilidad limitada y pruebas no equivalentes a PostgreSQL

Priority: MEDIUM

Confidence: HIGH

**WHERE / Evidence:** `app/logging.py:1; tests/conftest.py:51,79; pytest.ini; pyproject.toml; app/services/applications/dashboardService.py:420`

**WHY / Síntoma y causa raíz:** Logs sin correlación uniforme, duración/query count/calls externos; algunos catch retornan vacío. Tests crean metadata en SQLite, no ejecutan Alembic ni reproducen locks, índices parciales/pgvector y restricciones Postgres. No se encontraron workflows CI versionados.

**WHAT / HOW:** Conservar suite rápida; añadir lane PostgreSQL+pgvector/Redis desechables y pruebas de carreras/migraciones. Correlacionar fallos por IDs opacos y medir latencia, queries e intentos sin texto CV, tokens ni URLs firmadas.

**Validación requerida:** CI reproduce suite rápida e integración; fallos inyectados visibles sin PII; dashboards mínimos p50/p95/errores/job age/budget denials; documentar herramientas lint/typecheck antes de exigir comandos inexistentes.

### F-25 — Cuestionario acepta respuestas desconocidas/duplicadas y lectura no versionada

Priority: MEDIUM

Confidence: HIGH

**WHERE / Evidence:** `app/services/accounts/questionnaireService.py:19,33,75; app/schemas/questionnaireSchema.py:36; app/models/questionnaireModel.py:8`

**WHY / Síntoma y causa raíz:** submit suma cada respuesta sin unicidad ni pertenencia validada; IDs desconocidos aportan cero en silencio y repetidos suman varias veces. El perfil lee la definición actual aunque el resultado persistido guarda version.

**WHAT / HOW:** Validar contra definición versionada: IDs válidos y unicidad según tipo de pregunta. Conservar answers/results como snapshot histórico ligado a versión inmutable; no recalcular resultados anteriores con el JSON actual.

**Validación requerida:** Respuesta válida conserva scores; duplicado/desconocido devuelve 422; perfil de versión anterior usa definición anterior; cualquier política de preguntas opcionales queda explícita.

## LOW

### F-26 — Deuda documental, configuración duplicada y dependencias por verificar

Priority: LOW

Confidence: HIGH

**WHERE / Evidence:** `app/config.py; app/db.py:16; app/services/accounts/userService.py:24; app/services/companies/companyService.py:21; pyproject.toml:13; app/models/resourceModel.py:36; .gitignore; README.md`

**WHY / Síntoma y causa raíz:** ENV/helpers de configuración repetidos; extra sqlchemy mal escrito en fastapi-users; comentario TODO de progreso contradice tabla existente. scripts está ignorado aunque seis scripts ya están versionados. Hay imports locales TYPE_CHECKING que parecen ciclos: no se confirmó ciclo de ejecución.

**WHAT / HOW:** Unificar parsing compartido sin un framework de settings adicional; corregir metadatos/documentación; inventariar imports y consumidores antes de retirar apify/drivers/aliases. Comparar uv.lock con requirements usado por Docker y consultar advisories vigentes al ejecutar tarea; no afirmar CVE sin evidencia.

**Validación requerida:** Instalación reproducible con locks; smoke de arranque; escaneo de imports/callers y documentación actualizada; ningún paquete/tabla eliminado solo por heurística.

## Cobertura y límites de la búsqueda

Se inspeccionaron rutas, servicios, modelos, migraciones, schemas, JS, configuración, Docker, tests y documentación. Se inventariaron 47 tablas ORM y una tabla adicional solo en migraciones. No se inspeccionaron cuentas cloud, ACL de buckets, RLS desplegada, tráfico, logs de producción ni historial Git completo. No hubo pentest remoto ni auditoría de advisories en línea. No se afirma cobertura exhaustiva de todas las vulnerabilidades.

- SQL: las consultas revisadas emplean ORM/parámetros (incluido bindparam en dashboard); no se confirmó SQL injection. No recomendar un ORM nuevo.
- SSRF: scraper construye host fijo de LinkedIn y storage usa claves, no URL arbitraria del usuario. No se confirmó SSRF.
- XSS: F-03 confirmado como flujo de datos hacia HTML; no confundir escape HTML con validación del esquema de URL.
- CSRF: cookies SameSite=Lax y JSON reducen superficie; no se probó comportamiento cross-site en despliegue. Revisar Origin/CSRF en formularios mutadores dentro de TASK-010; no se declara explotación.
- Autorización: existen controles de propietario CV, membership de mensajes, tenant de compañía y superuser de admin/Capstone. F-02 y F-07 son excepciones concretas.
- RLS: no declarada en migraciones revisadas. En un backend único sin acceso directo del navegador a DB no es automáticamente un fallo; las políticas sensibles deben seguir en el backend. Grants/roles reales: Confidence: LOW, pendiente de inventario operativo.
- Secretos: búsqueda por patrones en archivos versionados; valores omitidos. `.env` local está ignorado; presencia local no demuestra exposición. No se copiaron sus valores ni se usaron para pruebas.
- Dependencias: no CVE confirmado. `uv.lock` y requirements existen; revisión actual de vulnerabilidades queda como tarea explícita.
- No hay evidencia de pagos reales, suscripciones, cobros, webhooks de pago, cron o cola externa. Las notificaciones actuales son registros mock. No crear tareas de Stripe ni microservicios.
- Los porcentajes mock y match_strength basado en hash son comportamiento existente: reemplazarlos por scoring real sería cambio de producto separado.

## Performance Hotspots

| Hotspot | Location | Type | Expected Impact | Priority | Recommended Fix |
| --- | --- | --- | --- | --- | --- |
| Progreso por recurso | resourceService.py:267 | N+1 | crecimiento lineal de round trips por catálogo | HIGH | batch de hechos/progreso, TASK-018 |
| Extracción por oferta | capstoneAnalyticsService.py:238 | N+1 / DB round trips | SELECT/commit por oferta hasta límite 500 | HIGH | prefetch e idempotencia de links, TASK-019 |
| LinkedIn síncrono | jobSearchService.py:84 | network | bloquea event loop durante requests/sleeps | HIGH | executor limitado/HTTP async, TASK-020 |
| CP-SAT síncrono | learningRouteOptimizerService.py:409 | CPU | hasta 1 s de solver más construcción en loop | HIGH | ejecución acotada fuera de loop, TASK-022 (subtarea MEDIUM por límite existente) |
| Upsert de vector sin fingerprint | embeddingService.py:128 | CPU / DB round trips | encode/write repetidos; coste depende de proveedor | MEDIUM | fingerprint versionado, TASK-021 |
| Historial de mensajes | messageService.py:171 | memory / serialization | payload proporcional a todo el historial | MEDIUM | cursor estable, TASK-024 |
| Dashboard materializado | dashboardService.py:266 | memory / DB round trips | rows completas para métricas y top5 | MEDIUM | agregados SQL/LIMIT, TASK-025 |
| Polling de CV | jobs.js:800 | polling | hasta 20 requests por inicio, ya acotado | MEDIUM | recuperación/backoff en TASK-026 cuando se mida |
| Uploads/archivos | resumeRoute.py:31; mediaStorageService.py:75 | memory / storage | RAM/disco y storage sin cota completa | CRITICAL | límites pre-parser y lectura incremental, TASK-006 |

Un hotspot no es otro finding independiente: hereda la causa raíz referenciada. No se midió latencia/coste real de producción. Clasificación de tarea preparatoria puede diferir del finding que ayuda a resolver.
