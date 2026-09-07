# Fuentes de verdad y lógica duplicada

Fecha: 2026-09-05. Revisión local: `6a2ea29`. Auditoría estática y pruebas aisladas; no se conectó a producción ni se modificó código productivo. Las líneas son referencias al snapshot y pueden desplazarse.

AUTHORITATIVE DATA es el hecho o decisión persistida que gobierna el concepto. DERIVED / CACHE / DENORMALIZED DATA se puede reconstruir desde esa autoridad, conservando versión o punto de corte cuando sea necesario. Dos tablas relacionadas no son automáticamente duplicadas.

| Domain Concept | Current Sources | Recommended Source of Truth | Derived/Cached Data | Migration Needed |
| --- | --- | --- | --- | --- |
| Identidad estudiante | users, JWT cookie, payloads JS | users y verificación de sesión backend | JWT temporal y DTO de perfil | configuración, no fusionar identidades |
| Organización y recruiter | companies, company_recruiters | companies organización; company_recruiters identidad/rol | DTO empresa y actor actual | verificar migración legacy aplicada |
| Respuesta de cuestionario | JSON v2, answers/version/results | answers con definición inmutable por versión | results snapshot del cálculo histórico | versionar lectura; no recalcular historia |
| Documento CV | resumes.storage_file_id/folder_id/view_url y objeto S3 | objeto identificado por clave única + registro resumes | URL de acceso generada | expandir identidad/cleanup sin mover legacy ciegamente |
| Resumen IA de CV | resumes.ai_summary, job_analysis.summary | resultado de análisis seleccionado y ligado a CV/versión | resumes.ai_summary como proyección | backfill relación verificable; conservar texto histórico |
| Elegibilidad de CV | evaluación COMPLETED + `app/services/learning/resumeApproval.py` (TASK-016) | evaluación COMPLETED versionada + policy score >=8 | pass_status derivado del score al guardar; copy UI descriptivo | RESUELTO: umbral escrito una vez; `pass_status` no puede contradecir al score |
| Cuota usuario | ai_usage_events, conteos job_analysis/evaluations, CounterStore | ledger por referencia idempotente + grants | contador compartido y resumen diario | backfill por referencia, no max indefinido |
| Gasto IA global | CounterStore diario, reintentos evaluadores | registro/control de intentos del proveedor | contadores globales con retención definida | guard por intento y reconciliación de reservas |
| Job CV activo | job_analysis y BackgroundTasks | job_analysis con claim/lease/estado | ejecución del runner y polling UI | índice de activo y recuperación |
| Estado candidatura | applications.status, eventos, agregados | applications.status actual; eventos para historial desde corte | application_daily_aggregates | transición única; reconstruir solo historia disponible |
| Match candidatura | hash en ApplicationService | mantener regla mock declarada | match_strength persistido | no sustituir por Capstone sin tarea de producto |
| Entrevista elegida | estados slots, DTO selected_interview_slot | una fila BOOKED por candidatura | DTO seleccionado/lista disponible | bloqueo + unicidad tras resolver duplicados |
| Miembros comunidad | community_members, communities.member_count | community_members | member_count derivado o cache reconciliable | comparar y switch; conservar respuesta |
| Progreso de recursos | `resource_lesson_progress` + evaluación aprobada, vía `CourseProgressProjector` (TASK-016) | hechos de lección + evaluación según policy común | porcentajes; `user_stats` legacy solo-lectura | RESUELTO: una proyección para curso y dashboard; GET no escribe |
| Recursos core | `resources.core_code` (TASK-016), título solo como fallback documentado | código estable de recurso | título y copy traducible | RESUELTO: backfill por inventario, índice único; títulos ambiguos quedan sin asignar |
| Progreso roadmap | user_task_progress, user_stage_progress | tareas completadas; proyecto separado | user_stage_progress y porcentajes | VERIFICADO (TASK-016): `user_stage_progress` se escribe solo al actualizar una tarea, nunca en GET, y sigue separado de los cursos |
| Skills CV | resume_skills por método y estado | evidencia/provenance y revisión manual | selección best_by_skill_id | conservar diferentes métodos, CHECK e idempotencia |
| Requisitos de rol | job_skills de ofertas y job_skills con posting NULL | separar lógicamente requisitos observados y fallback de rol | agregaciones de demanda | unicidad adecuada a cada caso; no fusionar evidencias |
| Catálogo de cursos | courses, resources opcional | courses oferta/constraints; resources contenido local | nombres/URL proyectados si linked | revisar sincronización; mantener ambos |
| Embeddings | resume_embeddings y generación por análisis | texto versionado + modelo efectivo | vector con fingerprint | backfill/invalidation, no compartir hash con modelo semántico |
| Optimización | optimization_runs y scoring de runtime | snapshot con objective_version, entradas y constraints | visualización de resultados | conservar reproducibilidad; no recalcular snapshots silenciosamente |
| Notificaciones | email_notification_logs | registro mock explícito | sent_at mock no prueba entrega | no activar envío real en refactor |

## Matriz de lógica duplicada

| Business Rule | Locations | Current Implementations | Risk | Canonical Destination |
| --- | --- | --- | --- | --- |
| CV aprobado | `app/services/learning/resumeApproval.py` (TASK-016); `resource_detail.js:525` copy | una policy backend; la UI muestra la decisión y el umbral como texto | RESUELTO | ResumeApprovalPolicy backend; UI recibe decisión y umbral descriptivo |
| Estado de candidatura | applicationService.py:168,213; interviewService.py:67; models/applicationModel.py:23; schemas/applicationSchema.py:11 | eventos en unas rutas; asignación directa en otra; enum duplicado | historial y agregados divergen | transición canónica y enum compartido |
| Progreso | `app/services/learning/courseProgress.py` (TASK-016) | una proyección desde los hechos; `user_stats` legacy solo-lectura | RESUELTO | CourseProgressProjector |
| Recurso core | `CORE_COURSES` en `app/services/learning/courseProgress.py` (TASK-016) | `resources.core_code`; título solo como fallback | RESUELTO para el dashboard; `ResourceService.MANDATORY_RESOURCE_TITLES` sigue ordenando el listado por título | código de recurso estable y mapping único |
| CV actual/propio/cache | resumeService.py:112,122; cvAnalysisService.py:86,95,299; capstoneAnalyticsService.py:274 | consultas similares repartidas | cambio de semántica latest/version exige múltiples cambios | consultas CV específicas reutilizadas; no repo genérico |
| Ranking recruiter | applicationService.py:332; companyRecruiterService.py:26 | sort Python vs CASE SQL | asignación/orden pueden variar | policy de rango de rol + query de selección limitada |
| Config auth | userService.py:24; companies/companyService.py:21; config.py | ENV/secret loader duplicados | defaults divergentes y mantenimiento | configuración validada compartida |
| Intento Gemini | llm_model.py:116; resume_audit_llm.py:99 | loops de retry parecidos, guards externos | presupuesto cuenta operación en vez de intento | gateway de intento y política retry; prompts permanecen separados |
| HTML/URL/errores de fetch | userProfile.js, jobs.js, career_lab.js, resource_detail.js | escape/fetch por pantalla y sumideros dispares | F-03 y estado stale | helpers concretos de API/render seguro, no framework genérico |

## Transición de autoridad

Para cada concepto: documentar regla actual con ejemplos, contar inconsistencias sin modificar filas, elegir autoridad con provenance, expandir columnas/constraints si hace falta, backfill idempotente por lotes, medir parity, cambiar readers/writers de forma coordinada y mantener vía de rollback. No dual-write indefinido. Si no se puede atribuir un resultado legacy a un CV concreto, conservarlo como legacy no atribuible: no asociarlo automáticamente al último CV. Los eventos inexistentes no se reconstruyen como si hubieran sucedido.
