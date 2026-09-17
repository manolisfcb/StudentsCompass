# Cutover del dominio al frontend y retiro progresivo del legacy

Origen: TASK-058 y TASK-059 del [tablero de refactor](TASKS.md). Este documento es
el **entregable de la Fase 0 (auditoría)**: describe el sistema tal como está,
asigna un dueño a cada URL, y fija el plan de cutover, de vuelta atrás y de
observación.

**No se ha modificado ni un fichero de código ni un recurso de infraestructura
para escribirlo.** Todo lo que sigue es lectura: el repositorio, `gcloud` en modo
consulta, `curl` contra los servicios ya públicos y Cloud Logging.

Fecha de la auditoría: **2026-09-17**.

La regla que ordena todo lo demás: **medir después del cutover, borrar solo con
evidencia.**

---

## 0. Qué se midió y cómo

| Fuente | Qué dio |
| --- | --- |
| `gcloud beta run domain-mappings list` | El dominio apunta hoy a la API |
| `gcloud run services list` / `describe` | URLs, revisiones e imágenes desplegadas |
| `curl` contra los dos `run.app` | Comportamiento real de cada ruta, hoy |
| `gcloud logging read` (5.000 peticiones, 2026-09-11 → 2026-09-17) | Tráfico por ruta y por user-agent |
| `gcloud alpha monitoring policies list` | Las seis alertas de TASK-057 están vivas |
| `gcloud logging buckets list` | Retención de logs: 30 días en `_Default` |

La muestra de tráfico está **acotada por el límite de 5.000 entradas**, no por la
ventana: es el tramo más reciente. Sirve para clasificar y para dar una línea
base, no como censo exacto.

---

## 1. Current Architecture

Lo que hay hoy, con el dominio todavía en la API:

```text
Internet
   │
   ▼
DNS  studentscompass.ca → 216.239.3{2,4,6,8}.21   (Google; NS en DigitalOcean)
   │                      sin registro para www.studentscompass.ca
   ▼
Cloud Run domain mapping   studentscompass.ca → studentscompass-api     ← EL CUTOVER ES ESTA LÍNEA
   │
   ▼
studentscompass-api  (FastAPI + Jinja + StaticFiles, allUsers invoker)
   ├── vistas Jinja: /, /login, /dashboard, /about, …     ← lo que ve un usuario HOY
   ├── /static/*  (StaticFiles)
   ├── /api/v1/*  (contrato REST)
   ├── /auth/jwt/* (login legacy, aún montado)
   ├── /robots.txt, /sitemap.xml, /favicon.ico
   ├── /health, /ready        (/healthz lo intercepta Cloud Run, ver §4.8)
   └── /internal/tasks/*      (Cloud Tasks, credencial propia)

studentscompass-front  (nginx + bundle React)   ← desplegado, sano, SIN TRÁFICO DE USUARIOS
   URL: https://studentscompass-front-ujl6fec6sa-uc.a.run.app
   ├── location ~ ^/(api/|health(z)?$|ready(z)?$|sitemap\.xml$|robots\.txt$)
   │        → proxy_pass a API_ORIGIN (la URL pública de la API)
   ├── /assets/   → bundle, immutable
   └── location / → try_files … /index.html      (fallback SPA)
```

Lo que esta topología ya hace bien, y conviene no romper al tocarla:

- **Mismo origen.** El navegador solo ve rutas relativas; nginx inyecta
  `API_ORIGIN` por variable de entorno y nunca llega al bundle. Por eso las
  cookies son first-party y CORS no participa en el diseño.
- **La cookie de sesión sobrevive al cutover.** `studentscompass_auth`
  (`backend/app/services/accounts/userService.py:47-52`) se emite **sin
  `cookie_domain`**, así que es host-only sobre `studentscompass.ca`. Como el
  dominio no cambia —solo cambia qué servicio hay detrás— las sesiones abiertas
  siguen siendo válidas después del repunte. Esto es lo que hace el cutover
  reversible sin cerrar la sesión de nadie.
- **El rollback no toca DNS.** Los dos servicios viven detrás del mismo mapeo de
  dominio; volver atrás es recrear el mapeo contra el otro servicio, sin
  propagación de DNS ni reemisión de certificado.

### Deriva entre lo desplegado y el repositorio

| | SHA | Fecha |
| --- | --- | --- |
| `studentscompass-api` en producción | `cef546b` | 2026-09-12 |
| `studentscompass-front` en producción (rev. 00003) | `cef546b` | 2026-09-12 |
| `HEAD` de `main` | `d698808` | 2026-09-17 |

**Producción va 3 commits por detrás**, y los tres tocan el frontend: el guard
`RequireAdmin` (`9353dc5`), el port de las hojas de estilo legacy (`8897a05`) y
la limpieza de estilos de perfil (`d698808`). Repuntar el dominio hoy expondría
el bundle del 12/09, no el que está en el repositorio. Ver bloqueante **B5**.

---

## 2. Route Ownership Matrix

`Tráfico` es de la muestra de §0 (200 salvo que se indique). `Seguro de borrar`
responde a los nueve criterios del final de este documento, hoy.

### 2.1 Pantallas que conservan su URL

Estas no necesitan redirect: el SPA responde en el mismo path.

| Ruta | Owner hoy | Owner tras cutover | Legacy | Tráfico | Manejo especial | ¿Borrar ya? |
| --- | --- | --- | --- | --- | --- | --- |
| `/` | API (Jinja) | frontend SPA | sí | **248** (incl. Googlebot) | En el sitemap; indexada | NO |
| `/about` | API (Jinja) | frontend SPA | sí | **21** | En el sitemap | NO |
| `/login` | API (Jinja) | frontend SPA | sí | **26** | En el sitemap | NO |
| `/register` | API (Jinja) | frontend SPA | sí | **8** | En el sitemap | NO |
| `/dashboard` | API (Jinja) | frontend SPA | sí | **3** (+303 a login) | — | NO |
| `/admin/login` | API (Jinja) | frontend SPA | sí | **2** | — | NO |
| `/questionnaire` | API (Jinja) | frontend SPA | sí | 0 en la muestra | — | NO |
| `/career-lab` | API (Jinja) | frontend SPA | sí | 0 en la muestra | — | NO |
| `/jobs` | API (Jinja) | frontend SPA | sí | 0 en la muestra | — | NO |
| `/resources`, `/resources/{id}` | API (Jinja) | frontend SPA | sí | 0 en la muestra | — | NO |
| `/roadmaps`, `/roadmaps/{slug}` | API (Jinja) | frontend SPA | sí | 0 en la muestra | — | NO |
| `/community`, `/community/{id}` | API (Jinja) | frontend SPA | sí | 0 en la muestra | — | NO |
| `/admin` | API (Jinja) | frontend SPA | sí | 0 en la muestra | — | NO |

### 2.2 Pantallas que CAMBIAN de URL — sin redirect hoy

Este es el grupo que rompe el cutover si no se resuelve antes. Hoy ninguna de
estas URLs existe en el router de React, así que tras el repunte caen todas en el
catch-all del SPA. Ver bloqueantes **B1** y **B2**.

| Ruta legacy | Ruta nueva | Tráfico | Qué pasa hoy tras el cutover | Decisión pendiente |
| --- | --- | --- | --- | --- |
| `/user-profile` | `/profile` | 0 en la muestra | 200 HTML → JS → `/__smoke` | **301** |
| `/company-dashboard` | `/company` | 0 en la muestra | ídem | **301** |
| `/company-candidates` | `/company/applicants` | 0 en la muestra | ídem | **301** |
| `/company-team` | `/company/recruiters` | 0 en la muestra | ídem | **301** |
| `/home` | `/` | 0 en la muestra | ídem | **301** (duplica `/`; canónico es `/`) |
| `/roadmap` | `/roadmaps` | 0 en la muestra | ídem | **301** (ya era un redirect en Jinja) |
| `GET /api/v1/auth/register` | `/register` | 3 (ruta compartida con el POST) | **sirve la página Jinja de registro, 11.513 bytes de HTML** — verificado a través del proxy | Ver **B10** |

Cero tráfico en la muestra **no autoriza a saltarse el redirect**: la muestra son
seis días y estas URLs llevan indexadas desde antes. `/user-profile` y las tres
de company son pantallas autenticadas —su tráfico llega en marcadores, no en
crawls— y el coste de un 301 es una línea de nginx.

### 2.3 Rutas de API y operación

| Ruta | Owner hoy | Owner tras cutover | Legacy | Tráfico | Manejo especial |
| --- | --- | --- | --- | --- | --- |
| `/api/v1/*` | API | **API** (vía proxy) | no | 68 en la muestra (64 reales) | Único prefijo del contrato |
| `/api/v1/posts`, `/upload_post`, `/delete_post/{id}` | API | API (vía proxy) | **sí** | **0** | Sin consumidor; sí medible tras el cutover |
| `/api/v1/students_dashboard` | API | API (vía proxy) | sí | 3 | Fusionada en `/api/v1/dashboard/student` (5) |
| `/auth/jwt/login`, `/auth/jwt/logout` | API | **nadie** (405 del SPA) | sí | **2** login | Ver **B4** |
| `/health`, `/ready` | API | API (vía proxy) | no | 620 / 24 | Sondas de plataforma |
| `/healthz` | **Cloud Run** (404) | Cloud Run (404) | — | — | Ver §4.8 |
| `/readyz` | API | API (vía proxy) | no | — | — |
| `/internal/tasks/*` | API | API **directo** por `run.app` | no | — | Cloud Tasks usa `INTERNAL_TASKS_BASE_URL`; no pasa por el dominio. Correcto. |
| `/docs`, `/redoc`, `/openapi.json` | deshabilitadas en producción | igual | — | — | `IS_PRODUCTION` las apaga |

### 2.4 Estáticos y SEO

| Ruta | Owner hoy | Owner tras cutover (sin tocar nada) | Tráfico | Problema |
| --- | --- | --- | --- | --- |
| `/static/*` | API (StaticFiles) | **nadie** — 200 HTML del SPA | **179** | **B3**: los assets se rompen en silencio |
| `/images/*` | no existe | frontend (bundle) | — | Es el destino de los de `/static/images/` |
| `/favicon.ico` | API (`FileResponse`) | frontend (bundle) | 34 | Verificado: 200 `image/x-icon` |
| `/robots.txt` | API | API **vía proxy de nginx** | **191** | Dueño sin decidir; ver §6 |
| `/sitemap.xml` | API (generado) | API **vía proxy de nginx** | **114** | Acoplado a los mtime de las plantillas; ver §6 |

### 2.5 Ruido

| Clase | Tráfico | Owner hoy | Tras el cutover |
| --- | --- | --- | --- |
| Escáneres (`/wp-admin/install.php`, `/.env`, `/wp-json/*`, `/index.php`…) | **1.936 respuestas 404** de 5.000 (39%) | API → 404 | **200 HTML del SPA** |

No es un bloqueante de corrección, pero sí de medición: pasar de 404 a 200 borra
la señal más barata que hay para separar tráfico real de basura, e invita a las
instancias del frontend a escalar por escáneres. Se resuelve con lo mismo que
**B1**.

---

## 3. Resumen de dueños tras el cutover

Un dueño por URL, sin solapes:

```text
frontend (bundle)     /  /about  /login  /register  /dashboard  /profile
                      /questionnaire  /resources/*  /roadmaps/*  /jobs/*
                      /career-lab  /community/*  /messages/*  /company/*
                      /admin  /admin/login  /assets/*  /images/*  /favicon.ico

frontend (nginx)      los 301 de §2.2, el 404 real del §4.1,
                      y robots.txt + sitemap.xml si se elige la Opción A (§6)

API (vía proxy)       /api/v1/*   /health   /ready   /readyz

API (directo run.app) /internal/tasks/*   ← Cloud Tasks, nunca un navegador
```

---

## 4. Bloqueantes descubiertos en la auditoría

Ninguno de estos estaba anotado en TASK-058. Los cuatro primeros son condiciones
previas de la propia lista de verificación de la Fase 1 («redirects correctos»,
«deep links funcionan», «SPA fallback funciona»), así que resolverlos **no altera
el orden exigido**: forma parte del pre-flight del cutover.

### B1 — El catch-all del SPA lleva a una pantalla de diagnóstico · BLOQUEANTE

`frontend/src/app/router.tsx:117`:

```tsx
{ path: "*", element: <Navigate to="/__smoke" replace /> },
```

`/__smoke` es la pantalla que TASK-046 creó para comprobar el proxy desde un
navegador: lista sondas contra `/api/v1/users/me`, `/healthz` y `/readyz` y
enseña sus status. Es una herramienta de desarrollo.

Tras el cutover, **toda** URL desconocida —las seis de §2.2, las 1.936 peticiones
de escáner, cualquier enlace roto, cualquier URL indexada que ya no exista—
responde `200` y aterriza ahí. Un 200 le dice a Google que la página existe y es
esa.

Verificado en el servicio desplegado: `/user-profile`, `/company-dashboard`,
`/home`, `/roadmap` y `/wp-admin` devuelven los cuatro `200 text/html` de 2.569
bytes, el mismo `index.html`.

**Qué hace falta:** una pantalla 404 de verdad en el catch-all, y que `/__smoke`
deje de ser el destino por defecto de nada.

### B2 — Siete URLs legacy cambian de path y no hay ningún redirect · BLOQUEANTE

Las de §2.2. El sitio de destino natural es **nginx**, no el router de React: un
301 servido por el proxy es un único dueño, no gasta un arranque del SPA y es
legible por un crawler sin ejecutar JavaScript. `frontend/nginx.conf` ya tiene la
forma para hacerlo (una `location =` por ruta, antes del `location /`).

### B3 — `/static/*` desaparece en silencio · BLOQUEANTE

179 respuestas 200 en la muestra, entre ellas `Logo_Ready_to_Use.png`,
`base.js`, `csrf.js` y `safeDom.js`.

Tras el cutover nginx no proxea `/static/`, así que el fallback del SPA devuelve
`200 text/html` para una petición de PNG o de JS. Verificado:
`/static/images/Logo_Ready_to_Use.png` → `200 text/html`, 2.569 bytes.

El logo está hotlinkeado desde fuera (es el `og:image` histórico). Un 200 con
HTML donde se espera una imagen es peor que un 404: ninguna caché ni ningún
cliente lo detecta como error.

**Decisión pendiente:** 301 de `/static/images/*` a `/images/*` (el bundle ya los
sirve: verificado `200 image/png`), y 410 para `/static/js/*` y `/static/css/*`,
que no tienen equivalente y no deben tenerlo.

### B4 — `/auth/jwt/*` deja de ser alcanzable, y de ser medible · IMPORTANTE

Hoy tiene tráfico real de personas autenticándose (2 en esta muestra; 10 en la
ventana más larga que registra TASK-058). No está en el regex del proxy, así que
tras el cutover un `POST /auth/jwt/login` recibe `405 text/html` de nginx.
Verificado.

Las consecuencias no son simétricas:

- **Las sesiones ya abiertas no se pierden**: la cookie es host-only sobre el
  dominio y el SPA la envía igual. Nadie se desloguea por el cutover.
- **Un cliente que aún llame a `/auth/jwt/login` se rompe.** Tras el cutover no
  quedan páginas Jinja servidas que lo llamen, así que debería ser nadie — pero
  eso es una predicción, no una medición.
- **Deja de poder medirse**: la petición ya no llega a FastAPI. Ver **B6**.

### B5 — Producción no sirve el frontend que hay en el repositorio · BLOQUEANTE

Detallado en §1. El cutover debe repuntar hacia un frontend **desplegado desde el
SHA que se quiere cortar y verificado en su `run.app`**, no hacia la revisión del
12/09.

### B6 — Tras el cutover, «cero tráfico» deja de significar lo mismo · CRÍTICO PARA LA FASE 3

Este es el hallazgo que más condiciona el resto del plan.

Después del repunte, nginx solo reenvía cinco familias de rutas. Todo lo demás
—las 23 vistas Jinja, `/static/*`, `/auth/jwt/*`— **deja de llegar a la API por
construcción**. Su contador se pone a cero el día del cutover porque el proxy no
las pasa, no porque nadie las pida.

Medir «cero peticiones a `/dashboard` en la API» después del cutover y concluir
que la pantalla Jinja está muerta es un razonamiento circular. La evidencia
válida es distinta según la ruta:

| Clase de ruta | ¿Sigue siendo medible en la API? | Qué cuenta como evidencia |
| --- | --- | --- |
| Vistas Jinja (22 de 23) | **No, por el dominio** | Peticiones **directas al `run.app` de la API**: si llegan a `/dashboard`, no vienen del proxy |
| `GET /api/v1/auth/register` (la 23ª) | **Sí** — cuelga de `/api/v1`, el proxy la pasa. Ver **B10** | Log de la API, tal cual |
| `/static/*`, `/auth/jwt/*` | **No, por el dominio** | Igual |
| `/api/v1/*` legacy (posts, `students_dashboard`, `enriched`) | **Sí** | Log de la API, tal cual |
| `/robots.txt`, `/sitemap.xml` | Depende de §6 | Log del dueño elegido |
| URLs legacy retiradas | — | Log del **frontend**: 404 y 301 servidos |

El servicio de API tiene `allUsers` como invoker —lo necesita, porque nginx lo
llama por su URL pública sin credencial—, así que su `run.app` seguirá siendo un
bypass abierto del dominio. Eso no es un fallo: es lo que hace la regla de arriba
posible de aplicar.

### B7 — El smoke público del deploy no reintenta, y `/ready` puede dar 503 en frío · MENOR

En la primera petición tras un periodo de inactividad, `/ready` devolvió `503`
(`min-instances=0`, arranque en frío con la base remota). Las seis siguientes,
`200` en ~0,4 s.

El smoke previo a la promoción reintenta 10 veces (`deploy.yml`, «Smoke de la
revisión sin tráfico»). El **smoke público no reintenta**: un solo `curl` por
path. Un deploy puede salir rojo por un arranque en frío sin que nada esté mal.
Conviene igualar los dos antes de la ventana de observación, para que un fallo de
deploy durante la ventana signifique algo.

### B8 — `/healthz` nunca llega a la aplicación · INFORMATIVO

`GET /healthz` devuelve el 404 del propio Google (`Error 404 (Not Found)!!1`),
tanto directo contra la API como a través del proxy: Cloud Run reserva ese path.
`deploy.yml` ya lo tenía anotado y por eso usa `/health` y `/ready`.

Efecto lateral: la sonda de `SmokePage` espera 404 en `/healthz` y lo obtiene —
por el motivo equivocado. No es un fallo de producción; sí es una sonda que no
prueba lo que dice probar.

### B9 — `www.studentscompass.ca` no existe · INFORMATIVO

Sin registro DNS. `deploy.yml` deliberadamente lo deja fuera de `CORS_ORIGINS` y
explica por qué. La lista por defecto de `app/app.py:190` sí lo incluye, pero esa
lista solo se usa cuando `CORS_ORIGINS` no está definida, que no es el caso en
producción. Si algún día se crea el CNAME, hay que mapearlo también en Cloud Run
o dará error de certificado.

### B10 — Una pantalla Jinja sobrevive al cutover, montada bajo `/api/v1` · BLOQUEANTE

`GET /api/v1/auth/register` (`backend/app/views/views.py:72`) no es un endpoint:
devuelve la **página Jinja de registro**. Comparte path con el
`POST /api/v1/auth/register` de fastapi-users, que sí es la API. El mismo path
sirve una pantalla o un endpoint según el método — la matriz de TASK-034 ya lo
tenía anotado como defecto del contrato.

Lo que la auditoría añade es su consecuencia para el cutover, que no estaba en
ningún sitio: **como cuelga de `/api/v1`, nginx la proxea.** Verificado a través
del frontend ya desplegado: `200 text/html`, 11.513 bytes, la página de registro
legacy entera.

Es decir: de las 23 vistas Jinja, 22 dejan de ser alcanzables por el dominio
tras el cutover y **esta no**. Un usuario que llegue a esa URL después del
repunte recibe la pantalla vieja —con su CSS legacy, su JS legacy y su POST
contra el flujo antiguo— servida desde dentro del frontend nuevo. También
contradice cualquier regla de proxy o de CSP que trate `/api/v1/*` como JSON.

Contrapartida útil: al seguir pasando por el proxy, **sí es medible** durante la
ventana, al contrario que las otras 22 (ver **B6**).

**Decisión pendiente antes del cutover:** un `location = /api/v1/auth/register`
en nginx que responda 301 a `/register` **solo para GET**, dejando el POST
intacto hacia la API. Retirar la vista en el backend resuelve la colisión de
raíz, pero eso es TASK-059 y va después de la ventana.

---

## 5. Cutover Plan

### Pre-flight (resuelve B1–B5; sigue siendo Fase 1)

1. Arreglar el catch-all del SPA: pantalla 404 real, `/__smoke` fuera del
   camino por defecto. **(B1)**
2. Añadir a `frontend/nginx.conf` los 301 de §2.2 (incluido el de
   `GET /api/v1/auth/register`, solo para GET), y el tratamiento de
   `/static/*` de §2.3. **(B2, B3, B10)**
3. Decidir qué pasa con `/auth/jwt/*`: dejarlo morir con el dominio, o proxearlo
   durante la ventana para poder medirlo. **(B4)**
4. Igualar el smoke público al pre-promoción (reintentos). **(B7)**
5. Merge a `main`, CI verde, `deploy.yml` despliega API y frontend con el mismo
   SHA. **(B5)**

### Verificación contra el `run.app` del frontend, antes de tocar el dominio

Todo esto se comprueba sobre
`https://studentscompass-front-ujl6fec6sa-uc.a.run.app`, que ya existe y no tiene
usuarios. Lo marcado ✅ está verificado hoy sobre la revisión del 12/09 y habrá
que repetirlo sobre la nueva.

- ✅ Servicio sano: `/` responde 200 con el `index.html` del bundle.
- ✅ El proxy llega a la API: `/api/v1/auth/session` → `401 application/json`
  (llegó a FastAPI, no lo tragó el SPA).
- ✅ `/ready` → 200 `{"status":"ready","checks":{"database":"ok"}}`.
- ✅ `/favicon.ico` → 200 `image/x-icon`.
- ✅ `/robots.txt` y `/sitemap.xml` → 200 con el contenido correcto y
  `https://studentscompass.ca` dentro.
- ✅ Fallback SPA y deep links: `/dashboard`, `/profile`, `/login` sirven el
  documento de entrada (refresco directo sobre la ruta funciona).
- ⬜ Los siete 301 de §2.2 responden 301 al destino correcto.
- ⬜ Una URL inexistente responde **404**, no 200.
- ⬜ `/static/images/Logo_Ready_to_Use.png` responde 301 a `/images/…`.
- ⬜ `GET /api/v1/auth/register` responde 301 a `/register`, y el `POST` al
   mismo path sigue llegando a la API.
- ⬜ Recorrido autenticado completo como estudiante y como recruiter, comparado
   contra `verify_parity.py` / [parity/REPORT.md](parity/REPORT.md).
- ⬜ HTTPS y certificado: los gestiona Cloud Run y **no cambian** en el repunte,
   porque el mapeo del dominio ya existe y solo cambia su `routeName`.

### El cutover

Un solo cambio. Cloud Run no permite reasignar un mapeo en sitio, así que son dos
comandos y **hay una ventana de indisponibilidad entre ellos**: elegir una franja
de bajo tráfico (la muestra concentra el tráfico real en horario diurno
norteamericano).

```bash
P=gen-lang-client-0908704200; R=us-central1; D=studentscompass.ca

# 0. Dejar constancia del estado del que se parte
gcloud beta run domain-mappings list --project $P --region $R \
  --format='value(metadata.name, spec.routeName)' --filter="metadata.name=$D"
#    esperado: studentscompass.ca  studentscompass-api

# 1. Borrar el mapeo actual (a partir de aquí el dominio no resuelve a nada)
gcloud beta run domain-mappings delete $D --project $P --region $R

# 2. Recrearlo contra el frontend — esto es el cutover
#    infra/gcp/60-domain-mapping.sh hace exactamente esto y verifica el destino
cd infra/gcp && ./60-domain-mapping.sh
```

El DNS **no se toca**: los cuatro registros A apuntan a Google y sirven para
cualquier servicio de Cloud Run de la región. El certificado gestionado tampoco
se reaprovisiona desde cero.

### Inmediatamente después

- `curl` sobre `/`, `/login`, `/dashboard`, `/api/v1/auth/session`,
  `/robots.txt`, `/sitemap.xml`, una URL inexistente y dos de los 301.
- Un login real de extremo a extremo y una sesión previa al cutover que siga
  viva (comprueba lo que dice §1 sobre la cookie host-only).
- Arranca la ventana de observación (§7). **No se borra nada.** El legacy se
  queda entero en pie: es el mecanismo de vuelta atrás.

---

## 6. Rollback Plan

| | |
| --- | --- |
| Target actual | `studentscompass-api` |
| Target nuevo | `studentscompass-front` |
| Configuración DNS previa | **No cambia.** 4 registros A a `216.239.3{2,4,6,8}.21`, NS en DigitalOcean |
| Certificado | Gestionado por Cloud Run; sobrevive al repunte |
| Sesiones de usuario | Sobreviven en ambos sentidos (cookie host-only sobre el dominio) |

**Procedimiento, sin tocar código:**

```bash
P=gen-lang-client-0908704200; R=us-central1; D=studentscompass.ca
gcloud beta run domain-mappings delete $D --project $P --region $R
gcloud beta run domain-mappings create --service studentscompass-api \
  --domain $D --project $P --region $R
```

**Disparadores de rollback** (cualquiera, durante la ventana):

- Tasa de 5xx del frontend o de la API por encima del 1% sostenido cinco minutos
  (ya hay alerta).
- Login roto: caída de logins con éxito respecto a la línea base de §7.
- Una pantalla sin paridad que impida completar un flujo (no un defecto
  cosmético).
- p95 por encima de 2.000 ms diez minutos (ya hay alerta).

**Condiciones para que el rollback siga siendo posible** —y que TASK-058 exige
mantener durante toda la ventana:

1. No borrar ninguna vista, plantilla, JS ni CSS legacy. El monolito Jinja debe
   poder volver a servir el dominio tal cual.
2. No retirar `/auth/jwt/*` del backend.
3. Congelar los cambios incompatibles de schema: la API sirve a las dos mitades.

---

## 7. Decisión de robots.txt y sitemap.xml

**Estado hoy, y es el que hay que corregir:** nginx **no los sirve, los reenvía**
(`frontend/nginx.conf:67`). La matriz de TASK-034 los marca `retire` con destino
«frontend Nginx», pero ese destino no está implementado. Es decir: incluso
después del cutover, retirarlos de FastAPI los rompe. Y el smoke público del
deploy comprueba `robots.txt == 200`, así que el fallo aparecería como un deploy
roto — lo cual es suerte, no diseño.

Hay además un acoplamiento ya documentado: `_build_sitemap_xml`
(`backend/app/app.py:101-130`) deriva el `lastmod` del **mtime de
`app/templates/{home,about,login,register}.html`**. Cuando TASK-059 borre esas
plantillas, `_get_last_modified_date` devolverá `None` para las cuatro y el
`lastmod` desaparecerá del sitemap **sin error y sin test que lo note**.

**Recomendación: Opción A — que nginx los sirva desde el bundle.**

El argumento es que no hay nada dinámico que perder. El sitemap tiene exactamente
cuatro entradas —`/`, `/about`, `/login`, `/register`— y las cuatro son páginas
públicas de marketing con URL fija. Todo lo demás del producto está detrás de
autenticación y no debe indexarse. Un sitemap generado en tiempo de ejecución
para cuatro URLs constantes es una fuente de verdad partida a cambio de nada, y
encima es la que arrastra la dependencia de las plantillas.

Concretamente: `frontend/public/robots.txt` y `frontend/public/sitemap.xml`,
`sitemap.xml` y `robots.txt` fuera del regex del proxy en `nginx.conf`, y en
TASK-059 fuera de `app/app.py`. Con eso el dueño es uno solo y el acoplamiento
desaparece antes de que pueda morder.

Verificación después del cambio: 200, `text/plain` y `application/xml`
respectivamente, contenido correcto, `https://studentscompass.ca` como base y la
línea `Sitemap:` apuntando al dominio público.

**Si en cambio se elige la Opción B** (dejarlos en la API), hay que hacerlo
explícito: siguen en el regex del proxy, **salen de la matriz de retiro** de
TASK-059, y el acoplamiento del `lastmod` con las plantillas pasa a ser un
bloqueante propio de TASK-059 en lugar de un problema resuelto.

Lo que no es aceptable es el estado actual: marcados como «los sirve el
frontend» mientras de hecho los sirve el backend.

---

## 8. Observation Strategy

### Instrumento

- **Cloud Logging**, bucket `_Default`, **30 días de retención** (verificado).
  Una ventana de 14 días cabe con margen para analizarla.
- **Dos servicios, dos logs.** Tras el cutover el log de peticiones de
  `studentscompass-front` es el registro de **qué piden los usuarios**; el de
  `studentscompass-api`, el de **qué sirve el contrato**. Antes del cutover solo
  existía el segundo. Los informes deben citar cuál de los dos.
- **Log estructurado de la aplicación** (TASK-028/045): una línea por petición en
  `app.request` con `endpoint` (la **plantilla** de ruta, no el path),
  `status`, `duration_ms`, `request_id` y `actor` (HMAC del id de usuario, con el
  tipo en claro). Permite «5xx de este actor en la última hora» sin grep y sin
  meter PII en el log.
- **Las seis alertas de TASK-057 están vivas y habilitadas** (verificado):
  5xx > 1%, p95 > 2.000 ms, 429, fallos de proveedor externo, jobs de CV
  fallidos tras gastar, techo de gasto de IA.
- **No hay analytics de producto.** No hay GA ni equivalente en el bundle, así
  que «usuarios únicos» no es medible directamente; el sustituto es `actor` en
  el log estructurado, que distingue personas autenticadas sin identificarlas.

### Ventana

**14 días naturales** desde el cutover. Dos ciclos semanales completos: el
tráfico estudiantil tiene forma semanal y una ventana de siete días no distingue
«nadie lo usa» de «esa semana no tocaba».

Todos los datos que autoricen un borrado deben pertenecer **íntegramente** a esta
ventana. Los números de §0 y §2 son línea base **pre**-cutover: sirven para
comparar, nunca para autorizar.

### Línea base pre-cutover (2026-09-11 → 2026-09-17, 5.000 peticiones)

| Clase | Peticiones |
| --- | --- |
| Ruido de escáneres (404) | 1.936 (39%) |
| `/health` (sondas) | 620 |
| Páginas Jinja servidas con 200 | **308** |
| `/robots.txt` + `/sitemap.xml` | 294 |
| Assets `/static/` con 200 | **179** |
| Contrato `/api/v1` | 68 (64 descontando escaneos) |
| `/auth/jwt/login` | **2** |
| API de posts legacy | **0** |

Distribución de status: 404 (1.936), 200 (1.490), 403 (1.084), 302 (403),
401 (32), 405 (19).

User-agents sobre las páginas Jinja con 200: mayoría navegadores reales
(Windows/Chrome, iPhone, macOS, Android), más **Googlebot**, **AhrefsBot**,
`SecurityResearch/1.0` y `curl`. La separación bot/humano es indispensable:
Googlebot sobre `/` es el motivo de que el SEO importe aquí.

### Qué se registra por ruta legacy

Lo pide la Fase 3 y el log ya lo da todo salvo lo indicado:

`request count` · `status` · `duración` · `user-agent` · `referer` (en el log de
peticiones de Cloud Run) · `actor` autenticado (log de aplicación) · `redirects`
· `errores`. **`unique users` no está disponible** sin analytics; se sustituye
por conteo de `actor` distintos.

Separación obligatoria en todo informe: `usuarios reales` / `bots y crawlers` /
`sondas de health` / `monitorización` / `escáneres`.

### Consultas de partida

```bash
P=gen-lang-client-0908704200
W='timestamp>="<INICIO_VENTANA>"'

# Lo que piden los usuarios, ya en el frontend
gcloud logging read "resource.labels.service_name=\"studentscompass-front\" AND $W" \
  --project $P --format='value(httpRequest.status, httpRequest.requestUrl, httpRequest.userAgent)'

# B6: acceso DIRECTO al run.app de la API a rutas que el proxy no reenvía.
# Cualquier acierto aquí es un cliente esquivando el dominio — la única
# evidencia válida de que una vista Jinja sigue teniendo consumidor.
gcloud logging read "resource.labels.service_name=\"studentscompass-api\" AND $W" \
  --project $P --format='value(httpRequest.requestUrl)' \
  | grep -vE '/(api/|health|ready|readyz|robots\.txt|sitemap\.xml|internal/)'

# Endpoints legacy que SÍ siguen siendo medibles (van por el proxy)
gcloud logging read "resource.labels.service_name=\"studentscompass-api\" AND $W AND
  (httpRequest.requestUrl:\"/api/v1/posts\" OR httpRequest.requestUrl:\"/api/v1/upload_post\"
   OR httpRequest.requestUrl:\"/api/v1/delete_post\" OR httpRequest.requestUrl:\"/api/v1/students_dashboard\")" \
  --project $P --format='value(httpRequest.requestMethod, httpRequest.status, httpRequest.requestUrl)'

# Los 301 de §2.2: quién sigue llegando por la URL vieja
gcloud logging read "resource.labels.service_name=\"studentscompass-front\" AND $W AND httpRequest.status=301" \
  --project $P --format='value(httpRequest.requestUrl, httpRequest.userAgent, httpRequest.referer)'
```

### Criterios de cierre de la ventana

La ventana cierra **sana** si, durante los 14 días:

- [ ] 5xx por debajo del 1% en ambos servicios; ninguna alerta de 5xx disparada.
- [ ] p95 por debajo de 2.000 ms; ninguna alerta de latencia disparada.
- [ ] Logins con éxito (`POST /api/v1/auth/student/login` y `/company/login`) en
      el nivel de la línea base o por encima. Una caída es el síntoma más
      probable de una regresión de sesión.
- [ ] Cero 404 del frontend con user-agent de navegador real y `referer` interno
      (un 404 así es una ruta que el SPA debía conocer).
- [ ] Ninguna alerta de jobs de CV fallidos tras gastar, ni de techo de IA.
- [ ] El rollback siguió siendo posible cada día: legacy intacto, sin migración
      incompatible.
- [ ] Ningún rollback ejecutado.

Si cualquiera falla, la ventana **no cierra** y el retiro de TASK-059 sigue
bloqueado.

---

## 9. Clasificación y retiro (Fases 4 a 6) — reglas, no ejecución

Estas fases no se pueden planificar con datos de hoy, por definición. Lo que sí
se fija ahora es cómo se leerán los datos de mañana.

### Clasificación

`ACTIVE` · `ZERO_TRAFFIC` · `BOT_ONLY` · `REDIRECT_ONLY` · `INTERNAL_ONLY` ·
`UNKNOWN`. Solo `ZERO_TRAFFIC` y, tras evaluar SEO, `BOT_ONLY` autorizan el
borrado. `UNKNOWN` **nunca**.

Con la corrección de **B6**: para una vista Jinja, `ZERO_TRAFFIC` significa
**cero peticiones directas al `run.app` de la API**, no cero peticiones a través
del dominio (eso es cierto por construcción y no prueba nada).

Predicción a falsar con la ventana, no a asumir: los cinco handlers de la API de
posts legacy ya midieron 0 en la muestra pre-cutover, y siguen siendo medibles
después. Son el candidato más limpio. Las vistas Jinja de §2.1 tenían tráfico
real y su evidencia post-cutover es de otra naturaleza.

### 404 / 410 / 301

Decidir por ruta, nunca por defecto:

- **301** cuando hay sustituta: las siete de §2.2 y `/static/images/*`.
- **410** cuando la página desapareció sin equivalente: `/static/js/*`,
  `/static/css/*`.
- **404** para lo que nunca existió (escáneres) — que es justo lo que hoy no pasa
  por culpa de **B1**.

### Retiro, pantalla por pantalla

Por cada una: identificar (ruta, vista, plantilla, CSS, JS, assets, tests,
imports) → confirmar clasificación con datos de la ventana → buscar referencias
en frontend, backend, plantillas, routing, navegación, tests, emails,
documentación, cron y redirects → borrar solo lo de esa pantalla → `build`,
`tests`, `lint`, `typecheck` → deploy pequeño e independiente → observar 404,
5xx y errores.

Un commit por pantalla (`remove legacy /route-a`), nunca uno masivo. Cada
borrado cita la vertical que lo sustituye y archiva su evidencia de tráfico.

El inventario para cuando toque, ya levantado por TASK-059: `backend/app/views/`
(1 módulo, 23 rutas), `backend/app/templates/` (23 ficheros),
`backend/app/static/` (css, images, js), los imports de `Jinja2Templates` y
`StaticFiles` (`backend/app/app.py:13-14`), el montaje de `/static`
(`backend/app/app.py:265`) y las 33 filas `retire` de
[route_targets.csv](route_targets.csv).

### Fuera de alcance de todo este trabajo

Lógica de negocio, APIs de dominio, base de datos, autenticación, autorización y
funcionalidades no relacionadas. Esto es routing, cutover, observabilidad y
limpieza de frontend legacy. En particular: **no se toca `allUsers` en la API**
—el proxy lo necesita— aunque sea el bypass que §B6 aprovecha para medir; cerrar
esa puerta es un cambio de topología con su propia ficha.

---

## 10. Criterios para borrar una pantalla

Los nueve, todos, por pantalla:

```text
[ ] domain cutover completado
[ ] ventana de observación de 14 días cerrada sana
[ ] tráfico de la ruta analizado CON LA REGLA DE B6
[ ] sin dependencia de usuarios reales
[ ] sin dependencia interna (monitorización, jobs, scripts)
[ ] sin dependencia externa (enlaces, integraciones, marcadores)
[ ] impacto SEO evaluado (indexación, canonical, sitemap, redirects)
[ ] ruta sustituta identificada si aplica
[ ] rollback posible
```

Si alguno es falso: **DO NOT DELETE**.

---

## 11. Estado

Fase 0 (auditoría): **completa**. Este documento es su entregable.

Fase 1 (cutover): **no iniciada**. Bloqueada por B1, B2, B3, B5 y B10, que
son condiciones previas de su propia lista de verificación.

Fases 2 a 6: no iniciadas, y no planificables en detalle hasta que existan datos
posteriores al cutover.

Nada de infraestructura ni de código se ha modificado para producir este informe.
