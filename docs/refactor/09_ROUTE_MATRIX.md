# Inventario de rutas y matriz legacy → REST

Origen: TASK-034 del [tablero de refactor](TASKS.md). Extiende §5.2 de
[08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md), que tabulaba
19 correspondencias sobre 150 handlers.

## Artefactos

| Archivo | Qué es | Cómo se produce |
| --- | --- | --- |
| [route_inventory.json](route_inventory.json) | Inventario completo: método, ruta, actor exigido, dependencias de auth, `response_model`, módulo, consumidor y destino | Generado por `backend/scripts/route_inventory.py` |
| [route_inventory.csv](route_inventory.csv) | Lo mismo, una fila por método × ruta | Generado |
| [route_targets.csv](route_targets.csv) | Tabla de decisión: destino, contrato objetivo, vertical y nota por handler | **Escrita a mano y revisada**; el script solo la cruza |

```bash
cd backend && ../.venv/bin/python scripts/route_inventory.py
```

Reejecutar no cambia los artefactos: se comprobó por hash. El script falla si un
handler no tiene decisión o si una decisión apunta a un handler inexistente, así
que «ningún handler queda sin clasificar» es un check y no una afirmación.

Lo que sale del código y lo que no está separado a propósito. Método, ruta, actor
y consumidor se leen de la app y de los archivos del frontend; el destino REST es
una decisión de diseño y vive en un CSV versionado. Mezclarlos haría imposible
distinguir un hecho de una intención al revisar el diff.

## Cómo se determina el actor

No por el nombre de la dependencia: las que crea `fastapi_users.current_user(...)`
son closures llamados todas `current_user_dependency`. El script recorre el árbol
`route.dependant` que FastAPI resuelve —incluidas las dependencias heredadas del
router y las anidadas— y compara **por identidad de objeto** contra las
dependencias declaradas en `userService`, `adminService` y `companyService`.
Cuando un handler exige varias identidades se registra la más restrictiva.

Las ocho rutas que genera fastapi-users (`/auth/jwt/logout`,
`/api/v1/auth/student/logout`, `/api/v1/auth/company/logout` y las cinco de
`/api/v1/users`) usan closures creados dentro del paquete, sin objeto alcanzable
con el que compararlas: se declaran una a una en
`GENERATED_ROUTER_ACTOR_OVERRIDES`, con el actor leído de
`fastapi_users/router/users.py`. Cualquier otra dependencia `current_*` o
`require_*` no reconocida rompe el script en vez de contarse como pública.

## Recuento y reconciliación con §2 del plan

| Origen | Handlers |
| --- | --- |
| `app/routes/` | 127 |
| `app/views/views.py` | 23 |
| **Subtotal propio** | **150** |
| Generados por fastapi-users (auth, register, verify, reset, users) | 20 |
| Generados por FastAPI (`/docs`, `/docs/oauth2-redirect`, `/redoc`, `/openapi.json`) | 4 |
| Declarados en `app/app.py` (`/favicon.ico`, `/robots.txt`, `/sitemap.xml`) | 3 |
| Propios añadidos por TASK-042 (`GET /auth/session`, `POST /auth/session/refresh`) | 2 |
| **Total registrado en la app** | **179** |

El plan §2 cuenta «150 handlers, 23 de ellos vistas». Coincide exacto con el
subtotal propio en el momento del inventario: el plan contó lo declarado en
`app/routes` y `app/views`. Los restantes existen en la app en ejecución y
también hay que decidirlos, porque un endpoint generado por una librería se sirve
igual que uno propio.

Las cuatro altas de TASK-042 son las dos rutas de sesión y el segundo montaje del
router de login/logout de estudiante bajo `/api/v1/auth/student`. El montaje
antiguo en `/auth/jwt` sigue registrado a la vez y por eso el total sube en
cuatro, no en dos.

## Actor exigido

| Actor | Handlers |
| --- | --- |
| student | 90 |
| student:optional | 14 |
| admin | 25 |
| recruiter | 8 |
| recruiter:job_manager | 6 |
| recruiter:owner | 4 |
| recruiter:optional | 3 |
| public | 25 |

`:optional` significa que el handler resuelve al actor si hay sesión pero no la
exige. Las 14 de estudiante son las vistas Jinja, que renderizan distinto según
haya sesión; ninguna protege datos por sí misma.

## Destino

| Destino | Handlers | Qué significa |
| --- | --- | --- |
| `rest` | 138 | Queda en el contrato REST público que consume React |
| `retire` | 31 | Se retira en el cutover (TASK-059) |
| `platform` | 4 | Lo genera FastAPI; no es contrato de dominio |
| `internal` | 2 | Endpoint interno autenticado; ninguna pantalla lo llama |

De los 138 que sobreviven como REST, **108 cambian de contrato** (ruta, método o
ambos) y 30 se quedan como están. §5.2 tabulaba 19 de esos 108.

Los 31 a retirar son las 23 vistas Jinja, los 5 handlers de la API de posts
legacy, `/home`, y los tres estáticos (`/favicon.ico`, `/robots.txt`,
`/sitemap.xml`) que pasan al servicio frontend.

Los 2 `internal` son `POST /api/v1/capstone/analytics/seed` y
`POST /api/v1/capstone/job-postings/skills/sync-open`: operaciones de datos y
barridos masivos que hoy están en el contrato público exigiendo solo sesión de
estudiante.

## Handlers por vertical

Este reparto es lo que hace verificable «la vertical terminó»: una vertical cierra
cuando todos sus handlers `rest` tienen consumidor React y todos sus `retire`
tienen cero tráfico.

| Vertical | Handlers |
| --- | --- |
| V1 — Shell público y auth (TASK-046) | 18 |
| V2 — Perfil, cuestionario y CV (TASK-047) | 13 |
| V3 — Dashboard, recursos y roadmaps (TASK-048) | 21 |
| V4 — Jobs, análisis de CV y candidaturas (TASK-049) | 12 |
| V5 — Company (TASK-050) | 27 |
| V6 — Community, friendships y messages (TASK-051) | 36 |
| V7 — Career Lab / Capstone (TASK-052) | 17 |
| V8 — Admin (TASK-053) | 27 |
| Sin vertical (`platform`) | 4 |

V6 y V8 son las mayores. V6 además arrastra las dos duplicaciones `enriched` y
los cinco handlers de posts legacy.

## Consumidores

| Coincidencia | Handlers | Qué significa |
| --- | --- | --- |
| `exact` | 71 | La ruta completa aparece literal en una plantilla o un JS |
| `prefix` | 86 | El cliente construye la URL; coincide un prefijo, que se registra en el artefacto |
| `none` | 18 | Ningún consumidor en `app/templates` ni `app/static` |

`prefix` es honesto sobre su límite: `admin.js` construye las 22 rutas de admin
desde `const API = '/api/v1/admin'`, así que ninguna aparece entera. El artefacto
guarda el fragmento que coincidió (`consumer_match_fragment`) para que cada
atribución se pueda comprobar a mano sin releer el script.

De los 18 sin consumidor, 4 son de FastAPI (`/docs`, `/redoc`, etc.) y 2 son
estáticos. Los 12 restantes son hallazgos, y están abajo.

## Hallazgos

Ninguno estaba en el plan. Los tres primeros son defectos del contrato actual,
no consecuencias de migrar.

### 1. Una vista Jinja montada bajo `/api/v1`

`GET /api/v1/auth/register` (`app/views/views.py:72`) devuelve HTML y comparte
ruta con `POST /api/v1/auth/register`, que es la API de registro de
fastapi-users. El mismo path sirve una pantalla y un endpoint según el método.
Retirar la vista en TASK-046 elimina la colisión; hasta entonces, cualquier
regla de proxy o de CSP que trate `/api/v1/*` como JSON está equivocada para esa
ruta.

### 2. Dos contratos para el perfil de la sesión

`GET/PATCH /api/v1/profile` (propio) y `GET/PATCH /api/v1/users/me` (generado por
fastapi-users) exponen ambos el perfil del actor. §5.2 manda `/profile` a
`/users/me`, que es exactamente donde ya está el otro. TASK-047 tiene que dejar
un solo contrato, no dos que devuelvan cosas parecidas.

Lo mismo, en admin: `GET/PATCH/DELETE /api/v1/users/{id}` exige superuser —el
mismo `is_superuser` que `current_admin_user`— y duplica
`GET/PATCH/DELETE /api/v1/admin/users/{user_id}`.

### 3. Colecciones duplicadas por su forma de respuesta

`GET /api/v1/communities/{id}/posts` y `.../posts/enriched` son la misma
colección con distinta expansión; igual con
`/api/v1/community-posts/{id}/comments` y `.../comments/enriched`. Dos endpoints
para un recurso es la fuente de verdad partida que la Definition of Done
prohíbe. La matriz los funde en una colección con expansión declarada.

### 4. Cinco handlers de posts sin ningún consumidor

`GET/POST /api/v1/posts`, `GET /api/v1/posts/{post_id}`,
`POST /api/v1/upload_post` y `DELETE /api/v1/delete_post/{post_id}` no aparecen
en ninguna plantilla ni en ningún JS. Son la API de posts anterior a las
comunidades; el feed actual usa `/api/v1/communities/{id}/posts`. Siguen
sirviéndose y siguen escribiendo. TASK-059 debe verificar cero tráfico antes de
retirarlos, no darlos por muertos porque el frontend no los llame.

### 5. `GET /api/v1/dashboard/stats` no lo llama el frontend

`dashboard.js:14` pide `/api/v1/students_dashboard`. `dashboard/stats` solo lo
ejercitan los tests, entre ellos el contrato que TASK-016 convirtió en «cero
escrituras en lectura». Son dos presenters del mismo dashboard; la matriz los
funde en `GET /api/v1/dashboard/student`.

### 6. El sitemap depende de las plantillas que TASK-059 borra

`_build_sitemap_xml` (`app/app.py:101`) calcula `lastmod` desde el mtime de
`app/templates/home.html`, `about.html`, `login.html` y `register.html`. Cuando
TASK-059 retire Jinja, `_get_last_modified_date` devolverá `None` para los cuatro
y el `lastmod` desaparecerá del sitemap **sin error y sin test que lo note**. El
sitemap tiene que moverse al frontend antes de borrar las plantillas, no después.

### 7. Una ruta de API fuera de `/api/v1`

`POST /auth/jwt/login` y `POST /auth/jwt/logout` colgaban de `/auth/jwt`, fuera
del prefijo versionado. El proxy Nginx del plan §1 enruta `/api`, `/healthz` y
`/readyz`; con ese par tal cual, el login no entraba por ninguna de las tres.

**Resuelto en TASK-042**, con una forma distinta a la que esta matriz proponía.
El destino escrito aquí era `POST`/`DELETE /api/v1/auth/session`; lo implantado
es `POST /api/v1/auth/student/login` y `/logout`, espejo exacto de
`/api/v1/auth/company/login`, que ya existía. La razón es que un único recurso
`/api/v1/auth/session` no puede expresar *como qué actor* se inicia sesión: son
dos identidades con cookies separadas, y el plan §6.2 pide explícitamente
conservarlas separadas durante la migración. Reducirlas a un solo recurso exigiría
un discriminador en el cuerpo, que es la misma distinción movida a un sitio peor.
`GET /api/v1/auth/session` sí existe, y es de lectura: dice qué actor eres, no te
convierte en uno.

`/auth/jwt/*` sigue montado y sin documentar en OpenAPI hasta TASK-059, porque las
páginas Jinja todavía lo llaman y retirarlo cerraría la sesión de todo el mundo a
mitad de migración. El proxy ya no necesita contemplarlo para que el login
funcione, pero sí mientras esas páginas se sirvan.

## Límites

La atribución de consumidores cubre `app/templates` y `app/static`. No prueba que
un endpoint no tenga clientes externos: `none` significa «ningún consumidor en
este repositorio», y por eso los retiros exigen comprobar tráfico real en
TASK-059, no solo este artefacto.

Los contratos objetivo son propuestas de esta tarea salvo las 19 que §5.2 ya
fijaba, marcadas como tales en la columna `note`. Cada vertical puede corregir el
suyo al implementarlo; lo que no puede es dejarlo sin decidir.

La matriz no cubre endpoints que aún no existen. §5.1 pide los de health y
readiness (TASK-045): son altas, no correspondencias, y por eso no tienen fila.
`GET /api/v1/auth/session` era una de esas altas y ya existe, así que ahora tiene
fila como cualquier otro handler.
