# StudentsCompass Capstone Guide

## Enfoque final

El capstone no debe presentarse como "un SaaS para estudiantes". Debe presentarse como un sistema analítico y de optimización:

> Skill Gap Analysis and Learning Path Optimization for International Students Using Labor Market Data and OR-Tools

StudentsCompass queda como la interfaz de demostración. El proyecto académico real es el pipeline de datos, el análisis del mercado laboral, el modelo de skill gap, el optimizador con OR-Tools y la evaluación cuantitativa contra baselines.

## Pregunta central

> Dado un CV, un rol objetivo y restricciones reales de tiempo/costo, ¿cuál es la ruta óptima de cursos o recursos que maximiza cobertura de skills laborales y mejora la preparación del estudiante?

## Principio de arquitectura

La nueva versión debe reducir piezas externas y concentrar el proyecto en una arquitectura limpia:

- Un solo sistema principal de datos: Postgres.
- Un solo sistema principal de archivos: mantener S3 si ya funciona bien o migrar a Supabase Storage solo si gana por costo, simplicidad y seguridad.
- Auth centralizada: mantener FastAPI Users inicialmente o migrar a Supabase Auth en una fase controlada.
- Embeddings en Postgres con pgvector.
- Analítica reproducible en notebooks/scripts.
- Optimización separada como modulo de dominio, no mezclada con UI.

## Estado actual del repo

El repo hoy es una plataforma web bastante completa:

- Backend FastAPI async.
- SQLAlchemy + Alembic.
- Templates Jinja2 + CSS/JS estaticos.
- Auth con FastAPI Users y JWT por cookie.
- Usuarios, empresas, reclutadores, comunidades, mensajes, postulaciones, roadmaps, recursos y dashboards.
- CV upload y analisis con Gemini.
- S3 para CVs y archivos de recursos.
- ImageKit para imagenes.
- Infraestructura de pgvector, pero embeddings desactivados.
- Scraper LinkedIn best-effort.
- Tests de varias areas del producto.

El problema para el capstone: el valor academico de Data Analysis todavia no esta en el centro. La app existe, pero faltan los modulos analiticos y de optimizacion.

## Auditoria de limpieza y consolidacion

### Hallazgos criticos

| Area | Estado actual | Riesgo | Accion recomendada |
| --- | --- | --- | --- |
| Credenciales Google Drive | No hay credenciales trackeadas; credenciales locales ignoradas fueron eliminadas | Cerrado | Mantener `app/credentials/` fuera del repo |
| Archivos basura | `.DS_Store` y `test.db` trackeados | Medio | Sacar del repo, ignorar y limpiar |
| Storage dividido | S3 queda como storage principal; ImageKit queda solo como media provider opcional para posts | Bajo | Mantener S3 por ahora |
| Embeddings | Modelo y tabla existen, servicio devuelve `None` | Alto academico | Reactivar o rediseñar como parte del motor analitico |
| Scraper duplicado | `linkedin_scraper.py` y `scrapper_propio.py` duplican logica | Medio | Mantener uno, renombrar a ingles, documentar limitaciones |
| Legacy frontend | `dashboard_old.html/css/js` trackeados | Bajo/medio | Remover si no hay dependencia activa |
| Naming | `resume_analyzer` ya normalizado; revisar otros typos si aparecen | Bajo | Mantener nombres en ingles consistentes antes de defensa |
| Dependencias | `boto3`, `imagekitio`, `google-genai`, `sentence-transformers`, `pgvector`, `apify-client` | Medio | Dejar solo dependencias alineadas al capstone |
| Data local | `data/` pesa mucho y contiene zips grandes no trackeados | Medio | Mover datasets a storage gobernado o documentar como data source local |

### Que se queda

Se debe conservar porque ayuda al capstone:

- `app/models/resumeModel.py`: base para perfiles/CVs.
- `app/core/resume_analyzer/`: extraccion y analisis de CV.
- `app/models/resourceModel.py`: puede convertirse en catalogo de cursos/recursos optimizables.
- `app/models/jobPostingModel.py`: base para ofertas laborales.
- `app/models/resumeEmbeddingsModel.py`: base para pgvector.
- `app/services/dashboardService.py`: se puede adaptar a dashboard analitico.
- `app/routes/resumeRoute.py`, `jobRoute.py`, `resourceRoute.py`: utiles si se simplifican.
- Alembic + SQLAlchemy: necesarios si FastAPI sigue siendo backend principal.
- Tests: conservar y ampliar.

### Que se debe remover o archivar

Recomendado para limpieza del repo:

- `.DS_Store` en raiz, `app/`, `app/static/`, `app/static/images/`.
- `test.db` si no es necesario.
- `app/templates/dashboard_old.html`.
- `app/static/css/dashboard_old.css`.
- `app/static/js/dashboard_old.js`.
- `app/core/JobsScraper/scrapper_propio.py` si `linkedin_scraper.py` queda como version canonical.
- Credenciales en `app/credentials/`: no deben existir en Git.
- `OAUTH_SETUP.md` si reaparece documentacion de Google Drive.
- Dependencias de storage eliminado en `pyproject.toml` y `requirements.txt`.

No borrar S3: queda como storage principal por decision de Fase 0.

### Que se debe refactorizar

| Modulo actual | Problema | Refactor sugerido |
| --- | --- | --- |
| `ResumeService` | Acoplado directamente a S3 | Crear interfaz `StorageService` y adapter S3/Supabase |
| `resumeRoute` | Upload, persistencia y analisis mezclados | Separar upload, metadata, extraction, analysis |
| `jobRoute` | Mucha logica en ruta | Mover search/scraping/analysis a servicios |
| `embeddingService` | Stub muerto | Implementar generacion real y persistencia |
| `resourceModel` | Recurso educativo, pero no catalogo optimizable | Agregar costo, horas, skills cubiertas, dificultad |
| `dashboardService` | Dashboard de producto | Crear dashboard analitico del capstone |
| `Company/Recruiter/Application` | Mucho SaaS/ATS | Mantener solo si sirve para demo; no debe ser centro del capstone |

## Decision sobre Supabase

### Estado real del repo

Hoy el proyecto no esta migrado a Supabase. No hay cliente Supabase, dependencia Supabase, config Supabase, ni llamadas a Supabase Storage/Auth en el codigo.

Lo que existe hoy:

- Base de datos via `DATABASE_URL`, compatible con Postgres generico.
- Auth propia con FastAPI Users.
- S3 para CVs y archivos de recursos.
- ImageKit para uploads de posts/media.
- Google Drive eliminado de la arquitectura; no hay uso vivo en codigo.

Por eso, Supabase debe tratarse como una decision de producto, no como una migracion automatica.

### Opcion A: Mantener Postgres + S3, recomendada por defecto

Mantener la arquitectura actual si S3 y Postgres ya funcionan bien.

Ventajas:

- Menor riesgo.
- Mantienes SQLAlchemy y Alembic.
- Mantienes FastAPI Users.
- S3 es solido para producto.
- Evitas una migracion grande antes de tener el motor analitico.
- Puedes usar Postgres + pgvector sin depender de Supabase.

Desventajas:

- Sigues administrando S3 aparte.
- Debes mantener AWS credentials y bucket policies correctamente.
- No centraliza DB + storage en una sola plataforma.

Recomendacion:

> Esta es la mejor decision por defecto si el objetivo es volver producto en 6 meses. Primero construir Data Analysis + OR-Tools; despues optimizar infraestructura.

### Opcion B: Supabase Postgres solamente

Usar Supabase solo como Postgres administrado, manteniendo FastAPI, FastAPI Users y S3.

Ventajas:

- Sigue siendo Postgres.
- Puede usar pgvector.
- No cambia storage ni auth.
- Migracion moderada si aun no hay DB productiva estable.

Desventajas:

- No elimina S3.
- No aporta mucho si ya tienes Postgres administrado funcionando.

Recomendacion:

> Buena opcion solo si todavia no tienes una base productiva definitiva o quieres pgvector administrado con setup rapido.

### Opcion C: Supabase Storage solamente

Usar Supabase Storage para CVs, datasets y recursos, manteniendo FastAPI y FastAPI Users.

Ventajas:

- Centraliza datos y archivos si tambien usas Supabase Postgres.
- Puede simplificar dashboard/admin.
- Buen encaje para datasets, reports y CVs si se diseña bien.

Desventajas:

- Requiere reescribir `S3Service`.
- Requiere migracion de archivos existentes.
- Requiere policies y signed URLs bien pensadas.

Recomendacion:

> Hacer solo despues de un spike tecnico comparando costo, complejidad y seguridad contra S3.

### Opcion D: Supabase Auth

Migrar login/usuarios/reclutadores a Supabase Auth.

Recomendacion:

> No hacerlo ahora. FastAPI Users ya esta integrado y probado. Migrar auth no mejora el capstone y puede consumir semanas. Evaluarlo despues de validar el producto.

## Arquitectura objetivo

```text
StudentsCompass
├── FastAPI backend
│   ├── Auth adapter
│   ├── Storage adapter
│   ├── Resume ingestion
│   ├── Labor market ingestion
│   ├── Skill extraction
│   ├── Skill gap scoring
│   ├── OR-Tools optimization engine
│   └── Analytics dashboard API
│
├── Postgres / Supabase Postgres
│   ├── users / profiles
│   ├── resumes
│   ├── job_postings
│   ├── skills
│   ├── job_skills
│   ├── resume_skills
│   ├── courses
│   ├── course_skills
│   ├── embeddings
│   ├── optimization_runs
│   └── optimization_recommendations
│
├── Product storage
│   ├── resumes/
│   ├── datasets/
│   ├── reports/
│   └── course_assets/
│
└── Analysis artifacts
    ├── notebooks/
    ├── cleaned datasets
    ├── evaluation tables
    └── final dashboard
```

## Nuevo modelo de datos analitico

### Skills

```text
skills
- id
- normalized_name
- display_name
- category
- aliases
- created_at
```

### Job skills

```text
job_skills
- id
- job_id
- skill_id
- importance_score
- extraction_method
- evidence_text
- created_at
```

### Resume skills

```text
resume_skills
- id
- resume_id
- user_id
- skill_id
- confidence_score
- evidence_text
- extraction_method
- created_at
```

### Courses

```text
courses
- id
- title
- provider
- url
- cost
- duration_hours
- difficulty
- rating
- is_active
- created_at
```

### Course skills

```text
course_skills
- id
- course_id
- skill_id
- coverage_score
- is_prerequisite
```

### Optimization runs

```text
optimization_runs
- id
- user_id
- resume_id
- target_role
- budget
- available_hours
- max_courses
- objective_version
- status
- total_score
- total_cost
- total_hours
- skill_coverage
- created_at
```

### Optimization recommendations

```text
optimization_recommendations
- id
- optimization_run_id
- course_id
- rank
- selected
- marginal_score
- skills_covered
- explanation
```

## Fase 0: Limpieza, seguridad y consolidacion

Duracion: 2 a 4 semanas.

Objetivo: dejar el repo limpio, reducir proveedores externos y preparar una base tecnica seria para analitica + optimizacion.

### 0.1 Seguridad inmediata

- Google Drive queda fuera del proyecto.
- Si alguna credencial Google fue usada anteriormente, debe quedar revocada fuera del repo.
- No hay credenciales Google trackeadas actualmente.
- Verificar que `.env` nunca haya sido trackeado.
- Confirmar que `app/credentials/` queda ignorado.

### 0.2 Limpieza del repo

- Sacar `.DS_Store` del repo.
- Sacar `test.db` del repo.
- Remover dashboard legacy si no se usa.
- Eliminar duplicado `scrapper_propio.py`.
- Renombrar carpetas/archivos con typos:
  - `ResumeAnalizer` -> `resume_analyzer`
  - `mockIaInetrviews.py` -> `mock_ai_interviews.py`
  - `scrapper_propio.py` -> eliminado o `linkedin_scraper.py`
- Remover `package.json` y `package-lock.json`: eran dependencias de generacion de presentaciones, no frontend de la app.

### 0.3 Decision de storage

Inventario actual:

- CVs: S3 via `S3Service`.
- Recursos: S3 via `ResourceService`/`AdminService`.
- Imagenes/posts: ImageKit por defecto, con provider S3 disponible via `MEDIA_STORAGE_PROVIDER=s3`.
- Google Drive: eliminado.
- Data local: `data/` con zips grandes y resumes.

Decision recomendada:

> Mantener S3 como storage principal por ahora. No migrar a Supabase Storage automaticamente. Google Drive queda eliminado. Mantener ImageKit solo mientras posts/media lo necesiten; usar `MEDIA_STORAGE_PROVIDER=s3` cuando se decida consolidar media en S3.

Pasos:

- Crear `StorageService` abstracto.
- Mantener `S3StorageService` como adapter actual.
- Implementar `SupabaseStorageService` solo si un spike tecnico futuro demuestra que conviene.
- `ResumeService`, `ResourceService` y media uploads ya dependen de adapters de storage.
- Migrar metadata:
  - `folder_id` -> `storage_bucket`
  - `storage_file_id` -> `storage_path`
  - `view_url` -> signed URL o public URL segun policy.

### 0.4 Decision de auth

Estado actual:

- FastAPI Users.
- JWT en cookies.
- Dos dominios auth: usuarios y reclutadores.

Decision cerrada de Fase 0:

> Mantener FastAPI Users durante el capstone. Evaluar Supabase Auth despues de que el motor analitico funcione.

Razon:

- Migrar auth consume mucho tiempo.
- No aporta tanto a Data Analysis.
- La defensa evaluara el modelo, no el proveedor de login.

Si se migra a Supabase Auth:

- Crear tabla `profiles` vinculada a `auth.users`.
- Rehacer dependencias `current_active_user`.
- Definir RLS por usuario.
- Migrar sesiones/cookies.
- Actualizar tests de auth.

### 0.5 Decision de database

Estado actual:

- SQLAlchemy async.
- Alembic.
- Postgres compatible.
- SQLite para tests.
- pgvector ya presente.

Decision cerrada de Fase 0:

> Mantener Postgres generico via `DATABASE_URL`. Supabase Postgres es una opcion valida futura, pero no obligatoria ahora.

Esto permite:

- Mantener codigo actual.
- Usar pgvector.
- Usar pgvector sin reescritura total.
- Evitar reescritura total.

### 0.6 Resultado esperado de Fase 0

Al final de la fase 0, el repo deberia quedar asi:

```text
External providers:
- Postgres administrado
- Un solo storage principal: S3
- Google GenAI o proveedor LLM elegido

Eliminados:
- Google Drive
- Storage secundario innecesario
- ImageKit queda solo como provider opcional de posts/media hasta consolidar media en S3
- Credenciales trackeadas
- Archivos legacy
- Archivos basura
```

## Fase 1: Replanteamiento academico

Duracion: 1 semana.

Entregables:

- Titulo final.
- Pregunta de investigacion.
- Objetivos.
- Alcance: 2 o 3 roles objetivo.
- Metricas de exito.
- Diagrama del pipeline.

Roles recomendados:

- Data Analyst.
- Business Analyst.
- Junior Data Scientist.

## Fase 2: Data pipeline laboral

Duracion: 3 a 4 semanas.

Fuentes recomendadas:

- Job Bank Canada como fuente principal.
- O*NET para taxonomia de skills.
- Dataset publico de cursos o catalogo curado.
- Resumes locales para prototipo.

Entregables:

- `jobs_raw`.
- `jobs_clean`.
- `skills_taxonomy`.
- `courses`.
- Diccionario de datos.
- Script reproducible de carga/limpieza.

## Fase 3: EDA serio

Duracion: 3 semanas.

Analisis minimos:

- Top skills por rol.
- Skills por ciudad/provincia.
- Salario por skill.
- Co-ocurrencia de skills.
- Diferencias entre roles.
- Seniority distribution.
- Missing values y outliers.
- Heatmap role-skill.

Entregables:

- Notebook `01_labor_market_eda.ipynb`.
- Graficos limpios.
- 8 a 12 insights.
- Dataset final versionado.

## Fase 4: Skill extraction y normalizacion

Duracion: 3 semanas.

Objetivo:

Convertir texto en datos estructurados.

Metodos:

- Diccionario de skills.
- Reglas/aliases.
- Embeddings para similitud semantica.
- LLM como apoyo, no como unica verdad.

Entregables:

- `SkillExtractionService`.
- `SkillNormalizer`.
- Tablas `job_skills` y `resume_skills`.
- Evaluacion manual sobre muestra.

## Fase 5: Skill gap scoring

Duracion: 3 semanas.

Formula conceptual:

```text
skill_gap_score =
  required_skill_weight
  - student_skill_evidence
```

El peso de una skill debe combinar:

- Frecuencia en trabajos objetivo.
- Importancia por rol.
- Asociacion con salario.
- Seniority.
- Criticidad academica o profesional.

Entregables:

- Ranking de gaps por estudiante/rol.
- Explicaciones por skill.
- Tests con perfiles sinteticos.

## Fase 6: Optimization engine con OR-Tools

Duracion: 5 semanas.

Problema:

Elegir un conjunto y una secuencia de cursos que maximicen readiness laboral
para un rol objetivo, cerrando skills faltantes de alto valor y respetando
restricciones reales del estudiante: presupuesto, tiempo disponible, numero
maximo de cursos, prerequisitos, dificultad y redundancia.

Esta es la fase central del capstone. El diferencial no es recomendar cursos de
forma generica, sino formular el problema como optimizacion restringida,
resolverlo con OR-Tools CP-SAT y producir una explicacion auditable de por que
cada curso fue seleccionado.

Documento formal:

- `docs/capstone_product/phase_6_optimization_model.md`.

Variables principales:

```text
x_i = 1 si el curso i es seleccionado
x_i = 0 si no
y_s = 1 si la skill s queda cubierta por la ruta
u_s = cobertura agregada de la skill s
m_s = 1 si la skill s queda sin cubrir
r_s = cobertura redundante de la skill s
pos_i = posicion del curso i dentro de la ruta
```

Objetivo:

```text
Maximize:
  weighted_skill_gap_coverage
  + labor_market_demand_coverage
  + salary_impact_coverage
  + critical_skill_coverage
  + course_quality_value
  - normalized_cost_penalty
  - normalized_time_penalty
  - redundancy_penalty
  - difficulty_progression_penalty
  - uncovered_gap_penalty
```

Restricciones:

```text
total_cost <= budget
total_hours <= available_hours
selected_courses <= max_courses
critical_skills_covered >= minimum_required
coverage_s >= threshold_s if skill s is counted as covered
inactive courses cannot be selected
equivalent duplicate courses cannot be selected together
prerequisite courses must be selected before dependent courses
selected courses must have unique route positions
difficulty progression must be reasonable or penalized
```

Entregables:

- `app/core/optimization/learning_path_optimizer.py`.
- Modelo CP-SAT con OR-Tools.
- Casos de prueba.
- Documentacion matematica.
- Output explicable.
- Comparacion posterior contra baselines de Fase 7.

## Fase 7: Evaluacion contra baselines

Duracion: 3 semanas.

Baselines:

- Cursos mas populares.
- Cursos mas baratos.
- Cursos por similitud semantica.
- Seleccion aleatoria controlada.

Metricas:

- Skill coverage.
- Critical skill coverage.
- Total cost.
- Total hours.
- Score per dollar.
- Score per hour.
- Redundancy rate.
- Constraint satisfaction.

Tabla objetivo:

```text
Method              Coverage   Cost   Hours   Critical Skills   Score
Popular courses     62%        $80    50      4/7               0.61
Cheapest courses    48%        $20    35      3/7               0.44
Similarity only     74%        $150   65      5/7               0.72
OR-Tools model      87%        $120   42      6/7               0.86
```

## Fase 8: Integracion en StudentsCompass

Duracion: 3 semanas.

Crear una seccion nueva:

```text
Career Optimization Lab
```

Flujo:

```text
Upload CV -> Choose Target Role -> Analyze Gap -> Optimize Learning Path -> View Dashboard
```

Pantallas:

- Labor market dashboard.
- Resume skill profile.
- Target role selector.
- Skill gap report.
- Optimized learning path.
- Baseline comparison.

## Fase 9: Escritura y defensa

Duracion: 2 semanas.

Estructura:

1. Introduction.
2. Problem Statement.
3. Data Sources.
4. EDA.
5. Skill Extraction.
6. Skill Gap Scoring.
7. Optimization Model.
8. Evaluation.
9. Prototype.
10. Limitations.
11. Future Work.

Limitaciones honestas:

- Los datos laborales pueden estar sesgados.
- La extraccion de skills no prueba dominio real.
- Salario y skills no implican causalidad perfecta.
- Cursos no garantizan empleabilidad.
- LLM puede fallar; por eso se valida con reglas y muestras.

## Roadmap de implementacion de 6 meses

| Mes | Enfoque | Entregable principal |
| --- | --- | --- |
| 1 | Limpieza, seguridad, consolidacion, alcance | Repo limpio + arquitectura objetivo |
| 2 | Data pipeline + EDA | Dataset laboral limpio + notebook EDA |
| 3 | Skill extraction + normalizacion | Skills estructuradas de jobs y CVs |
| 4 | Skill gap + catalogo de cursos | Ranking de gaps + course-skill matrix |
| 5 | OR-Tools + evaluacion | Optimizador + comparacion contra baselines |
| 6 | Dashboard + documento final | Career Optimization Lab + defensa |

## Backlog tecnico priorizado

### P0 - Seguridad y limpieza

- Google Drive eliminado del repo y del workspace local.
- `app/credentials/` ignorado; no hay credenciales trackeadas.
- `.DS_Store`, `test.db`, dashboard legacy y duplicados no estan trackeados.
- Storage principal decidido: S3.
- Auth/database decididos: mantener FastAPI Users y Postgres via `DATABASE_URL`.

### P1 - Base analitica

- Crear tablas `skills`, `job_skills`, `resume_skills`, `courses`, `course_skills`.
- Reactivar embeddings.
- Crear pipeline de jobs.
- Crear notebook EDA.

### P2 - Optimizacion

- Agregar OR-Tools.
- Construir modelo CP-SAT.
- Crear baselines.
- Crear metricas.

### P3 - Producto/demo

- Crear `Career Optimization Lab`.
- Integrar upload CV -> skill gap -> optimized path.
- Crear visualizaciones.

## Como deberia quedar la historia final

La narrativa final debe ser:

> StudentsCompass uses labor market data to identify skill demand, extracts a student's current skills from their resume, measures the gap against a target role, and uses constrained optimization to recommend the most efficient learning path under budget, time, and difficulty constraints.

En español:

> StudentsCompass usa datos del mercado laboral para identificar demanda de habilidades, extrae las habilidades actuales del estudiante desde su CV, mide la brecha frente a un rol objetivo y usa optimizacion con restricciones para recomendar la ruta de aprendizaje mas eficiente segun presupuesto, tiempo y dificultad.

## Decision final recomendada

Para el capstone, la mejor ruta es:

1. Mantener FastAPI.
2. Mantener Postgres via `DATABASE_URL`; Supabase Postgres no es requisito ahora.
3. Mantener S3 como storage principal.
4. Mantener FastAPI Users por ahora.
5. Google Drive queda eliminado.
6. Mantener ImageKit solo como provider opcional de posts/media hasta consolidar media en S3.
7. Reactivar pgvector.
8. Construir el motor OR-Tools como el centro academico.
9. Usar StudentsCompass solo como demo/interface.

Esto convierte el proyecto de "SaaS con IA" a "sistema analitico con optimizacion defendible".
