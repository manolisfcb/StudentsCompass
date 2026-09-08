# Baseline de paridad — TASK-035

Generado por `scripts/capture_baseline.py`. No editar a mano: se reescribe entero en cada ejecución.

- OpenAPI: `openapi.json` (144 paths)
- Fixtures capturadas: 59 · sin capturar: 6
- Capturas: 44 (22 pantallas × 2 viewports)

## Pantallas por vertical

| Pantalla | Ruta | Actor | Vertical | Status | Desktop | Mobile |
| --- | --- | --- | --- | --- | --- | --- |
| root | `/` | anonymous | V1-TASK-046 | 200 | `screens/root.desktop.png` | `screens/root.mobile.png` |
| home | `/home` | anonymous | V1-TASK-046 | 200 | `screens/home.desktop.png` | `screens/home.mobile.png` |
| about | `/about` | anonymous | V1-TASK-046 | 200 | `screens/about.desktop.png` | `screens/about.mobile.png` |
| login | `/login` | anonymous | V1-TASK-046 | 200 | `screens/login.desktop.png` | `screens/login.mobile.png` |
| register | `/register` | anonymous | V1-TASK-046 | 200 | `screens/register.desktop.png` | `screens/register.mobile.png` |
| register-api-alias | `/api/v1/auth/register` | anonymous | V1-TASK-046 | 200 | `screens/register-api-alias.desktop.png` | `screens/register-api-alias.mobile.png` |
| admin-login | `/admin/login` | anonymous | V8-TASK-053 | 200 | `screens/admin-login.desktop.png` | `screens/admin-login.mobile.png` |
| dashboard | `/dashboard` | student | V3-TASK-048 | 200 | `screens/dashboard.desktop.png` | `screens/dashboard.mobile.png` |
| questionnaire | `/questionnaire` | student | V2-TASK-047 | 200 | `screens/questionnaire.desktop.png` | `screens/questionnaire.mobile.png` |
| user-profile | `/user-profile` | student | V2-TASK-047 | 200 | `screens/user-profile.desktop.png` | `screens/user-profile.mobile.png` |
| resources | `/resources` | student | V3-TASK-048 | 200 | `screens/resources.desktop.png` | `screens/resources.mobile.png` |
| resource-detail | `/resources/{resource}` | student | V3-TASK-048 | 200 | `screens/resource-detail.desktop.png` | `screens/resource-detail.mobile.png` |
| roadmaps | `/roadmaps` | student | V3-TASK-048 | 200 | `screens/roadmaps.desktop.png` | `screens/roadmaps.mobile.png` |
| roadmap-detail | `/roadmaps/{slug}` | student | V3-TASK-048 | 200 | `screens/roadmap-detail.desktop.png` | `screens/roadmap-detail.mobile.png` |
| jobs | `/jobs` | student | V4-TASK-049 | 200 | `screens/jobs.desktop.png` | `screens/jobs.mobile.png` |
| community | `/community` | student | V6-TASK-051 | 200 | `screens/community.desktop.png` | `screens/community.mobile.png` |
| community-feed | `/community/{community}` | student | V6-TASK-051 | 200 | `screens/community-feed.desktop.png` | `screens/community-feed.mobile.png` |
| career-lab | `/career-lab` | student | V7-TASK-052 | 200 | `screens/career-lab.desktop.png` | `screens/career-lab.mobile.png` |
| admin | `/admin` | admin | V8-TASK-053 | 200 | `screens/admin.desktop.png` | `screens/admin.mobile.png` |
| company-dashboard | `/company-dashboard` | recruiter | V5-TASK-050 | 200 | `screens/company-dashboard.desktop.png` | `screens/company-dashboard.mobile.png` |
| company-candidates | `/company-candidates` | recruiter | V5-TASK-050 | 200 | `screens/company-candidates.desktop.png` | `screens/company-candidates.mobile.png` |
| company-team | `/company-team` | recruiter | V5-TASK-050 | 200 | `screens/company-team.desktop.png` | `screens/company-team.mobile.png` |

### Rutas de vista sin captura

- `/roadmap` — redirección 307 a /roadmaps; no renderiza pantalla propia

### Peticiones externas bloqueadas durante la captura

El navegador solo puede hablar con el servidor local. Estas pantallas pidieron algo de fuera y no lo recibieron; su captura muestra la página sin ese recurso.

- `admin` — https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap
- `admin-login` — https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap
- `questionnaire` — https://cdn.tailwindcss.com/

## Fixtures por vertical

| Endpoint | Actor | Vertical | Status | Fichero |
| --- | --- | --- | --- | --- |
| `GET /api/v1/admin/applications` | admin | V8-TASK-053 | 200 | `fixtures/admin/admin_applications.json` |
| `GET /api/v1/admin/communities` | admin | V8-TASK-053 | 200 | `fixtures/admin/admin_communities.json` |
| `GET /api/v1/admin/companies` | admin | V8-TASK-053 | 500 | `fixtures/admin/admin_companies.json` |
| `GET /api/v1/admin/jobs` | admin | V8-TASK-053 | 200 | `fixtures/admin/admin_jobs.json` |
| `GET /api/v1/admin/resources` | admin | V8-TASK-053 | 200 | `fixtures/admin/admin_resources.json` |
| `GET /api/v1/admin/resources/{resource_id}` | admin | V8-TASK-053 | 200 | `fixtures/admin/admin_resources_resource_id.json` |
| `GET /api/v1/admin/stats` | admin | V8-TASK-053 | 200 | `fixtures/admin/admin_stats.json` |
| `GET /api/v1/admin/users` | admin | V8-TASK-053 | 200 | `fixtures/admin/admin_users.json` |
| `GET /api/v1/admin/users/{user_id}/resource-progress` | admin | V8-TASK-053 | 200 | `fixtures/admin/admin_users_user_id_resource_progress.json` |
| `GET /api/v1/applications` | student | V4-TASK-049 | 200 | `fixtures/student/applications.json` |
| `GET /api/v1/applications/eligible-resumes` | student | V4-TASK-049 | 200 | `fixtures/student/applications_eligible_resumes.json` |
| `GET /api/v1/capstone/analytics/roles` | student | V7-TASK-052 | 200 | `fixtures/student/capstone_analytics_roles.json` |
| `GET /api/v1/capstone/analytics/status` | student | V7-TASK-052 | 200 | `fixtures/student/capstone_analytics_status.json` |
| `GET /api/v1/capstone/catalog/quality` | student | V7-TASK-052 | 200 | `fixtures/student/capstone_catalog_quality.json` |
| `GET /api/v1/capstone/gap-analysis` | student | V7-TASK-052 | 200 | `fixtures/student/capstone_gap_analysis.json` |
| `GET /api/v1/capstone/learning-route/runs` | student | V7-TASK-052 | 200 | `fixtures/student/capstone_learning_route_runs.json` |
| `GET /api/v1/capstone/resumes/{resume_id}/skills` | student | V7-TASK-052 | 200 | `fixtures/student/capstone_resumes_resume_id_skills.json` |
| `GET /api/v1/communities` | student | V6-TASK-051 | 200 | `fixtures/student/communities.json` |
| `GET /api/v1/communities/tags` | student | V6-TASK-051 | 200 | `fixtures/student/communities_tags.json` |
| `GET /api/v1/communities/{community_id}` | student | V6-TASK-051 | 200 | `fixtures/student/communities_community_id.json` |
| `GET /api/v1/communities/{community_id}/membership` | student | V6-TASK-051 | 200 | `fixtures/student/communities_community_id_membership.json` |
| `GET /api/v1/communities/{community_id}/posts` | student | V6-TASK-051 | 200 | `fixtures/student/communities_community_id_posts.json` |
| `GET /api/v1/communities/{community_id}/posts/enriched` | student | V6-TASK-051 | 200 | `fixtures/student/communities_community_id_posts_enriched.json` |
| `GET /api/v1/community-posts/{post_id}/comments` | student | V6-TASK-051 | 200 | `fixtures/student/community_posts_post_id_comments.json` |
| `GET /api/v1/community-posts/{post_id}/comments/enriched` | student | V6-TASK-051 | 200 | `fixtures/student/community_posts_post_id_comments_enriched.json` |
| `GET /api/v1/companies/me` | recruiter | V5-TASK-050 | 200 | `fixtures/recruiter/companies_me.json` |
| `GET /api/v1/companies/me/applicants` | recruiter | V5-TASK-050 | 200 | `fixtures/recruiter/companies_me_applicants.json` |
| `GET /api/v1/companies/me/job-postings` | recruiter | V5-TASK-050 | 200 | `fixtures/recruiter/companies_me_job_postings.json` |
| `GET /api/v1/companies/me/recruiters` | recruiter | V5-TASK-050 | 200 | `fixtures/recruiter/companies_me_recruiters.json` |
| `GET /api/v1/companies/me/recruiters/current` | recruiter | V5-TASK-050 | 200 | `fixtures/recruiter/companies_me_recruiters_current.json` |
| `GET /api/v1/company_dashboard` | recruiter | V5-TASK-050 | 200 | `fixtures/recruiter/company_dashboard.json` |
| `GET /api/v1/conversations` | student | V6-TASK-051 | 200 | `fixtures/student/conversations.json` |
| `GET /api/v1/conversations/{conversation_id}/messages` | student | V6-TASK-051 | 200 | `fixtures/student/conversations_conversation_id_messages.json` |
| `GET /api/v1/dashboard/stats` | student | V3-TASK-048 | 200 | `fixtures/student/dashboard_stats.json` |
| `GET /api/v1/friends` | student | V6-TASK-051 | 200 | `fixtures/student/friends.json` |
| `GET /api/v1/friends/requests/incoming` | student | V6-TASK-051 | 200 | `fixtures/student/friends_requests_incoming.json` |
| `GET /api/v1/friends/requests/outgoing` | student | V6-TASK-051 | 200 | `fixtures/student/friends_requests_outgoing.json` |
| `GET /api/v1/friends/status` | student | V6-TASK-051 | 200 | `fixtures/student/friends_status.json` |
| `GET /api/v1/jobs/board` | student | V4-TASK-049 | 200 | `fixtures/student/jobs_board.json` |
| `GET /api/v1/jobs/keywords` | student | V4-TASK-049 | 200 | `fixtures/student/jobs_keywords.json` |
| `GET /api/v1/jobs/keywords/{job_id}` | student | V4-TASK-049 | 404 | `fixtures/student/jobs_keywords_job_id.json` |
| `GET /api/v1/me/roadmaps` | student | V3-TASK-048 | 200 | `fixtures/student/me_roadmaps.json` |
| `GET /api/v1/posts` | student | V6-TASK-051 | 200 | `fixtures/student/posts.json` |
| `GET /api/v1/posts/{post_id}` | student | V6-TASK-051 | 200 | `fixtures/student/posts_post_id.json` |
| `GET /api/v1/profile` | student | V2-TASK-047 | 200 | `fixtures/student/profile.json` |
| `GET /api/v1/profile/cv` | student | V2-TASK-047 | 200 | `fixtures/student/profile_cv.json` |
| `GET /api/v1/profile/cv/course-audit-attempts` | student | V2-TASK-047 | 200 | `fixtures/student/profile_cv_course_audit_attempts.json` |
| `GET /api/v1/questionnaire` | student | V2-TASK-047 | 200 | `fixtures/student/questionnaire.json` |
| `GET /api/v1/questionnaire/profile` | student | V2-TASK-047 | 200 | `fixtures/student/questionnaire_profile.json` |
| `GET /api/v1/resources` | student | V3-TASK-048 | 200 | `fixtures/student/resources.json` |
| `GET /api/v1/resources/file` | student | V3-TASK-048 | 404 | `fixtures/student/resources_file.json` |
| `GET /api/v1/resources/{resource_id}` | student | V3-TASK-048 | 200 | `fixtures/student/resources_resource_id.json` |
| `GET /api/v1/resources/{resource_id}/outline` | student | V3-TASK-048 | 200 | `fixtures/student/resources_resource_id_outline.json` |
| `GET /api/v1/resources/{resource_id}/progress` | student | V3-TASK-048 | 200 | `fixtures/student/resources_resource_id_progress.json` |
| `GET /api/v1/roadmaps` | student | V3-TASK-048 | 200 | `fixtures/student/roadmaps.json` |
| `GET /api/v1/roadmaps/{slug}` | student | V3-TASK-048 | 200 | `fixtures/student/roadmaps_slug.json` |
| `GET /api/v1/students_dashboard` | student | V3-TASK-048 | 200 | `fixtures/student/students_dashboard.json` |
| `GET /api/v1/users/me` | student | V1-TASK-046 | 200 | `fixtures/student/users_me.json` |
| `GET /api/v1/users/{id}` | admin | V8-TASK-053 | 200 | `fixtures/admin/users_id.json` |

### Endpoints GET sin fixture, con razón

- `GET /api/v1/companies/me/applications/{application_id}/resume/download` — descarga desde object storage; el aislamiento bloquea la salida y la respuesta describiría el entorno, no el endpoint
- `GET /api/v1/companies/me/applications/{application_id}/resume/preview` — previsualización desde object storage; misma razón que /resume/download
- `GET /api/v1/profile/cv/{resume_id}/similar` — usa el operador pgvector `<=>`; la baseline corre sobre SQLite y el endpoint declara que exige PostgreSQL con la extensión vector
- `GET /favicon.ico` — asset binario servido por FileResponse; no hay payload que comparar
- `GET /robots.txt` — texto plano estático
- `GET /sitemap.xml` — XML cubierto por tests/test_sitemap.py

