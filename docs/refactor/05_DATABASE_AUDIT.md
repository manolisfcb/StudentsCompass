# Auditoría de base de datos

Fecha: 2026-09-05. Revisión local: `6a2ea29`. Auditoría estática y pruebas aisladas; no se conectó a producción ni se modificó código productivo. Las líneas son referencias al snapshot y pueden desplazarse.

## Alcance

47 tablas declaradas en modelos y `resource_enrollments` adicional en migraciones. Inventario lógico del repositorio, **no** dump de producción. Los nombres de servicios son referencias a `app/services/` y se pueden localizar por símbolo; Reads/Writes indican consumidores conocidos, no actividad medida. F-08 y F-20 impiden asumir que metadata, SQLite de tests y DB desplegada son idénticas. KEEP no certifica ausencia de problemas: indica conservar la entidad.

## Matriz de tablas

| Table | Purpose | Reads | Writes | Potential Redundancy | Recommended Action |
| --- | --- | --- | --- | --- | --- |
| `ai_usage_events` | Ledger de uso por usuario/feature; `app/models/aiUsageModel.py:12` | AIUsageService | AIUsageService.commit_usage | No confirmada | REVIEW |
| `ai_quota_grants` | Concesión de unidades extra por periodo; `app/models/aiUsageModel.py:25` | AIUsageService.get_daily_limit | No escritor runtime dedicado confirmado; fixtures/operación DB | No confirmada | KEEP |
| `application_status_events` | Historial de transiciones; `app/models/applicationAnalyticsModel.py:19` | DashboardService / analytics | ApplicationService._record_status_event | No confirmada | KEEP |
| `application_daily_aggregates` | Proyección diaria por empresa; `app/models/applicationAnalyticsModel.py:46` | DashboardService | ApplicationService._apply_daily_aggregate_delta | Derivado de eventos | REVIEW |
| `applications` | Candidatura y estado actual; `app/models/applicationModel.py:38` | ApplicationService, DashboardService, CompanyApplicantService | ApplicationService, InterviewService | No confirmada | KEEP |
| `communities` | Comunidad y cache member_count; `app/models/communityModel.py:13` | CommunityService, admin, feed | CommunityService y AdminService | member_count derivable | KEEP |
| `community_members` | Pertenencia a comunidad; `app/models/communityModel.py:32` | CommunityService y perfil | CommunityService join/leave | No confirmada | KEEP |
| `community_posts` | Post dentro de comunidad; `app/models/communityPostModel.py:11` | CommunityService y feed | CommunityService | No confirmada | KEEP |
| `community_post_likes` | Like único usuario/post; `app/models/communityPostModel.py:29` | CommunityService contadores/batching | CommunityService toggle | No confirmada | KEEP |
| `community_post_comments` | Comentarios del feed; `app/models/communityPostModel.py:46` | CommunityService | CommunityService | No confirmada | KEEP |
| `companies` | Organización empleadora; `app/models/companyModel.py:11` | company/job/applicant/dashboard services | companyRoute y gestión empresa | No confirmada | KEEP |
| `company_recruiters` | Credenciales y rol de compañía; `app/models/companyRecruiterModel.py:13` | companyService, recruiterService, ApplicationService | registro compañía y CompanyRecruiterService | No confirmada | KEEP |
| `email_notification_logs` | Registro de email mock; `app/models/emailNotificationLogModel.py:10` | CompanyApplicantService / relaciones candidatura | EmailNotificationService.queue_mock_email | No confirmada | KEEP |
| `friend_requests` | Solicitud y estado de amistad; `app/models/friendshipModel.py:11` | FriendshipService y perfil | FriendshipService | No confirmada | KEEP |
| `friendships` | Relación dirigida de amistad; `app/models/friendshipModel.py:26` | FriendshipService y MessageService | FriendshipService accept/remove | No confirmada | KEEP |
| `interview_availabilities` | Opciones y reserva por candidatura; `app/models/interviewAvailabilityModel.py:18` | InterviewService y DTO candidatura | InterviewService | No confirmada | REVIEW |
| `job_analysis` | Job keywords y resultado; `app/models/jobAnalysisModel.py:18` | CVAnalysisService y jobRoute | CVAnalysisService | No confirmada | REVIEW |
| `job_postings` | Oferta interna de compañía; `app/models/jobPostingModel.py:19` | JobPostingService, búsquedas, Capstone | JobPostingService y admin | No confirmada | KEEP |
| `conversations` | DM identificado por pareja; `app/models/messageModel.py:11` | MessageService | MessageService create/get | No confirmada | KEEP |
| `conversation_participants` | Participantes y lectura; `app/models/messageModel.py:33` | MessageService | MessageService creación/mark_read | No confirmada | KEEP |
| `messages` | Contenido y remitente; `app/models/messageModel.py:50` | MessageService.list_messages / inbox | MessageService.send_message | No confirmada | KEEP |
| `posts` | Publicación general con media; `app/models/postModel.py:9` | PostService y rutas posts | PostService; upload_post | Coexiste con community_posts; distinta responsabilidad | REVIEW |
| `user_questionnaires` | Respuestas y resultados por versión; `app/models/questionnaireModel.py:8` | QuestionnaireService, DashboardService | QuestionnaireService.submit_questionnaire | No confirmada | KEEP |
| `resources` | Contenido pedagógico/catálogo; `app/models/resourceModel.py:13` | ResourceService, DashboardService, Capstone linked course | AdminService | No confirmada | KEEP |
| `resource_modules` | Módulos ordenados de recurso; `app/models/resourceModel.py:42` | ResourceService / dashboard | AdminService | No confirmada | KEEP |
| `resource_lessons` | Lecciones y contenido tipado; `app/models/resourceModel.py:62` | ResourceService / dashboard | AdminService / codec | No confirmada | KEEP |
| `resource_lesson_progress` | Hechos de avance por lección; `app/models/resourceModel.py:83` | ResourceService / DashboardService | ResourceService.set_lesson_progress | Shapes distintas en migraciones | REVIEW |
| `resume_course_evaluations` | Auditoría CV versionada; `app/models/resumeCourseEvaluationModel.py:20` | ApplicationService, ResourceService, ResumeCourseAuditService | ResumeCourseAuditService | No confirmada | KEEP |
| `resume_embeddings` | Vector por CV/modelo; `app/models/resumeEmbeddingsModel.py:10` | ResumeEmbeddingService similarity | ResumeEmbeddingService upsert | No confirmada | KEEP |
| `resumes` | Identidad y referencia de documento; `app/models/resumeModel.py:9` | ResumeService, CVAnalysis, Capstone, applicants | ResumeService y CVAnalysisService | summary/URL derivados | REVIEW |
| `roadmaps` | Plan de aprendizaje publicado; `app/models/roadmapModel.py:36` | RoadmapRepository / RoadmapService | roadmapSeedService; sin editor general confirmado | No confirmada | KEEP |
| `roadmap_stages` | Etapas ordenadas de roadmap; `app/models/roadmapModel.py:63` | RoadmapRepository / RoadmapService | roadmapSeedService | No confirmada | KEEP |
| `stage_tasks` | Tareas de una etapa; `app/models/roadmapModel.py:86` | RoadmapRepository / RoadmapService | roadmapSeedService | No confirmada | KEEP |
| `stage_projects` | Proyecto de una etapa; `app/models/roadmapModel.py:112` | RoadmapRepository / RoadmapService | roadmapSeedService | No confirmada | KEEP |
| `user_roadmaps` | Roadmaps guardados; `app/models/roadmapModel.py:127` | RoadmapRepository | RoadmapService save/unsave | No confirmada | KEEP |
| `user_task_progress` | Estado de tarea del usuario; `app/models/roadmapModel.py:139` | RoadmapRepository / RoadmapService | RoadmapService.update_task_progress | No confirmada | KEEP |
| `user_stage_progress` | Proyección de avance etapa; `app/models/roadmapModel.py:161` | RoadmapRepository / RoadmapService | RoadmapService.update_task_progress | Derivado de tareas | DERIVE |
| `user_project_submissions` | Entrega del proyecto; `app/models/roadmapModel.py:174` | RoadmapRepository / RoadmapService | RoadmapService submit_project | No confirmada | KEEP |
| `skills` | Catálogo canónico de skills; `app/models/skillModel.py:26` | SkillExtractionService, Capstone | capstoneAnalyticsSeedService / catálogo | No confirmada | KEEP |
| `skill_aliases` | Alias a skill canónica; `app/models/skillModel.py:48` | SkillExtractionService / lookup | capstoneAnalyticsSeedService | No confirmada | KEEP |
| `job_skills` | Evidencia de oferta o requisito fallback; `app/models/skillModel.py:64` | Capstone gap/mercado | CapstoneAnalyticsService, seed | Dos tipos de evidencia; falta unicidad | REVIEW |
| `resume_skills` | Evidencia CV y revisión por método; `app/models/skillModel.py:85` | Capstone y matching | Capstone extracción/revisión/manual | No confirmada | KEEP |
| `courses` | Oferta de curso para optimización; `app/models/skillModel.py:114` | courseCatalogQueries, Capstone, optimizer | capstoneAnalyticsSeedService | No confirmada | KEEP |
| `course_skills` | Cobertura/prerrequisito de curso; `app/models/skillModel.py:141` | courseCatalogQueries y optimizer | capstoneAnalyticsSeedService | No confirmada | KEEP |
| `optimization_runs` | Snapshot de resultado y constraints; `app/models/skillModel.py:161` | Capstone.list_learning_route_runs | Capstone.optimize_learning_route | No confirmada | KEEP |
| `users` | Identidad/perfil estudiante; `app/models/userModel.py:11` | auth/profile, dominios con actor | FastAPI Users y profileService | No confirmada | KEEP |
| `user_stats` | Cache de progreso estudiante; `app/models/userStatsModel.py:10` | DashboardService | DashboardService create/sync en lectura | Cache de progreso | DERIVE |
| `resource_enrollments` | Inscripción legacy; migración `6e4bc7a18f21:29` | Sin caller app confirmado | Migración/backfill histórico; sin escritor app confirmado | Posible legacy, existencia/filas reales pendientes | REVIEW |

## Relaciones declaradas

| Tabla dependiente | FKs simples en modelos |
| --- | --- |
| `ai_usage_events` | `users.id` |
| `ai_quota_grants` | `users.id` |
| `application_status_events` | `applications.id`, `companies.id`, `company_recruiters.id`, `job_postings.id`, `users.id` |
| `application_daily_aggregates` | `companies.id` |
| `applications` | `companies.id`, `company_recruiters.id`, `resumes.id`, `users.id` |
| `communities` | `users.id` |
| `community_members` | `communities.id`, `users.id` |
| `community_posts` | `communities.id`, `users.id` |
| `community_post_likes` | `community_posts.id`, `users.id` |
| `community_post_comments` | `community_posts.id`, `users.id` |
| `company_recruiters` | `companies.id` |
| `email_notification_logs` | `applications.id`, `companies.id`, `company_recruiters.id`, `users.id` |
| `friend_requests` | `users.id` |
| `friendships` | `users.id` |
| `interview_availabilities` | `applications.id`, `companies.id`, `company_recruiters.id`, `users.id` |
| `job_analysis` | `resumes.id`, `users.id` |
| `job_postings` | `companies.id` |
| `conversation_participants` | `conversations.id`, `users.id` |
| `messages` | `conversations.id`, `users.id` |
| `posts` | `users.id` |
| `user_questionnaires` | `users.id` |
| `resource_modules` | `resources.id` |
| `resource_lessons` | `resource_modules.id` |
| `resource_lesson_progress` | `resource_lessons.id`, `users.id` |
| `resume_course_evaluations` | `resumes.id`, `users.id` |
| `resume_embeddings` | `resumes.id` |
| `resumes` | `users.id` |
| `roadmap_stages` | `roadmaps.id` |
| `stage_tasks` | `roadmap_stages.id` |
| `stage_projects` | `roadmap_stages.id` |
| `user_roadmaps` | `roadmaps.id`, `users.id` |
| `user_task_progress` | `stage_tasks.id`, `users.id` |
| `user_stage_progress` | `roadmap_stages.id`, `users.id` |
| `user_project_submissions` | `stage_projects.id`, `users.id` |
| `skill_aliases` | `skills.id` |
| `job_skills` | `job_postings.id`, `skills.id` |
| `resume_skills` | `resumes.id`, `skills.id`, `users.id` |
| `courses` | `resources.id` |
| `course_skills` | `courses.id`, `skills.id` |
| `optimization_runs` | `resumes.id`, `users.id` |
| `user_stats` | `users.id` |

Además, `applications(job_posting_id,company_id)` referencia `job_postings(id,company_id)` mediante FK compuesta: **ya existe** defensa de consistencia empresa/oferta. `assigned_recruiter_id` y `resume_id` son FKs simples; no imponen por sí solas que recruiter pertenezca a empresa o CV a usuario. Los servicios revisados validan selección de CV; verificar cualquier nuevo writer y decidir constraints compuestas solo con evidencia de necesidad. No se propone RLS obligatoria sin evaluar el modelo de acceso.

## Integridad, cascadas y tipos

- **F-04:** resumes permite user_id NULL y storage_file_id no único. No convertir a NOT NULL/UNIQUE hasta inventariar registros legacy y referencias compartidas. Unicidad de clave nueva no requiere renombrar todo storage.
- **F-11/F-12:** eventos/agregados se escriben en la misma transacción en ApplicationService, pero existen writers alternativos y carreras. Unicidad diaria ya existe; falta actualización atómica. Unicidad parcial de slot BOOKED se añade después de resolver duplicados, sin borrar historia.
- **F-13:** ai_usage_events tiene FK user y referencias genéricas sin FK. Reference_type/id no únicos. Su carácter polimórfico es razonable, pero requiere idempotencia por operación. No usar simplemente UNIQUE sobre campos opcionales sin tratar NULL y concesiones manuales.
- **F-20:** resource_lesson_progress puede existir con resource_id NOT NULL según orden de ramas; el modelo no lo escribe. Convergencia requiere derivarlo vía lesson→module para backfill/verificación. Los timestamps completed_at nullable de la rama legacy no equivalen a una fila completada actual.
- **F-23:** job_skills debe distinguir oferta real de perfil de rol. Dos índices parciales pueden cubrir casos con/ sin posting; preservar extraction_method y evidencia. resume_skills ya tiene unique(resume,skill,method), courses unique(provider,title) y course_skills unique(course,skill): no añadir duplicados.
- FKs con CASCADE son extensas en comunidad/roadmaps/skills. Borrar un creador puede borrar comunidades por la FK created_by en DB; ORM/cascadas pueden comportarse distinto. No se confirmó el flujo destructivo completo. Antes de cambiarlo probar borrado de usuario con dependencias y definir si se transfiere propiedad; no ejecutar borrados para auditar.
- DateTime mayormente UTC naive frente a embeddings timezone-aware; campos de entrevista incluyen timezone textual. Mantener wire format, validar fechas aware/naive y DST; no convertir timestamps masivamente suponiendo zona histórica.
- Vector(384) es fijo, mientras EMBEDDING_DIMS configurable y campo dims separado. Validar compatibilidad al arrancar/escribir; un cambio de modelo/dimensión requiere migración e índice propios (F-21/F-23).
- Float en costes de cursos/optimización es aproximado. No hay contabilidad financiera; comparar error de redondeo con escalado entero del solver antes de proponer Numeric. CHECK no negativos/rangos puede ser suficiente inicialmente.
- JSON en cuestionarios, tags y snapshots de optimización es razonable; no normalizar cada atributo. `resource_lessons.content` contiene texto/JSON tipado por codec; conservar codec como autoridad y validar URLs al decodificar/renderizar. Course/resources son complementarios; no hay justificación de MERGE.

## Índices: existentes y candidatos

| Área | Evidencia existente | Acción |
| --- | --- | --- |
| Candidaturas | Índices compuestos usuario/fecha, empresa/status/fecha, job/fecha y unique parcial usuario/job en modelo y revisión c8a6 | Conservar; manejar IntegrityError de submit concurrente, no añadir otro unique equivalente |
| Cuota | Revisión 3f8a añade `(user_id,feature,created_at)` y grants `(user_id,feature,is_active)` | Ya cubre consultas principales mejor que índices aislados; alinear metadata, no afirmar índice faltante |
| Mensajes | Revisión 2d4e añade conversation_id/created_at y participantes | Evaluar compuesto `(conversation_id,created_at,id)` para cursor con EXPLAIN en TASK-024 |
| Progreso | Unique `(user_id,lesson_id)`; FKs/indexes de módulos/lecciones en migraciones | Usar JOIN/batching; inspeccionar schema antes de añadir índices |
| Embeddings | Unique `(resume_id,model_name)` y revisión c7d8 de HNSW | Verificar extensión/HNSW en DB; el test de búsqueda pgvector se omite en SQLite |
| Agregados | Unique empresa/día más índice del mismo prefijo | Candidato a redundancia; retirar solo con catálogo/planes/estadísticas, no por nombres |
| Job analysis | Índice resume_id en e1f7; consultas usuario/resume/status/fecha | Evaluar índice compuesto y unique parcial de activo junto a TASK-013 |
| Catálogo | Índices skills/links/role, algunos booleanos is_active | No atribuir utilidad o desuso sin cardinalidad y pg_stat_user_indexes |

No se ejecutó EXPLAIN en producción. Un full scan de tabla pequeña no es automáticamente un problema. No usar OFFSET para históricos grandes sin medir; cursor necesita orden total estable y migración de API.

## Queries y cambios propuestos

F-17 documenta N+1 real en list_user_enrollment_progress (al menos dos consultas extra por recurso, más evaluación condicional) y batch de extracción de ofertas (links/commit por oferta). Mantener batching existente de mensajes, roadmaps y lookup de skills. F-22: listar todos los mensajes y aplicaciones aumenta RAM/payload; dashboard puede usar COUNT/FILTER y top5 SQL. F-21: fingerprint evita generación/write en warm path. `courseCatalogQueries` carga links y filtra is_active después: empujar filtro mediante JOIN es optimización moderada, no un refactor del dominio.

## Secuencia de migración segura

1. Resolver configuración/credenciales (TASK-002); inventariar revisiones y snapshots con acceso de solo lectura autorizado.
2. Crear baseline y convergencia (TASK-009), probar vacío y copias de cada estado soportado. No ejecutar la cadena histórica sobre datos reales por intuición.
3. Reservar nombres de revisión por tarea; cada migración nueva parte del head integrado conocido. Integrador serializa merges, nunca dos agentes editan la misma revisión.
4. Expandir y backfill en lotes reanudables; verificar NULL, duplicados, conteos y FKs. Para índice concurrente documentar autocommit fuera de transacción; no elegirlo sin considerar tamaño/locks.
5. Validar constraints antes del switch; actualizar writer/reader conservando contratos; medir parity.
6. Mantener columnas legacy hasta comprobar consumidores y restore. Eliminación destructiva requerirá tarea nueva específica con evidencia de no uso; este plan no autoriza DROP genérico.

Rollback: preferir volver a código compatible con schema expandido. No hacer downgrade que borre datos; restauración probada o forward fix. Copiar y verificar objetos storage independientemente de backups DB. No existe una transacción distribuida que cubra ambos.
