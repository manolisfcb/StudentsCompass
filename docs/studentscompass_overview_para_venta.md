# StudentsCompass - Overview completo para entender y vender el sistema

## 1. Resumen ejecutivo

StudentsCompass es una plataforma de preparacion profesional para estudiantes y recien graduados, enfocada especialmente en el mercado laboral canadiense. Su promesa central es convertir a un estudiante confundido, con poca claridad laboral y herramientas dispersas, en un candidato mas preparado, mas alineado y mas facil de evaluar por empresas.

La plataforma no se plantea solo como una bolsa de empleo. Su diferenciador es que une tres mundos que normalmente estan separados:

- Preparacion del estudiante: autoconocimiento, CV, LinkedIn, entrevistas, recursos y roadmaps.
- Busqueda laboral estructurada: empleos, postulaciones, seguimiento y matching con el perfil del candidato.
- Valor para empresas: publicar vacantes, revisar candidatos, administrar reclutadores y reducir tiempo de screening.

En una frase:

> StudentsCompass no vende empleos; construye candidatos listos para el mercado.

## 2. El problema que resuelve

Muchos estudiantes quieren trabajar, pero no saben como presentarse, que roles buscar, que habilidades priorizar ni como explicar su valor. Al mismo tiempo, las empresas reciben muchos CVs, pero les cuesta identificar quienes estan realmente preparados, alineados con el rol y motivados para crecer.

El problema tiene dos lados:

Para estudiantes:

- Aplican a demasiados trabajos sin estrategia.
- Tienen CVs que describen tareas, no logros.
- No saben adaptar su perfil al mercado canadiense.
- Usan LinkedIn como un repositorio, no como una herramienta de descubrimiento.
- Se preparan para entrevistas tarde o de manera improvisada.
- Saltan entre consejos, cursos, PDFs, videos y portales sin un camino claro.

Para empresas:

- Reciben volumen, pero no necesariamente calidad.
- Pierden tiempo revisando candidatos poco alineados.
- Tienen poca visibilidad sobre la preparacion real de un estudiante.
- Los perfiles entry-level suelen parecer similares.
- El costo de una mala contratacion o una rotacion temprana puede ser alto.

StudentsCompass conecta ambos lados con una idea simple: preparar mejor al talento antes de que llegue a la empresa.

## 3. Que es StudentsCompass

StudentsCompass es un ecosistema de carrera profesional. Ayuda al estudiante a pasar por un proceso guiado de claridad, preparacion, aprendizaje, busqueda y postulacion. A la vez, entrega a las empresas un espacio para publicar oportunidades y revisar candidatos con mas contexto que un CV suelto.

La experiencia se organiza alrededor de una ruta de preparacion profesional:

1. Descubrir el perfil del estudiante.
2. Mejorar el CV y hacerlo mas relevante.
3. Optimizar LinkedIn y posicionamiento profesional.
4. Construir red y comunidad.
5. Prepararse para entrevistas.
6. Buscar y aplicar a empleos con intencion.
7. Convertirse en una presencia profesional mas visible.

El producto mezcla formacion, tecnologia, IA, comunidad y reclutamiento.

## 4. Propuesta de valor

### Para estudiantes

StudentsCompass le da al estudiante un sistema completo para dejar de improvisar su carrera. El usuario puede crear su perfil, completar un cuestionario de autodescubrimiento, subir su CV, recibir feedback de IA, acceder a recursos, seguir roadmaps, buscar empleos, guardar progreso y controlar sus postulaciones.

Beneficios principales:

- Claridad sobre que tipo de roles buscar.
- Mejor CV, alineado a expectativas del mercado canadiense.
- Roadmaps practicos para desarrollar habilidades.
- Recursos curados para CV, LinkedIn, entrevistas y empleabilidad.
- Comunidad para aprender con otros estudiantes.
- Seguimiento de aplicaciones y progreso.
- Experiencia centralizada en vez de usar herramientas desconectadas.

### Para empresas

StudentsCompass ofrece a las empresas acceso a estudiantes que ya pasaron por un proceso de preparacion. Las empresas pueden crear su perfil, manejar reclutadores, publicar vacantes, recibir aplicaciones y revisar candidatos desde un dashboard.

Beneficios principales:

- Candidatos mas preparados y mejor alineados.
- Menos ruido que una bolsa de empleo tradicional.
- Publicacion y gestion de ofertas.
- Vista de candidatos y postulaciones.
- Seguimiento de estados: aplicado, en revision, entrevista, oferta, rechazado o retirado.
- Soporte para coordinacion de entrevistas.
- Mejor presencia de marca empleadora frente a talento joven.

## 5. Diferenciador comercial

La diferencia frente a un job board tradicional es que StudentsCompass no empieza en la vacante; empieza en la preparacion del estudiante.

Un portal de empleo tradicional responde a la pregunta:

> Donde puedo aplicar?

StudentsCompass responde a preguntas mas importantes:

> Para que roles estoy listo?
> Que me falta para ser competitivo?
> Como mejoro mi CV, LinkedIn y entrevistas?
> Como aplico con intencion?
> Como puede una empresa confiar mas rapido en mi perfil?

Esto permite vender la plataforma como una infraestructura de career readiness y no solo como un marketplace laboral.

## 6. Usuarios principales

### Estudiante

Es el usuario central. Puede registrarse, completar su perfil, subir CVs, hacer cuestionarios, consumir recursos, avanzar en roadmaps, participar en comunidad, enviar mensajes, buscar empleos y gestionar postulaciones.

### Empresa

Es el comprador o partner potencial. Puede registrar empresa, publicar oportunidades, administrar candidatos y coordinar el flujo de reclutamiento.

### Reclutador de empresa

Usuario asociado a una empresa. El sistema permite roles como owner, admin, recruiter y viewer. Esto es importante porque una empresa real puede tener varias personas usando el sistema.

### Administrador de plataforma

Gestiona usuarios, comunidades, recursos, empleos, empresas y aplicaciones desde un panel administrativo.

## 7. Flujo del estudiante

### 1. Registro y perfil

El estudiante crea una cuenta y completa informacion basica: nombre, email, telefono, direccion, edad, nickname y otros datos de perfil. El sistema usa autenticacion con JWT y FastAPI Users.

### 2. Cuestionario de autodescubrimiento

El cuestionario ayuda a identificar preferencias, estilos de trabajo, motivaciones y posibles rutas profesionales. Las respuestas se guardan y generan resultados por carrera o area.

Este modulo no busca calificar al estudiante. Busca darle direccion.

### 3. CV y analisis con IA

El estudiante puede subir su CV. El sistema almacena el archivo, extrae texto y utiliza IA para generar resumen, keywords y feedback. Tambien puede hacer auditorias de CV asociadas a cursos, con score, reporte, fortalezas, debilidades y recomendaciones.

Esto sirve para convertir un CV generico en una herramienta orientada a roles concretos.

### 4. Recursos educativos

El estudiante accede a una biblioteca de recursos. Los recursos pueden estar organizados por modulos y lecciones. El sistema registra progreso por leccion y puede priorizar recursos obligatorios como:

- Resume Templates
- LinkedIn Optimization
- Interview Preparation

### 5. Roadmaps personalizados

Los roadmaps son rutas de aprendizaje para roles especificos. Por ejemplo, existe una ruta de Web Developer que incluye etapas, tareas, duracion, recursos, proyectos y criterios de evaluacion.

Cada roadmap puede incluir:

- Stages o etapas.
- Tareas de lectura, practica, aprendizaje, construccion o video.
- Proyectos.
- Rubricas.
- Progreso del usuario.
- Entregas con repo, live URL y notas.

Esto transforma la preparacion en una ruta accionable, no en consejos sueltos.

### 6. Busqueda de empleos

El estudiante puede ver ofertas publicas y buscar por keywords o ubicacion. El sistema tambien puede analizar el CV para generar keywords y usarlas como base para encontrar oportunidades relevantes.

### 7. Postulaciones

El estudiante puede crear aplicaciones y hacer seguimiento del estado. Cada aplicacion puede estar asociada a:

- Usuario.
- Empresa.
- Vacante.
- CV usado.
- Recruiter asignado.
- Estado.
- Match strength.
- URL de aplicacion.
- Notas.
- Disponibilidad de entrevistas.

### 8. Comunidad y networking

El sistema incluye comunidades tematicas, publicaciones, likes, comentarios, solicitudes de amistad y mensajes directos. Esto convierte la plataforma en un espacio de acompanamiento, no solo de transaccion laboral.

## 8. Flujo de empresa

### 1. Registro de empresa

Una empresa puede crear su cuenta y perfil con nombre, industria, descripcion, website, ubicacion, contacto y telefono.

### 2. Equipo de reclutadores

La empresa puede administrar reclutadores con roles. Esto permite que la plataforma escale a equipos reales de hiring.

Roles soportados:

- Owner
- Admin
- Recruiter
- Viewer

### 3. Publicacion de empleos

La empresa puede crear ofertas con detalles como:

- Titulo.
- Descripcion.
- Requisitos.
- Responsabilidades.
- Ubicacion.
- Tipo de empleo.
- Modalidad: remoto, hibrido u onsite.
- Seniority.
- Rango salarial.
- Beneficios.
- URL de aplicacion.
- Fecha de expiracion.
- Estado activo/inactivo.

### 4. Dashboard de empresa

La empresa ve metricas como:

- Vacantes activas.
- Total de aplicaciones.
- Entrevistas agendadas.
- Candidatos shortlisted o en revision.
- Publicaciones recientes y volumen de aplicaciones por vacante.

### 5. Gestion de candidatos

La empresa puede listar aplicaciones, filtrar por vacante o estado, revisar CVs, actualizar estado de candidatos y gestionar disponibilidad de entrevistas.

Esta parte es clave para vender a empresas: no solo publican, tambien administran pipeline.

## 9. Modulos principales del sistema

### Autenticacion y usuarios

Maneja registro, login, usuarios activos, verificacion y gestion de cuenta. La plataforma usa JWT y FastAPI Users.

### Perfil

Permite consultar y actualizar informacion personal del usuario. El perfil alimenta otras partes del sistema: dashboard, aplicaciones, comunidad y CV.

### Cuestionario

Contiene preguntas, respuestas y resultados ponderados. Sirve como base de autoconocimiento y direccion profesional.

### CV y analisis con IA

Permite subir CVs, almacenarlos, extraer texto, generar resumen, keywords, analisis y auditorias. Usa IA para convertir informacion no estructurada en insights utiles.

### Jobs

Incluye job board, busqueda publica, busqueda por keywords, ofertas creadas por empresas y analisis del CV para sugerir busquedas.

### Aplicaciones

Gestiona el ciclo de postulacion del estudiante y la vista del pipeline para empresas. Es el puente entre preparacion y reclutamiento.

### Empresas y reclutadores

Gestiona perfiles de empresas, miembros del equipo, permisos basicos y operaciones de reclutamiento.

### Dashboard de estudiante

Muestra progreso general, aplicaciones recientes, breakdown de estados, recursos clave y datos de perfil.

### Dashboard de empresa

Muestra actividad de vacantes, aplicaciones, entrevistas y candidatos.

### Recursos

Biblioteca de contenido con modulos, lecciones, progreso, archivos y control de publicacion/bloqueo.

### Roadmaps

Rutas de aprendizaje por rol con etapas, tareas, proyectos, rubricas y progreso del usuario.

### Comunidad

Comunidades, membresias, posts, likes, comentarios y feeds enriquecidos.

### Amistades y mensajes

Solicitudes de amistad, lista de amigos, conversaciones directas, mensajes y read receipts.

### Administracion

Panel para administrar usuarios, comunidades, recursos, trabajos, empresas y aplicaciones.

### Cuotas de IA

Controla limites diarios de uso de IA por usuario y por feature. Esto es importante para controlar costos y habilitar planes pagos en el futuro.

## 10. Como funciona la IA dentro del producto

La IA aparece como una capa de asistencia, no como reemplazo del criterio humano.

Usos actuales:

- Analizar CVs.
- Extraer resumen profesional.
- Generar keywords del perfil.
- Auditar CV dentro del curso.
- Producir feedback estructurado.
- Ayudar a orientar busquedas laborales.

Tambien hay soporte para embeddings y busqueda vectorial con Sentence Transformers y pgvector, lo que permite evolucionar hacia matching mas semantico entre candidatos, CVs, habilidades y vacantes.

## 11. Stack tecnico

StudentsCompass esta construido como una aplicacion web full-stack con backend en Python y frontend renderizado por templates.

Componentes principales:

- Backend: FastAPI.
- Servidor: Uvicorn.
- Base de datos: PostgreSQL, con SQLite para testing.
- ORM: SQLAlchemy async.
- Migraciones: Alembic.
- Autenticacion: FastAPI Users con JWT.
- Frontend: Jinja2 templates, CSS y JavaScript estatico.
- IA: Google GenAI / Gemini.
- CV parsing: PyMuPDF y extractores de texto.
- Storage: AWS S3 via boto3, con abstraccion de storage.
- Vector search: pgvector y Sentence Transformers.
- Testing: Pytest, pytest-asyncio y httpx.

## 12. Arquitectura general

El codigo esta organizado por capas:

- `app/routes`: endpoints de API.
- `app/services`: logica de negocio.
- `app/models`: modelos SQLAlchemy.
- `app/schemas`: schemas Pydantic para validacion y respuesta.
- `app/templates`: vistas HTML.
- `app/static`: CSS, JavaScript e imagenes.
- `app/views`: rutas que renderizan paginas.
- `alembic`: migraciones de base de datos.
- `tests`: pruebas automatizadas.

Esta estructura facilita explicar que el producto no es solo una maqueta. Tiene backend, base de datos, autenticacion, modelos, servicios, migraciones, tests y paneles reales.

## 13. Paginas y experiencias visibles

La aplicacion incluye vistas como:

- Home.
- About.
- Login.
- Register.
- Dashboard de estudiante.
- Dashboard de empresa.
- Company candidates.
- Company team.
- Questionnaire.
- User profile.
- Resources.
- Resource detail.
- Roadmaps list.
- Roadmap detail.
- Community.
- Community feed.
- Jobs.
- Admin login.
- Admin panel.

Esto cubre tanto la experiencia publica de marketing como la experiencia privada del producto.

## 14. Mensaje de venta recomendado

Una forma simple de venderlo:

> StudentsCompass ayuda a instituciones, estudiantes y empresas a cerrar la brecha entre educacion y empleo. Para estudiantes, es una plataforma de career readiness con IA, CV feedback, roadmaps, recursos y comunidad. Para empresas, es una fuente de talento mas preparado, con herramientas para publicar vacantes y revisar candidatos con mas contexto. No competimos como otro job board; competimos como el sistema que prepara mejores candidatos antes de que lleguen al proceso de hiring.

Version corta:

> StudentsCompass convierte estudiantes en candidatos listos para contratar.

Version para empresas:

> Publicar una vacante no es dificil; encontrar candidatos preparados si. StudentsCompass reduce ese ruido preparando estudiantes antes de que apliquen y entregando a las empresas perfiles mas claros, motivados y alineados.

Version para universidades o programas educativos:

> StudentsCompass es una capa de empleabilidad que ayuda a los estudiantes a transformar formacion academica en preparacion laboral concreta: CV, LinkedIn, entrevistas, roadmaps, recursos, comunidad y postulaciones.

## 15. Posibles compradores o aliados

### Empresas

Empresas que quieren contratar talento joven, interns, juniors o perfiles early-career con menos friccion.

### Universidades y colleges

Instituciones que quieren mejorar empleabilidad, career services y resultados de sus estudiantes.

### Bootcamps y programas de formacion

Programas que necesitan demostrar que sus estudiantes no solo aprenden, sino que salen listos para presentarse profesionalmente.

### Organizaciones comunitarias

ONGs, newcomer programs y organizaciones que ayudan a jovenes o inmigrantes a entrar al mercado laboral canadiense.

### Estudiantes individuales

Usuarios B2C que buscan una guia clara para prepararse y aplicar mejor.

## 16. Modelos de monetizacion posibles

### B2B para empresas

Cobrar a empresas por publicar vacantes, acceder a candidatos preparados, usar dashboard de pipeline o aumentar visibilidad de marca empleadora.

### B2B2C para instituciones educativas

Cobrar a universidades, colleges o bootcamps una licencia por cohorte o por estudiante.

### Freemium para estudiantes

Dar acceso gratuito a funciones basicas y cobrar por features premium:

- Auditorias de CV adicionales.
- IA avanzada.
- Roadmaps premium.
- Preparacion de entrevista.
- Reportes descargables.
- Certificados de readiness.

### Employer branding

Empresas pagan por aparecer en espacios relevantes para talento joven, publicar recursos o crear challenges.

### Talent pipeline partnerships

Empresas pagan por acceso a cohorts o grupos de candidatos preparados para roles especificos.

## 17. Fortalezas actuales del producto

- Tiene una vision clara: career readiness, no solo job board.
- Cubre ambos lados del mercado: estudiantes y empresas.
- Ya cuenta con arquitectura backend completa.
- Tiene dashboards, recursos, roadmaps, comunidad, mensajes y postulaciones.
- Integra IA en partes donde agrega valor real: CV, keywords y auditorias.
- Tiene control de cuotas de IA, importante para costos y monetizacion.
- Tiene modelos de empresa y reclutadores, lo que permite vender a organizaciones reales.
- Tiene tests automatizados y migraciones, senal de madurez tecnica.

## 18. Riesgos o puntos a explicar con cuidado

Para venderlo bien, conviene evitar presentarlo como "otro LinkedIn" o "otro Indeed". El valor no esta en competir por volumen de ofertas, sino en preparar talento y mejorar la calidad del match.

Tambien conviene distinguir entre:

- Lo que ya existe en el sistema.
- Lo que es vision de negocio.
- Lo que puede desarrollarse como siguiente etapa.

La narrativa correcta es:

> Ya existe una base funcional fuerte. El potencial comercial esta en empaquetarla para instituciones y empresas que necesitan talento joven mejor preparado.

## 19. Roadmap comercial sugerido

### Fase 1: Piloto con estudiantes

Validar que estudiantes completen CV, cuestionario, recursos y roadmaps. Medir progreso, uso de IA y conversion a aplicaciones.

### Fase 2: Piloto con empresas

Invitar empresas a publicar roles entry-level o internships. Medir aplicaciones, calidad percibida y tiempo de screening.

### Fase 3: Alianzas institucionales

Presentar el producto a colleges, universidades, bootcamps y organizaciones de newcomers como herramienta de career readiness.

### Fase 4: Matching mas avanzado

Usar embeddings, perfiles, CVs, skills, recursos completados y aplicaciones para mejorar recomendaciones y ranking de oportunidades.

### Fase 5: Certificacion de readiness

Crear una senal verificable para empresas: estudiantes que completaron ciertos recursos, pasaron auditoria de CV y completaron roadmaps/proyectos.

## 20. Elevator pitch final

StudentsCompass es una plataforma de career readiness que ayuda a estudiantes a entender su direccion profesional, mejorar su CV, construir habilidades, prepararse para entrevistas y aplicar con estrategia. Para empresas, ofrece acceso a candidatos mas preparados y una herramienta para gestionar vacantes, postulaciones y reclutadores. La oportunidad comercial esta en venderlo como el puente entre educacion y empleo: una solucion que reduce confusion para estudiantes y reduce ruido para empresas.

En pocas palabras:

> StudentsCompass prepara talento joven para que las empresas contraten con mas confianza.

