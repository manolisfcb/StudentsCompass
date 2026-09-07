# ADR-001 — Patrón de ingreso a Cloud Run

- Fecha: 2026-09-07
- Estado: **Aceptada**
- Origen: TASK-036 del [tablero de refactor](TASKS.md)
- Decide: §3 de [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md), que dejaba la opción abierta
- Implementan: TASK-055 (aprovisionamiento) y TASK-056 (despliegue). **No la re-deciden.**

## Contexto

El plan 08 despliega dos servicios de Cloud Run: `studentscompass-front` (Nginx
sirviendo el bundle React) y `studentscompass-api` (FastAPI JSON). El dominio
apunta solo al frontend, que proxea `/api`, `/healthz` y `/readyz` a la API. Un
solo origen visible para el navegador es lo que hace que cookies, CSRF y
navegación no dependan de CORS cross-site.

Lo que el plan dejó sin decidir es si la API, además, queda cerrada a nivel IAM.
§3 advierte que un proxy Nginx simple no puede llamar a un servicio Cloud Run que
exija autenticación IAM: haría falta un HTTPS Load Balancer con serverless NEGs y
routing `/api/*`, o un proxy capaz de emitir identity tokens. §14 lista «API
directa elude Nginx» como riesgo vivo.

La decisión cambia coste, topología y qué barreras de seguridad son reales.
Tomarla implícitamente al escribir el primer Terraform la volvería difícil de
revisar, y por eso es un gate.

## Opciones consideradas

### A. Proxy Nginx, API invocable sin autenticación IAM

El frontend proxea `/api` al URL de Cloud Run de la API. Ese URL sigue siendo
públicamente invocable; la autorización la hace la aplicación.

### B. HTTPS Load Balancer con serverless NEGs

Un balanceador con NEGs sin servidor y routing por path enruta `/api/*` a la API
y el resto al frontend. La API puede exigir IAM y quedar inalcanzable salvo a
través del balanceador.

## Comparación

| Criterio | A — Nginx, sin IAM | B — LB con serverless NEGs |
| --- | --- | --- |
| Coste mensual base | ~$0. No añade recursos facturables sobre los dos servicios | ~$18–25 de forwarding rule y backend services, más tráfico, con independencia del uso |
| Piezas que operar | Las dos que el plan ya exige | Añade balanceador, NEGs, backend services, health checks y certificado gestionado |
| Superficie expuesta | Dos URLs alcanzables: el dominio y el `run.app` de la API | Una sola entrada; el `run.app` de la API deja de ser invocable |
| Si alguien llama la API directamente | Llega a FastAPI y encuentra las mismas barreras que por el proxy: sesión, CSRF y rate limits | Recibe 403 de IAM antes de tocar la aplicación |
| Tiempo hasta el primer despliegue | Corto; es el patrón de FinanceTracker que el plan toma como referencia | Más largo; el routing por path y los certificados son un proyecto propio |
| Reversibilidad | Migrar a B después no cambia el código de la aplicación, solo la topología | Volver a A es igual de mecánico |

## Decisión

**Se adopta la opción A**: la API queda invocable sin autenticación IAM, detrás
del proxy Nginx del servicio frontend.

Las razones, en orden:

1. **IAM no sustituye a ninguno de los controles que de verdad protegen los
   recursos privados.** Todo recurso privado exige sesión, CSRF y rate limits en
   FastAPI en las dos opciones. B no permite relajar ninguno; solo añade una
   puerta antes. Pagar por esa puerta tiene sentido cuando la aplicación es la
   parte débil, y aquí la aplicación es la única parte que decide.
2. **El coste de B es fijo y el beneficio es marginal en este punto del
   proyecto.** ~$20/mes constantes por cerrar un vector cuyo impacto, si los
   controles de aplicación funcionan, es un atacante llegando exactamente a las
   mismas 401 y 403 que obtendría por el dominio.
3. **B es reversible y no toca el código.** Si aparece una razón concreta
   —cumplimiento, un incidente, tráfico que justifique WAF o Cloud Armor— se
   migra a B sin cambiar la aplicación. Decidir A ahora no cierra esa puerta.

## Qué se acepta explícitamente al decidir A

El riesgo «API directa elude Nginx» de §14 **queda vivo y aceptado**, no
mitigado. Concretamente:

- El URL `run.app` de la API es descubrible y llamable por cualquiera.
- Cualquier cabecera que el proxy añada por higiene —y no por seguridad— puede
  faltar en una llamada directa. Ninguna decisión de autorización puede depender
  de que el proxy haya pasado por delante.
- Todo endpoint que la API exponga es, a efectos prácticos, público en cuanto a
  alcanzabilidad. Los endpoints internos que el inventario clasifica como
  `internal` —`POST /api/v1/internal/capstone/seed` y los barridos de skills,
  ver [09_ROUTE_MATRIX.md](09_ROUTE_MATRIX.md)— necesitan su propia
  autenticación, no la suposición de que nadie los encontrará.
- Lo mismo para el endpoint que Cloud Tasks invocará en TASK-054: OIDC
  obligatorio y verificado en la aplicación, porque su URL será alcanzable desde
  internet.
- `/docs`, `/redoc` y `/openapi.json` quedan alcanzables por el `run.app`.
  Decidir si se exponen en producción es parte de TASK-056; esta ADR solo deja
  constancia de que no hay una capa que lo impida por topología.

## Controles que siguen siendo responsabilidad de la aplicación

En **ambas** opciones, y por tanto también tras adoptar A. Ninguno es opcional:

| Control | Dónde vive | Tarea |
| --- | --- | --- |
| Autenticación por actor y sesión con cookies seguras | FastAPI | TASK-042 |
| CSRF double-submit en todo método mutante, con validación de `Origin` | FastAPI | TASK-042 |
| Rate limits por IP y por actor | `app/middleware/rate_limit.py` | TASK-007, TASK-010 |
| Autorización por ownership en cada recurso | Servicios de dominio | TASK-003, TASK-008 |
| Límite máximo de servidor en toda colección | Helpers de paginación | TASK-041 |
| Autenticación OIDC del endpoint interno de Cloud Tasks | FastAPI | TASK-054 |
| Límites de cuerpo y multipart | `app/middleware/body_size.py` | TASK-006 |

## Consecuencia concreta: `TRUSTED_PROXY_IPS`

Es la parte de esta decisión que más fácil sería pasar por alto. Todos los
límites por IP de la aplicación se resuelven por `resolve_client_ip()`, que
depende de `TRUSTED_PROXY_IPS`; hoy vale `private` por defecto y el `Dockerfile`
lo fija así (ver [ingress_and_client_ip.md](../ingress_and_client_ip.md)).

Con un solo servicio hay un salto entre el cliente y la aplicación. Con la
topología de A hay dos: navegador → frontend Nginx → API. La cadena
`X-Forwarded-For` que ve la API es más larga, y el peer inmediato ya no es el
mismo. Además, una llamada directa al `run.app` de la API llega por un camino
distinto que una que pasa por el frontend.

Si `TRUSTED_PROXY_IPS` queda demasiado amplio en la API, un cliente directo puede
inventarse su `X-Forwarded-For` y estrenar un bucket de rate limit por petición;
es decir, **el control que esta ADR pone como principal guardián se anula**. Si
queda demasiado estrecho, todos los clientes se contarán como una sola IP —la del
frontend— y el límite por IP se convertirá en un límite global.

Por eso TASK-056 no puede desplegar sin haber comprobado empíricamente, contra el
despliegue real y no por deducción, qué peer y qué cadena ve la API en los dos
caminos, y haber fijado `TRUSTED_PROXY_IPS` en consecuencia. Ese valor se
documenta junto al despliegue. Es la única parte de esta decisión que no se puede
cerrar sobre el papel.

## Revisión

Esta decisión se revisa si aparece cualquiera de estas condiciones, y entonces la
opción B pasa a ser la esperada:

- Un requisito de cumplimiento que exija que la API no sea alcanzable desde
  internet.
- Un incidente de abuso que los rate limits de aplicación no contengan.
- Necesidad de WAF, Cloud Armor o reglas de borde que solo existen en el
  balanceador.
- Un tercer servicio que deba hablar con la API sin pasar por el frontend.
