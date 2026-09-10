# Observabilidad: correlación, duración y contadores

Origen: TASK-028 del tablero de refactor, hallazgo F-24.

## El problema que resuelve

Antes de esta tarea, los logs no tenían correlación uniforme, ni duración, ni
cuenta de consultas o llamadas externas, y varios `catch` devolvían un éxito
vacío. La consecuencia práctica: **«el análisis de CV va lento» y «el análisis de
CV está roto» producían la misma evidencia — ninguna.**

## Qué hay

### El request id

Cada petición recibe un id, que:

- se acepta del cliente si viene en `X-Request-ID` **y** es seguro de repetir
  (`^[A-Za-z0-9._:-]{1,64}$`); si no, se genera uno nuevo;
- se estampa en **todos** los registros de log del proceso, vía
  `logging.setLogRecordFactory`, no vía un filtro por handler — un handler
  añadido después (el `caplog` de pytest, un handler JSON, el de una librería)
  produciría registros sin el atributo y `%(request_id)s` reventaría sobre ellos;
- se devuelve en la cabecera `X-Request-ID`, para que un usuario pueda citarlo
  en un reporte;
- vale `-` fuera de una petición (arranque, job en background, test), que se ve
  distinto de un valor truncado.

**Un id hostil se reemplaza, no se sanea.** `X-Request-ID: foo\nlevel=CRITICAL`
acaba en una línea de log, así que cualquier cosa que no sea un token corto y
plano se sustituye por uno nuevo. Sanearlo sería peor: el id resultante ya no
nombraría la petición que el llamante cree.

### La línea por petición

Una sola línea al final de cada petición, en `app.request`:

```
request method=GET endpoint=/api/v1/questionnaire/profile status=404 \
  duration_ms=6.59 sql_statements=0 external_calls=0 external_failures=0
```

- `endpoint` es la **plantilla** de la ruta (`/users/{id}`), no el path
  (`/users/9f3c…`). Un path lleva ids: agregaría mal y metería un id de usuario
  en cada línea.
- Sale a INFO, o a **WARNING** si el status es 5xx, para que un endpoint que
  falla se vea sin subir el nivel de log.
- Nada se registra por fila ni por statement: los contadores se suman en el
  contexto de la petición y se reportan una vez.
- `actor` (TASK-045) identifica **quién**, sin decir quién: es un HMAC del id
  con la clave de firma de la app, truncado, con el tipo en claro
  (`student:a5db2211854c1dca`, `recruiter:…`, o `-` si nadie se autenticó). Un
  hash sin clave no valdría: el espacio de ids de usuario es pequeño y
  enumerable, así que cualquiera con la tabla de usuarios —que es justo quien
  lee estos logs— podría revertirlo. Lo estampan las dependencias de
  autenticación, que son el único sitio por el que pasan todas las rutas.
- `job_id` aparece solo cuando la petición trata de un job concreto.

### El formato: texto en desarrollo, JSON en producción

`JSON_LOGS` (por defecto: activo si `ENV=production`) cambia el render a un
objeto JSON por línea, que es lo que Cloud Logging parsea en una entrada
estructurada: `severity` pasa a ser el nivel por el que se filtra y cada campo
extra pasa a ser un campo consultable.

```json
{"severity": "INFO", "message": "request method=GET …", "logger": "app.request",
 "request_id": "ec4823…", "method": "GET", "endpoint": "/api/v1/jobs",
 "status": 200, "actor": "student:a5db2211854c1dca", "duration_ms": 0.03}
```

La diferencia práctica es entre poder preguntar «enséñame los 5xx de este actor
en la última hora» y tener que hacer grep. En texto la misma información va en
el `message`, porque a ese tamaño el JSON no hay quien lo lea en un terminal.

### `/healthz` y `/readyz`

No son la misma pregunta, y confundirlas rompe cosas distintas:

| | Pregunta | Toca la base | Si falla |
| --- | --- | --- | --- |
| `/healthz` | ¿el proceso vive? | **no** | la plataforma reinicia el contenedor |
| `/readyz` | ¿debe entrar tráfico **ahora**? | sí, con timeout de 2 s | la revisión sale del balanceador |

Un `/healthz` que tocara la base convertiría una caída de base en un bucle de
reinicios: la plataforma mata un contenedor que funcionaba, el siguiente falla
igual, y una caída recuperable pasa a ser una en la que no queda nada vivo con
lo que recuperarse. Un `/readyz` que no la tocara dejaría entrar tráfico a una
réplica que va a fallar cada petición.

`/readyz` comprueba con la **misma sesión** que usa una petición, no abriendo su
propia conexión: una sonda con conexión propia puede informar de una base
perfectamente alcanzable mientras cada petición real falla por un pool agotado.
Devuelve 503 —no 500— y el motivo va al log, nunca al cuerpo: la sonda es
alcanzable desde internet y un error de driver nombra el host, el puerto y a
menudo el usuario.

Ninguna de las dos está en el OpenAPI: las llama la plataforma, no un cliente, y
el contrato es de lo que consume el frontend (TASK-043).

### Los contadores

| Campo | Qué mide | Dónde se incrementa |
| --- | --- | --- |
| `duration_ms` | la petición entera | el middleware |
| `sql_statements` | round trips a la base | evento `before_cursor_execute` del engine |
| `external_calls` / `external_failures` | intentos contra algo fuera del proceso | el bloque `external_call(...)` |
| `provider.<nombre>.calls` / `.failures` / `.ms` | lo mismo, por proveedor | ídem |

Proveedores instrumentados hoy: `gemini` (los dos evaluadores LLM), `linkedin`
(el scraper de búsqueda) y `cp_sat` (el solver de rutas).

**Se cuenta una sola vez, en la frontera.** El bloque `with external_call(...)`
es el único sitio donde se registra un intento externo; un llamante que además
incrementara un contador propio contaría doble. Un **reintento es otro intento**
y cuenta como tal: es otra petición pagada al proveedor.

El contador de SQL se instala una vez sobre el engine (`install_sql_counter`) y
es idempotente — instalarlo dos veces contaría cada statement dos veces.

## Lo que nunca se registra

La línea por petición se construye **solo** con ids generados aquí, una
plantilla de ruta, un nombre de proveedor y números. No hay texto libre en ella,
y hay un test que lo comprueba campo a campo.

Texto libre que llegue a un log por otras vías pasa por
`app.core.errors.redact`, que es de TASK-011: esta tarea lo reutiliza en vez de
crear una segunda redacción. Prohibido explícitamente y verificado en tests:
texto de CV, nombre de fichero, token y URL firmada.

## Fallos recuperables

Un fallo recuperable se registra; no se devuelve como éxito vacío. El caso que
F-24 señalaba —`seed_roadmaps_on_startup_if_dev` devolvía `0` tanto si no había
nada que sembrar como si la siembra reventaba— ahora registra la excepción y
sigue devolviendo `0`, porque un seed fallido no debe impedir arrancar. La
diferencia es justo lo que alguien buscaría en ese log.

Los otros `except` que devuelven vacío se auditaron y se dejaron como estaban,
con razón: una `Content-Length` malformada («longitud desconocida»), una IP
malformada («no confiable») y una `IntegrityError` de idempotencia («no se
aplicó») son respuestas deliberadas, no fallos tragados.

## Coste

Medido con el mismo endpoint con y sin el middleware, 400 peticiones tras
calentar:

| | p50 | p95 |
| --- | --- | --- |
| Sin middleware | 0.075 ms | 0.159 ms |
| Con middleware | 0.085 ms | 0.212 ms |
| **Delta** | **9.5 µs** | **52.9 µs** |

Las primitivas por separado: `record_sql_statement` 0.085 µs, un bloque
`external_call` 0.924 µs, un registro de log con el factory 0.105 µs.

**Por qué es ASGI puro y no `BaseHTTPMiddleware`:** la primera versión usaba
`BaseHTTPMiddleware` y medía **218 µs de delta a p50** — dos órdenes de magnitud
más que los contadores, porque envuelve cada petición en un task group de anyio
y pasa la respuesta por una cola. Reescrito como ASGI puro son 9.5 µs, 23 veces
menos. Es el mismo estilo que `RequestBodySizeLimitMiddleware`, y por el mismo
tipo de motivo.

## Qué **no** es

No es tracing. No hay spans, ni exporter, ni logging por fila: el Scope de
TASK-028 lo excluye explícitamente. **TASK-045** da forma a estos mismos campos
para que Cloud Run los consuma y **TASK-057** construye las alertas encima. Una
telemetría, no dos.
