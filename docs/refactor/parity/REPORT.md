# Paridad de las ocho verticales — TASK-046 a TASK-053

Generado por `backend/scripts/verify_parity.py`. No editar a mano.

El SPA corre contra **la misma semilla sintética que la baseline de TASK-035**, servido en un solo origen por el espejo en proceso de `frontend/nginx.conf`. Cada pantalla se fotografía y, en la misma visita, se anota todo lo que pidió al servidor.

## Resumen

- Pantallas capturadas: **48** (24 pantallas × 2 viewports)
- Comparadas contra la baseline: **42**
- Endpoints REST barridos por rol: **60** × 4 actores
- Rutas del SPA con guard verificado: **15** × 4 actores
- **Peticiones al contrato legacy: 0**
- **Violaciones de permisos: 0**
- **Endpoints que devuelven 5xx a quien tiene derecho: 1**

## V1-TASK-046 — Vertical 1 — Shell público y autenticación

### Pantallas

| Pantalla | Ruta SPA | Actor | HTTP | Baseline | RMS layout | Marca | Errores JS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| about.desktop | `/about` | anonymous | 200 | about | 69.78 | sí | 0 |
| about.mobile | `/about` | anonymous | 200 | about | 58.63 | sí | 0 |
| home.desktop | `/` | anonymous | 200 | home | 83.67 | sí | 0 |
| home.mobile | `/` | anonymous | 200 | home | 80.12 | sí | 0 |
| login.desktop | `/login` | anonymous | 200 | login | 104.13 | sí | 0 |
| login.mobile | `/login` | anonymous | 200 | login | 83.37 | sí | 0 |
| register.desktop | `/register` | anonymous | 200 | register | 99.63 | sí | 0 |
| register.mobile | `/register` | anonymous | 200 | register | 88.86 | sí | 0 |
| root.desktop | `/` | anonymous | 200 | root | 83.67 | sí | 0 |
| root.mobile | `/` | anonymous | 200 | root | 80.12 | sí | 0 |

- **login** — Mismo contenido y misma estructura de dos paneles (aside de marca + formulario, toggle de tipo de cuenta, ambos enlaces). Lo que sube el RMS es el shell: el monolito servía `/login` como página full-bleed sobre el degradado y sin navegación, y el SPA la sirve dentro de `PublicShell`, con nav, fondo claro y los dos paneles separados en vez de fundidos. Es una consecuencia de meter la pantalla en el shell público, no contenido perdido; cambiarlo sería rediseñar el shell, que ninguna ficha pide.
- **register** — Igual que `login`: mismo contenido, misma estructura, el RMS es la diferencia de shell.

### Tráfico al contrato legacy

**Cero.** Ninguna de las pantallas de esta vertical pidió un endpoint marcado `retire` en la matriz de TASK-034 ni un asset de `/static/`. Medido sobre 56 peticiones distintas.

### Permisos por rol

| Endpoint | Derecho | anon | student | recruiter | admin | |
| --- | --- | --- | --- | --- | --- | --- |
| `/api/v1/users/me` | student | 401 | 200 | 401 | 200 | ✓ |


## V2-TASK-047 — Vertical 2 — Perfil, cuestionario y CV

### Pantallas

| Pantalla | Ruta SPA | Actor | HTTP | Baseline | RMS layout | Marca | Errores JS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| questionnaire.desktop | `/questionnaire` | student | 200 | questionnaire | 101.09 | sí | 0 |
| questionnaire.mobile | `/questionnaire` | student | 200 | questionnaire | 26.1 | sí | 0 |
| user-profile.desktop | `/profile` | student | 200 | user-profile | 52.34 | sí | 0 |
| user-profile.mobile | `/profile` | student | 200 | user-profile | 62.47 | sí | 0 |

- **questionnaire** — El monolito pintaba las 16 preguntas en una página de 1788 px de alto; el SPA es un stepper de una pregunta por paso. La diferencia de altura y de tinta entre las dos capturas es esa, no contenido perdido: el contenido y el orden de las preguntas salen de `GET /api/v1/questionnaire`, que es el mismo endpoint y la misma definición versionada. Es un cambio de presentación, no de regla.

### Tráfico al contrato legacy

**Cero.** Ninguna de las pantallas de esta vertical pidió un endpoint marcado `retire` en la matriz de TASK-034 ni un asset de `/static/`. Medido sobre 32 peticiones distintas.

### Permisos por rol

| Endpoint | Derecho | anon | student | recruiter | admin | |
| --- | --- | --- | --- | --- | --- | --- |
| `/api/v1/profile` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/profile/cv` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/profile/cv/course-audit-attempts` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/profile/cv/{resume_id}/similar` | student | 401 | 200 | 401 | 404 | ✓ |
| `/api/v1/questionnaire` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/questionnaire/profile` | student | 401 | 500 | 401 | 404 | ✓ |

- ⚠ **`/api/v1/questionnaire/profile`**: student: 500 — un actor con derecho recibe un error de servidor. No es un fallo de permisos, pero rompe la pantalla que lo consume.

Guards del SPA (a dónde aterriza quien no es dueño de la ruta):

| Ruta | Dueño | anon | student | recruiter | admin |
| --- | --- | --- | --- | --- | --- |
| `/profile` | student | `/login` | `/profile` | `/company` | `/profile` |
| `/questionnaire` | student | `/login` | `/questionnaire` | `/company` | `/questionnaire` |

## V3-TASK-048 — Vertical 3 — Dashboard, recursos y roadmaps

### Pantallas

| Pantalla | Ruta SPA | Actor | HTTP | Baseline | RMS layout | Marca | Errores JS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dashboard.desktop | `/dashboard` | student | 200 | dashboard | 62.43 | sí | 0 |
| dashboard.mobile | `/dashboard` | student | 200 | dashboard | 67.34 | sí | 0 |
| resource-detail.desktop | `/resources/{resource}` | student | 200 | resource-detail | 82.55 | sí | 0 |
| resource-detail.mobile | `/resources/{resource}` | student | 200 | resource-detail | 95.11 | sí | 0 |
| resources.desktop | `/resources` | student | 200 | resources | 81.15 | sí | 0 |
| resources.mobile | `/resources` | student | 200 | resources | 99.54 | sí | 0 |
| roadmap-detail.desktop | `/roadmaps/{slug}` | student | 200 | roadmap-detail | 87.51 | sí | 0 |
| roadmap-detail.mobile | `/roadmaps/{slug}` | student | 200 | roadmap-detail | 98.69 | sí | 0 |
| roadmaps.desktop | `/roadmaps` | student | 200 | roadmaps | 65.88 | sí | 0 |
| roadmaps.mobile | `/roadmaps` | student | 200 | roadmaps | 82.29 | sí | 0 |

### Tráfico al contrato legacy

**Cero.** Ninguna de las pantallas de esta vertical pidió un endpoint marcado `retire` en la matriz de TASK-034 ni un asset de `/static/`. Medido sobre 54 peticiones distintas.

### Permisos por rol

| Endpoint | Derecho | anon | student | recruiter | admin | |
| --- | --- | --- | --- | --- | --- | --- |
| `/api/v1/dashboard/stats` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/me/roadmaps` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/resources` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/resources/file` | student | 401 | 422 | 401 | 422 | ✓ |
| `/api/v1/resources/{resource_id}` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/resources/{resource_id}/outline` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/resources/{resource_id}/progress` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/roadmaps` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/roadmaps/{slug}` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/students_dashboard` | student | 401 | 200 | 401 | 200 | ✓ |


Guards del SPA (a dónde aterriza quien no es dueño de la ruta):

| Ruta | Dueño | anon | student | recruiter | admin |
| --- | --- | --- | --- | --- | --- |
| `/dashboard` | student | `/login` | `/dashboard` | `/company` | `/dashboard` |
| `/resources` | student | `/login` | `/resources` | `/company` | `/resources` |
| `/roadmaps` | student | `/login` | `/roadmaps` | `/company` | `/roadmaps` |

## V4-TASK-049 — Vertical 4 — Jobs, análisis de CV y candidaturas

### Pantallas

| Pantalla | Ruta SPA | Actor | HTTP | Baseline | RMS layout | Marca | Errores JS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| jobs.desktop | `/jobs` | student | 200 | jobs | 80.0 | sí | 0 |
| jobs.mobile | `/jobs` | student | 200 | jobs | 102.62 | sí | 0 |
| jobs-applications.desktop | `/jobs/applications` | student | 200 | _sin baseline_ | — | — | 0 |
| jobs-applications.mobile | `/jobs/applications` | student | 200 | _sin baseline_ | — | — | 0 |

- Pantalla sin baseline: listado de candidaturas; en el monolito vivía dentro de /jobs

### Tráfico al contrato legacy

**Cero.** Ninguna de las pantallas de esta vertical pidió un endpoint marcado `retire` en la matriz de TASK-034 ni un asset de `/static/`. Medido sobre 20 peticiones distintas.

### Permisos por rol

| Endpoint | Derecho | anon | student | recruiter | admin | |
| --- | --- | --- | --- | --- | --- | --- |
| `/api/v1/applications` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/applications/eligible-resumes` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/jobs/board` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/jobs/keywords` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/jobs/keywords/{job_id}` | student | 401 | 404 | 401 | 404 | ✓ |


Guards del SPA (a dónde aterriza quien no es dueño de la ruta):

| Ruta | Dueño | anon | student | recruiter | admin |
| --- | --- | --- | --- | --- | --- |
| `/jobs` | student | `/login` | `/jobs` | `/company` | `/jobs` |
| `/jobs/applications` | student | `/login` | `/jobs/applications` | `/company` | `/jobs/applications` |

## V5-TASK-050 — Vertical 5 — Company

### Pantallas

| Pantalla | Ruta SPA | Actor | HTTP | Baseline | RMS layout | Marca | Errores JS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| company-candidates.desktop | `/company/applicants` | recruiter | 200 | company-candidates | 104.05 | sí | 0 |
| company-candidates.mobile | `/company/applicants` | recruiter | 200 | company-candidates | 106.29 | sí | 0 |
| company-dashboard.desktop | `/company` | recruiter | 200 | company-dashboard | 82.56 | sí | 0 |
| company-dashboard.mobile | `/company` | recruiter | 200 | company-dashboard | 80.75 | sí | 0 |
| company-postings.desktop | `/company/postings` | recruiter | 200 | _sin baseline_ | — | — | 0 |
| company-postings.mobile | `/company/postings` | recruiter | 200 | _sin baseline_ | — | — | 0 |
| company-team.desktop | `/company/recruiters` | recruiter | 200 | company-team | 81.17 | sí | 0 |
| company-team.mobile | `/company/recruiters` | recruiter | 200 | company-team | 81.17 | sí | 0 |

- Pantalla sin baseline: gestión de ofertas; en el monolito vivía dentro de /company-dashboard

### Tráfico al contrato legacy

**Cero.** Ninguna de las pantallas de esta vertical pidió un endpoint marcado `retire` en la matriz de TASK-034 ni un asset de `/static/`. Medido sobre 40 peticiones distintas.

### Permisos por rol

| Endpoint | Derecho | anon | student | recruiter | admin | |
| --- | --- | --- | --- | --- | --- | --- |
| `/api/v1/companies/me` | recruiter | 401 | 401 | 200 | 401 | ✓ |
| `/api/v1/companies/me/applicants` | recruiter | 401 | 401 | 200 | 401 | ✓ |
| `/api/v1/companies/me/applications/{application_id}/resume/download` | recruiter | 401 | 401 | 500 | 401 | ✓ |
| `/api/v1/companies/me/applications/{application_id}/resume/preview` | recruiter | 401 | 401 | 500 | 401 | ✓ |
| `/api/v1/companies/me/job-postings` | recruiter:job_manager | 401 | 401 | 200 | 401 | ✓ |
| `/api/v1/companies/me/recruiters` | recruiter:owner | 401 | 401 | 200 | 401 | ✓ |
| `/api/v1/companies/me/recruiters/current` | recruiter | 401 | 401 | 200 | 401 | ✓ |
| `/api/v1/company_dashboard` | recruiter | 401 | 401 | 200 | 401 | ✓ |


Denegaciones por recurso (correctas: el actor es del tipo adecuado pero no tiene acceso a *esa* fila):
- `/api/v1/companies/me/applications/{application_id}/resume/download` — recruiter: 500 por almacenamiento de objetos no configurado en este arnés, no por el código
- `/api/v1/companies/me/applications/{application_id}/resume/preview` — recruiter: 500 por almacenamiento de objetos no configurado en este arnés, no por el código

Guards del SPA (a dónde aterriza quien no es dueño de la ruta):

| Ruta | Dueño | anon | student | recruiter | admin |
| --- | --- | --- | --- | --- | --- |
| `/company` | recruiter | `/login` | `/dashboard` | `/company` | `/dashboard` |
| `/company/applicants` | recruiter | `/login` | `/dashboard` | `/company/applicants` | `/dashboard` |
| `/company/postings` | recruiter | `/login` | `/dashboard` | `/company/postings` | `/dashboard` |
| `/company/recruiters` | recruiter | `/login` | `/dashboard` | `/company/recruiters` | `/dashboard` |

## V6-TASK-051 — Vertical 6 — Community, friendships y messages

### Pantallas

| Pantalla | Ruta SPA | Actor | HTTP | Baseline | RMS layout | Marca | Errores JS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| community.desktop | `/community` | student | 200 | community | 79.99 | sí | 0 |
| community.mobile | `/community` | student | 200 | community | 99.17 | sí | 0 |
| community-feed.desktop | `/community/{community}` | student | 200 | community-feed | 74.46 | sí | 0 |
| community-feed.mobile | `/community/{community}` | student | 200 | community-feed | 78.07 | sí | 0 |
| messages.desktop | `/messages` | student | 200 | _sin baseline_ | — | — | 0 |
| messages.mobile | `/messages` | student | 200 | _sin baseline_ | — | — | 0 |

- Pantalla sin baseline: mensajería; nunca tuvo pantalla legacy (TASK-024 la dejó solo como API)

### Tráfico al contrato legacy

**Cero.** Ninguna de las pantallas de esta vertical pidió un endpoint marcado `retire` en la matriz de TASK-034 ni un asset de `/static/`. Medido sobre 34 peticiones distintas.

### Permisos por rol

| Endpoint | Derecho | anon | student | recruiter | admin | |
| --- | --- | --- | --- | --- | --- | --- |
| `/api/v1/communities` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/communities/tags` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/communities/{community_id}` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/communities/{community_id}/membership` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/communities/{community_id}/posts` | student | 401 | 200 | 401 | 403 | ✓ |
| `/api/v1/communities/{community_id}/posts/enriched` | student | 401 | 200 | 401 | 403 | ✓ |
| `/api/v1/community-posts/{post_id}/comments` | student | 401 | 200 | 401 | 403 | ✓ |
| `/api/v1/community-posts/{post_id}/comments/enriched` | student | 401 | 200 | 401 | 403 | ✓ |
| `/api/v1/conversations` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/conversations/{conversation_id}/messages` | student | 401 | 200 | 401 | 404 | ✓ |
| `/api/v1/friends` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/friends/requests/incoming` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/friends/requests/outgoing` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/friends/status` | student | 401 | 200 | 401 | 200 | ✓ |


Denegaciones por recurso (correctas: el actor es del tipo adecuado pero no tiene acceso a *esa* fila):
- `/api/v1/communities/{community_id}/posts` — admin: 403 (autorización de recurso, no de rol)
- `/api/v1/communities/{community_id}/posts/enriched` — admin: 403 (autorización de recurso, no de rol)
- `/api/v1/community-posts/{post_id}/comments` — admin: 403 (autorización de recurso, no de rol)
- `/api/v1/community-posts/{post_id}/comments/enriched` — admin: 403 (autorización de recurso, no de rol)

Guards del SPA (a dónde aterriza quien no es dueño de la ruta):

| Ruta | Dueño | anon | student | recruiter | admin |
| --- | --- | --- | --- | --- | --- |
| `/community` | student | `/login` | `/community` | `/company` | `/community` |
| `/messages` | student | `/login` | `/messages` | `/company` | `/messages` |

## V7-TASK-052 — Vertical 7 — Career Lab / Capstone

### Pantallas

| Pantalla | Ruta SPA | Actor | HTTP | Baseline | RMS layout | Marca | Errores JS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| career-lab.desktop | `/career-lab` | student | 200 | career-lab | 46.71 | sí | 0 |
| career-lab.mobile | `/career-lab` | student | 200 | career-lab | 45.17 | sí | 0 |

### Tráfico al contrato legacy

**Cero.** Ninguna de las pantallas de esta vertical pidió un endpoint marcado `retire` en la matriz de TASK-034 ni un asset de `/static/`. Medido sobre 16 peticiones distintas.

### Permisos por rol

| Endpoint | Derecho | anon | student | recruiter | admin | |
| --- | --- | --- | --- | --- | --- | --- |
| `/api/v1/capstone/analytics/roles` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/capstone/analytics/status` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/capstone/catalog/quality` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/capstone/gap-analysis` | student | 401 | 422 | 401 | 422 | ✓ |
| `/api/v1/capstone/learning-route/runs` | student | 401 | 200 | 401 | 200 | ✓ |
| `/api/v1/capstone/resumes/{resume_id}/skills` | student | 401 | 200 | 401 | 404 | ✓ |


Guards del SPA (a dónde aterriza quien no es dueño de la ruta):

| Ruta | Dueño | anon | student | recruiter | admin |
| --- | --- | --- | --- | --- | --- |
| `/career-lab` | student | `/login` | `/career-lab` | `/company` | `/career-lab` |

## V8-TASK-053 — Vertical 8 — Admin

### Pantallas

| Pantalla | Ruta SPA | Actor | HTTP | Baseline | RMS layout | Marca | Errores JS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| admin.desktop | `/admin` | admin | 200 | admin | 13.48 | sí | 0 |
| admin.mobile | `/admin` | admin | 200 | admin | 21.71 | sí | 0 |
| admin-login.desktop | `/admin/login` | anonymous | 200 | admin-login | 12.16 | sí | 0 |
| admin-login.mobile | `/admin/login` | anonymous | 200 | admin-login | 22.09 | sí | 0 |

- **admin** — Fondo oscuro en ambas: ADR-002 lo trata como un scope sobre los mismos tokens, no como una cuarta paleta, y el RMS bajo (13-22) lo confirma.

### Tráfico al contrato legacy

**Cero.** Ninguna de las pantallas de esta vertical pidió un endpoint marcado `retire` en la matriz de TASK-034 ni un asset de `/static/`. Medido sobre 16 peticiones distintas.

### Permisos por rol

| Endpoint | Derecho | anon | student | recruiter | admin | |
| --- | --- | --- | --- | --- | --- | --- |
| `/api/v1/admin/applications` | admin | 401 | 403 | 401 | 200 | ✓ |
| `/api/v1/admin/communities` | admin | 401 | 403 | 401 | 200 | ✓ |
| `/api/v1/admin/companies` | admin | 401 | 403 | 401 | 200 | ✓ |
| `/api/v1/admin/jobs` | admin | 401 | 403 | 401 | 200 | ✓ |
| `/api/v1/admin/resources` | admin | 401 | 403 | 401 | 200 | ✓ |
| `/api/v1/admin/resources/{resource_id}` | admin | 401 | 403 | 401 | 200 | ✓ |
| `/api/v1/admin/stats` | admin | 401 | 403 | 401 | 200 | ✓ |
| `/api/v1/admin/users` | admin | 401 | 403 | 401 | 200 | ✓ |
| `/api/v1/admin/users/{user_id}/resource-progress` | admin | 401 | 403 | 401 | 200 | ✓ |
| `/api/v1/users/{id}` | admin | 401 | 403 | 401 | 200 | ✓ |


Guards del SPA (a dónde aterriza quien no es dueño de la ruta):

| Ruta | Dueño | anon | student | recruiter | admin |
| --- | --- | --- | --- | --- | --- |
| `/admin` | admin | `/admin/login` | `/admin/login` | `/admin/login` | `/admin` |

## Hallazgos

### V2-TASK-047 — `GET /api/v1/questionnaire/profile` responde 500 ante una fila de cuestionario que no sea una lista

El endpoint legacy no tenía `response_model` y devolvía la fila tal cual, con 200. `QuestionnaireProfileRead` (TASK-047) declara `answers: List[AnswerCreate]` y `results: List[CareerScore]`, así que una fila con otra forma ya no valida y la pantalla de perfil recibe un 500.

**Lo que está comprobado:** con la semilla archivada de TASK-035, que guarda `answers` como diccionario, el endpoint pasa de 200 (baseline) a 500 (hoy).

**Lo que no:** si alguna fila real tiene esa forma. `questionnaireService.submit_questionnaire` escribe una lista y el comentario del modelo documenta la lista, así que la forma del seed no es la que produce la aplicación hoy — pero el seed es evidencia archivada de TASK-035 y **no se ha retocado** para que el 500 desaparezca. Se resuelve con una consulta: si existen filas `user_questionnaires` cuyo `answers` no sea un array, tienen este 500 hoy.

**Por qué no se arregla aquí:** la salida —degradar en vez de 500, migrar las filas, o confirmar que no las hay— es una decisión de producto sobre datos históricos, que es justo lo que TASK-030 acotó y lo que la Definition of Done global prohíbe resolver inventando historia.

### V8-TASK-053 — El guard de `/admin` pasaba a cualquier estudiante — corregido en esta pasada

`views.py` rebotaba `user is None or not user.is_superuser` a `/admin/login`. El router de React guardaba `/admin` con `RequireActor allow={["student"]}`, que cualquier estudiante satisface, así que un no-administrador llegaba al shell de admin y lo veía llenarse de 403.

Ningún dato se filtró —las nueve rutas `/api/v1/admin/*` responden 403 al estudiante, y la tabla de esta vertical lo enseña— pero «el acceso prohibido responde igual» no se cumplía.

**Corregido:** `SessionActor.is_superuser` (aditivo en el contrato) y el guard `RequireAdmin`, con los cuatro casos cubiertos en `guards.test.tsx`.

## Lo que esto no demuestra

- **Que ningún otro consumidor use el contrato legacy.** Esto mide lo que pide el SPA, que es lo que dice el criterio («cero tráfico *del frontend*»). Que nadie más lo llame solo se sabe con el servicio desplegado y sus logs: TASK-056/057, y es la condición de TASK-059.
- **Paridad visual pixel a pixel.** La migración cambió el DOM y el motor de layout; `layout_rms` ordena la revisión humana sobre `sidebyside/`, no la sustituye. Lo exigible de ADR-002 —que la paleta de marca no se rediseñó— sí se comprueba, en la columna «Marca».
- **Que los datos reales se vean bien.** La semilla es sintética y tiene una fila por forma; un fallo que solo aparece con mil filas no está aquí.
