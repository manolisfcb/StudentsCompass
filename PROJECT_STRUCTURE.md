# 🧭 Student Compass — Estructura del Proyecto y Features

**Your Career. Your Direction.**

Student Compass es una plataforma de navegación de carrera profesional para estudiantes, enfocada especialmente en el mercado laboral canadiense. En lugar de actuar como un portal de empleo, se centra en el **autodescubrimiento, la preparación y el posicionamiento estratégico**, empoderando a los estudiantes a perseguir las oportunidades correctas con intención.

---

## 📋 Resumen Técnico

- **Backend:** Python con **FastAPI**
- **Base de datos:** PostgreSQL (con soporte para SQLite en testing) + **Alembic** para migraciones
- **Frontend:** Templates HTML con **Jinja2** + CSS/JS estáticos
- **IA:** Integración con **Google GenAI** (Gemini) y **Sentence Transformers** para embeddings
- **Almacenamiento:** **AWS S3** (via boto3) como storage principal; **ImageKit** queda como provider opcional para media de posts
- **Autenticación:** **FastAPI-Users** (JWT)
- **Scraping:** **Apify** + **BeautifulSoup4**

---

## 🗂️ Estructura del Proyecto

```
StudentsCompass/
├── main.py                    # Punto de entrada (Uvicorn, puerto 8000)
├── pyproject.toml             # Dependencias del proyecto (uv/pip)
├── alembic.ini                # Configuración de Alembic
├── .env                       # Variables de entorno
├── alembic/                   # Migraciones de base de datos
│
├── app/
│   ├── app.py                 # Configuración de FastAPI (CORS, routers, lifespan)
│   ├── db.py                  # Conexión a base de datos
│   ├── logging.py             # Configuración de logging
│   │
│   ├── models/                # 📦 Modelos SQLAlchemy (ORM)
│   │   ├── userModel.py           # Usuario
│   │   ├── resumeModel.py         # Currículum
│   │   ├── resumeEmbeddingsModel.py  # Embeddings vectoriales del CV
│   │   ├── questionnaireModel.py  # Cuestionario de autodescubrimiento
│   │   ├── jobPostingModel.py     # Publicaciones de empleo
│   │   ├── jobAnalysisModel.py    # Análisis de empleos
│   │   ├── applicationModel.py    # Postulaciones
│   │   ├── companyModel.py        # Empresas
│   │   ├── communityModel.py      # Comunidades
│   │   ├── communityPostModel.py  # Posts de comunidades
│   │   ├── postModel.py           # Posts generales
│   │   ├── resourceModel.py       # Recursos educativos
│   │   └── userStatsModel.py      # Estadísticas del usuario
│   │
│   ├── schemas/               # 📐 Schemas Pydantic (validación de datos)
│   │   ├── userSchema.py          # Esquema de usuario (UserCreate, UserRead, UserUpdate)
│   │   ├── resumeSchema.py        # Esquema de currículum
│   │   ├── resumeEmbeddingSchema.py # Esquema de embeddings
│   │   ├── jobPostingSchema.py    # Esquema de publicaciones de empleo
│   │   ├── applicationSchema.py   # Esquema de postulaciones
│   │   ├── communitySchema.py     # Esquema de comunidades
│   │   ├── companySchema.py       # Esquema de empresas
│   │   ├── questionnaireSchema.py # Esquema del cuestionario
│   │   ├── resourceSchema.py      # Esquema de recursos
│   │   ├── postSchema.py          # Esquema de posts
│   │   ├── profileSchema.py       # Esquema de perfil
│   │   └── userStatsSchema.py     # Esquema de estadísticas
│   │
│   ├── routes/                # 🛣️ Endpoints de la API (REST)
│   │   ├── dashboardRoute.py      # Dashboard del estudiante
│   │   ├── jobRoute.py            # Empleos (scraping, análisis, matching)
│   │   ├── communityRoute.py      # Comunidades y feed
│   │   ├── resumeRoute.py         # Gestión y análisis de CVs
│   │   ├── questionnaireRoute.py  # Cuestionarios de autodescubrimiento
│   │   ├── companyRoute.py        # Gestión de empresas
│   │   ├── resourceRoute.py       # Recursos educativos
│   │   ├── postRoute.py           # Posts generales
│   │   └── profileRoute.py       # Perfil de usuario
│   │
│   ├── services/              # ⚙️ Lógica de negocio
│   │   ├── dashboardService.py    # Lógica del dashboard y estadísticas
│   │   ├── communityService.py    # Lógica de comunidades y posts
│   │   ├── userService.py         # Autenticación (FastAPI-Users, JWT)
│   │   ├── resumeService.py       # Procesamiento y análisis de CVs
│   │   ├── embeddingService.py    # Generación de embeddings vectoriales
│   │   ├── questionnaireService.py # Lógica del cuestionario
│   │   ├── resourceService.py     # Gestión de recursos educativos
│   │   ├── companyService.py      # Gestión de empresas
│   │   ├── s3Service.py           # Integración con AWS S3
│   │   ├── images.py              # Procesamiento de imágenes (ImageKit)
│   │   ├── postService.py         # Lógica de posts
│   │   └── profileService.py     # Lógica de perfil
│   │
│   ├── core/                  # 🧠 Módulos Especializados (IA y Scraping)
│   │   ├── JobsScraper/           # Scraping de ofertas de empleo (Apify)
│   │   └── resume_analyzer/        # Análisis de CVs con IA (Google Gemini)
│   │
│   ├── views/                 # 🖼️ Vistas (renderización de templates)
│   │   └── views.py              # Rutas que sirven páginas HTML
│   │
│   ├── templates/             # 🎨 Templates HTML (Jinja2)
│   │   ├── base.html              # Layout base (header, footer, meta tags)
│   │   ├── home.html              # Página principal / landing
│   │   ├── login.html             # Página de login
│   │   ├── register.html          # Página de registro
│   │   ├── dashboard.html         # Dashboard del estudiante
│   │   ├── questionnaire.html     # Cuestionario de autodescubrimiento
│   │   ├── jobs.html              # Búsqueda y listado de empleos
│   │   ├── community.html         # Vista de comunidad
│   │   ├── community_feed.html    # Feed de publicaciones de comunidad
│   │   ├── roadmap.html           # Roadmap de carrera personalizado
│   │   ├── userProfile.html       # Perfil completo del usuario
│   │   ├── resources.html         # Listado de recursos educativos
│   │   ├── resource_detail.html   # Detalle de un recurso
│   │   ├── company-dashboard.html # Dashboard para empresas
│   │   └── includes/             # Componentes parciales reutilizables
│   │
│   ├── static/                # 📁 Archivos Estáticos
│   │   ├── css/                   # Hojas de estilo
│   │   ├── js/                    # JavaScript del frontend
│   │   └── images/                # Imágenes e íconos
│   │
│   └── data/
│       └── questionnaires/        # Datos estáticos del cuestionario
│
├── scripts/                   # 🔧 Scripts Utilitarios
│   ├── migrate_sqlite_to_postgres.py  # Migración SQLite → PostgreSQL
│   ├── seed_communities.py            # Seed de comunidades iniciales
│   ├── seed_resources.py              # Seed de recursos educativos
│   └── test_embedding.py             # Tests de embeddings
│
└── tests/                     # ✅ Tests Automatizados (Pytest)
    ├── conftest.py                # Configuración de fixtures
    ├── test_auth.py               # Tests de autenticación
    ├── test_applications.py       # Tests de postulaciones
    ├── test_dashboard.py          # Tests del dashboard
    └── test_resume.py             # Tests del currículum
```

---

## 🌟 Features Principales

### 1. 🔐 Autenticación y Gestión de Usuarios

- Registro y login con **JWT** (JSON Web Tokens)
- Gestión de sesiones con **FastAPI-Users**
- Reset de contraseña vía email
- Verificación de cuenta por email
- Perfil de usuario con foto de perfil (subida a ImageKit/S3)
- CRUD completo de usuarios

### 2. 🧭 Journey de 7 Pasos (Core del Producto)

El journey está estructurado en **7 pasos guiados**, cada uno diseñado para construir sobre el anterior. No hay respuestas correctas ni incorrectas — el objetivo es la claridad, no la evaluación.

| Paso | Nombre | Descripción |
|------|--------|-------------|
| 1 | **My Compass** (Discover Yourself) | Cuestionario de autodescubrimiento: preferencias, estilos de trabajo, soft skills, motivaciones |
| 2 | **Resume & CV** (Toolkit: Resume) | Alineación del CV con el perfil personal. Formato canadiense, método STAR |
| 3 | **LinkedIn** (Toolkit: LinkedIn) | Optimización del perfil de LinkedIn como herramienta de descubrimiento |
| 4 | **Community** (Building Your Network) | Networking y construcción de relaciones profesionales estratégicas |
| 5 | **AI Coach** (Interview Preparation) | Preparación para entrevistas con IA, práctica de preguntas comunes |
| 6 | **Job Hunting** (Curated Sources) | Búsqueda estratégica de empleo con fuentes curadas |
| 7 | **Thought Leader** (LinkedIn Thought Leader) | Acceso al mercado laboral oculto (~70% de roles nunca se publican) |

### 3. 📝 Cuestionario de Autodescubrimiento

- Preguntas interactivas sobre preferencias laborales, habilidades blandas y motivaciones
- Sin respuestas correctas o incorrectas
- Generación de **perfil personalizado** con IA (Google Gemini)
- Sugerencia de roles con **baja barrera de entrada**
- Exploración de **posiciones remote-friendly**
- Recomendación de **certificaciones** (solo si es necesario)

### 4. 📄 Análisis de CV con IA (Resume Analyzer)

- Subida de CV en formato **PDF** (procesado con PyMuPDF)
- Análisis inteligente con **Google Gemini AI**
- Generación de **embeddings vectoriales** del CV usando:
  - **Sentence Transformers** para la generación de vectores
  - **pgvector** (extensión de PostgreSQL) para almacenamiento y búsqueda vectorial
- **Matching semántico** entre CV y ofertas de empleo
- Sugerencias de mejora del CV alineadas al formato canadiense

### 5. 💼 Búsqueda y Gestión de Empleos

- **Scraping automatizado** de ofertas de empleo con **Apify** + **BeautifulSoup4**
- Análisis de compatibilidad CV ↔ empleo con IA
- Gestión de **postulaciones** (applications): crear, seguir estado, actualizar
- **Análisis de empleos** (jobAnalysis): evaluación detallada de cada oferta
- Dashboard de empresas con sus ofertas activas

### 6. 👥 Comunidades

- Creación y gestión de comunidades temáticas
- Feed de publicaciones dentro de cada comunidad
- Sistema de posts con interacciones
- Seeds de comunidades iniciales predefinidas

### 7. 📊 Dashboard del Estudiante

- Estadísticas del usuario (userStats)
- Progreso en el journey de 7 pasos
- **Roadmap de carrera** personalizado
- Visualización del estado de postulaciones
- Métricas y análisis del perfil

### 8. 📚 Recursos Educativos

- Catálogo curado de recursos de aprendizaje
- Vista de detalle por recurso
- Videos educativos organizados por paso del journey
- Seeds con contenido inicial precargado

### 9. 🏢 Dashboard de Empresas

- Vista dedicada para empresas (`company-dashboard.html`)
- Gestión de la información de la empresa
- Publicación y gestión de ofertas de empleo

---

## 🛣️ Endpoints de la API

Todos los endpoints de la API están bajo el prefijo `/api/v1`, excepto las vistas HTML y la autenticación:

| Prefijo | Router | Tags | Descripción |
|---------|--------|------|-------------|
| `/auth/jwt` | Auth Router | auth | Login/Logout con JWT |
| `/api/v1/auth` | Register/Verify/Reset | auth | Registro, verificación, reset de contraseña |
| `/api/v1/users` | Users Router | users | CRUD de usuarios |
| `/api/v1` | Post Router | — | Posts generales |
| `/api/v1` | Questionnaire Router | questionnaire | Cuestionarios |
| `/api/v1` | Resume Router | resume | Gestión de CVs |
| `/api/v1` | Job Router | jobs | Empleos, scraping y análisis |
| `/api/v1` | Company Router | companies | Empresas |
| `/api/v1` | Dashboard Router | dashboard | Dashboard y estadísticas |
| `/api/v1` | Community Router | communities | Comunidades |
| `/api/v1` | Resource Router | resources | Recursos educativos |
| `/` | Views Router | views | Páginas HTML (templates) |

### Endpoints Adicionales

| Ruta | Descripción |
|------|-------------|
| `/sitemap.xml` | Sitemap XML para SEO |
| `/robots.txt` | Directivas para crawlers |
| `/favicon.ico` | Ícono del sitio |

---

## 🛠️ Stack Tecnológico Completo

| Categoría | Tecnología | Versión Mínima |
|-----------|-----------|----------------|
| **Framework** | FastAPI | ≥ 0.128.0 |
| **Servidor** | Uvicorn (standard) | ≥ 0.39.0 |
| **ORM** | SQLAlchemy (async, via FastAPI-Users) | — |
| **Base de Datos** | PostgreSQL + asyncpg | ≥ 0.29.0 |
| **BD (driver sync)** | psycopg / psycopg2-binary | ≥ 3.1.0 / ≥ 2.9.11 |
| **Vectores** | pgvector | ≥ 0.4.2 |
| **Migraciones** | Alembic | ≥ 1.18.1 |
| **Autenticación** | FastAPI-Users (JWT) | ≥ 14.0.2 |
| **IA Generativa** | Google GenAI (Gemini) | ≥ 1.59.0 |
| **Embeddings** | Sentence Transformers | ≥ 3.3.1 |
| **PDF** | PyMuPDF | ≥ 1.26.7 |
| **Scraping** | Apify Client | ≥ 2.4.0 |
| **HTML Parsing** | BeautifulSoup4 | ≥ 4.12.3 |
| **Storage (Cloud)** | boto3 (AWS S3) | ≥ 1.35.0 |
| **Media opcional** | ImageKit + Pillow | ≥ 5.0.0 / ≥ 12.1.0 |
| **Templates** | Jinja2 | ≥ 3.1.6 |
| **Config** | python-dotenv | ≥ 1.2.1 |
| **BD Testing** | aiosqlite | ≥ 0.22.1 |
| **Testing** | Pytest + pytest-asyncio + pytest-cov | — |
| **HTTP Client (test)** | httpx | ≥ 0.28.1 |
| **Python** | CPython | ≥ 3.10 |

---

## 🧠 Filosofía del Producto

- ❌ **No** es un portal de empleo (job board)
- ❌ **No** es un ATS (Applicant Tracking System)
- ❌ **No** es una plataforma de ranking o evaluación
- ✅ **Sí** es una herramienta de autodescubrimiento y orientación profesional
- ✅ **Sí** ayuda a los estudiantes a encontrar dirección para construir carreras significativas

> *"We don't sell jobs. We cultivate careers."*

---

## 🏁 Resultado para los Estudiantes

Al finalizar el journey, los estudiantes:
- Tienen claridad sobre su dirección profesional
- Saben en qué trabajar (y en qué no)
- Se sienten confiados navegando el mercado laboral
- Están preparados — no abrumados

---

## 🔧 Scripts Disponibles

| Script | Descripción |
|--------|-------------|
| `scripts/migrate_sqlite_to_postgres.py` | Migra datos de SQLite a PostgreSQL |
| `scripts/seed_communities.py` | Carga comunidades iniciales en la BD |
| `scripts/seed_resources.py` | Carga recursos educativos iniciales |
| `scripts/test_embedding.py` | Prueba la generación de embeddings |

---

## ✅ Tests

Los tests se ejecutan con **pytest** y cubren:

| Test | Descripción |
|------|-------------|
| `test_auth.py` | Registro, login, JWT, sesiones |
| `test_applications.py` | CRUD de postulaciones |
| `test_dashboard.py` | Dashboard y estadísticas |
| `test_resume.py` | Subida y procesamiento de CVs |

### Ejecución

```bash
# Ejecutar todos los tests
pytest

# Con cobertura
pytest --cov=app

# Test específico
pytest tests/test_auth.py -v
```

---

## 🚀 Ejecución del Proyecto

```bash
# Instalar dependencias
uv sync

# Ejecutar en modo desarrollo
python main.py
# o
uvicorn app.app:app --host 0.0.0.0 --port 8000 --reload
```

El servidor arranca en `http://localhost:8000`.

---

*Documento generado el 22 de febrero de 2026*
