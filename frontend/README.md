# frontend

SPA React + TypeScript (Vite) del plan
[08_REST_REACT_CLOUD_RUN_PLAN.md](../docs/refactor/08_REST_REACT_CLOUD_RUN_PLAN.md).
Nginx la sirve y proxea `/api`, `/healthz` y `/readyz` al backend, de modo que el
navegador ve **un solo origen** en local igual que en Cloud Run.

Estilos e i18n están decididos en
[ADR-002](../docs/refactor/ADR-002-frontend-styling-and-i18n.md); no se
re-deciden por pantalla.

## Arranque

### Topología completa (la que se parece a producción)

Desde la raíz del repositorio:

```bash
docker compose up --build
open http://localhost:8080/__smoke
```

Levanta `db`, `redis`, `migrate` (Alembic, corre y sale), `api`, `worker` y
`web`. Todo el tráfico del navegador entra por `http://localhost:8080`.

`docker-compose.yml` publica además la API en `127.0.0.1:8000`. Es para `curl` y
para el modo de abajo: apuntar un navegador ahí reintroduce el segundo origen
que este montaje existe para evitar.

### Iteración rápida sobre la UI

```bash
cd frontend && npm install && npm run dev
```

Vite sirve en `http://localhost:5173` y proxea los mismos tres prefijos a
`DEV_API_ORIGIN` (por defecto `http://127.0.0.1:8000`, que es donde el compose
publica la API). El navegador sigue viendo un solo origen.

Las dos rutas dan el mismo resultado; comprobado en TASK-038:

| Petición | Vía Nginx (8080) | Vía Vite (5173) |
| --- | --- | --- |
| `GET /__smoke` | 200 HTML | 200 HTML |
| `GET /api/v1/users/me` | 401 JSON | 401 JSON |
| `GET /healthz` | 404 JSON | 404 JSON |
| `GET /readyz` | 404 JSON | 404 JSON |

Los 404 son correctos hoy: TASK-045 publica esos endpoints. Que respondan **JSON
del backend** y no el HTML de la SPA es justamente lo que prueba que el prefijo
se proxea y no lo absorbe el fallback de historial.

## Comandos

```bash
npm run lint        # eslint
npm run typecheck   # tsc -b --noEmit (strict + noUncheckedIndexedAccess)
npm test            # vitest
npm run i18n:check  # catálogo completo, sin claves vacías ni huérfanas
npm run build       # bundle de producción en dist/
```

TASK-039 los conecta a la lane de CI.

## Reglas que el scaffold hace cumplir

- **Una sola capa HTTP.** Ningún componente llama `fetch`; lo hace
  `src/api/client.ts`. Hay una regla de ESLint que lo impide, no solo una
  convención.
- **Rutas relativas siempre.** `apiRequest` rechaza una URL absoluta: daría al
  navegador un segundo origen y las cookies dejarían de ser first-party.
- **Sin secretos en el bundle.** `API_ORIGIN` se inyecta en Nginx al arrancar el
  contenedor (`envsubst`, filtrado a esa única variable), nunca en build.
- **Sin cadenas literales visibles.** Todas pasan por `t()`.
- **El proxy resuelve el nombre de la API en cada petición**, no una vez al
  arrancar. Nginx cachea la IP de un `proxy_pass` literal de por vida, así que
  recrear el contenedor de la API dejaba 502 permanentes; `nginx.conf` usa un
  `resolver` y una variable. En otra plataforma hay que ajustar
  `API_DNS_RESOLVER` al nameserver del contenedor (Cloud Run:
  `169.254.169.254`); lo fija TASK-056.

## Estructura

```text
src/
├── app/          # providers, router, guards (los guards llegan con TASK-044)
├── api/          # client.ts, queryKeys.ts, generated/ (tipos de TASK-043)
├── components/   # primitives/, patterns/, layout/
├── features/     # una carpeta por vertical del plan §8
├── i18n/
├── lib/
└── styles/       # index.css: los tokens, en un único sitio
```

`features/smoke` es la única pantalla de este scaffold. Las reales llegan por
vertical, TASK-046 en adelante.
