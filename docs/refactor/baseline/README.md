# Baseline de paridad — TASK-035

Esta carpeta es la evidencia contra la que se mide la paridad de cada vertical de
la migración a REST + React. El plan
[08_REST_REACT_CLOUD_RUN_PLAN.md](../08_REST_REACT_CLOUD_RUN_PLAN.md) §9 exige
paridad funcional y visual por vertical y §13 pide comparación visual de cada
pantalla migrada. Sin baseline archivada, «se ve igual» es una opinión.

## Cómo se regenera

```
.venv/bin/python scripts/capture_baseline.py              # todo
.venv/bin/python scripts/capture_baseline.py --skip-screens  # sin navegador
```

Las capturas necesitan Chromium:

```
.venv/bin/python -m playwright install chromium
```

El comando reescribe la carpeta entera. Nada de aquí se edita a mano.

## Qué produce

| Ruta | Versionado | Contenido |
| --- | --- | --- |
| `openapi.json` | sí | Schema OpenAPI actual, 144 paths. |
| `fixtures/<actor>/*.json` | sí | Payload real de cada endpoint GET relevante, por actor. |
| `manifest.json` | sí | Qué se capturó, con sha256 de lo versionado. |
| `MANIFEST.md` | sí | Lo mismo, legible, con la pantalla y el endpoint atados a su vertical. |
| `screens/*.png` | **no** | 44 capturas (22 pantallas × desktop/mobile). |
| `screens/index.json` | **no** | sha256 y tamaño de cada PNG; viaja con ellos. |

## Decisión: los PNG no se versionan

Una captura completa pesa ~18 MB en 44 ficheros. La baseline se reejecuta en cada
punto de control de la migración —una vez por vertical, ocho verticales— así que
versionarlos sumaría del orden de 150 MB de binarios al historial, irreversibles,
para comparar imágenes que además dependen del renderizador de la máquina.

Se versiona el manifiesto y se publican los PNG como **artefacto de CI**
(`.github/workflows/tests.yml`, job `baseline`). Quien necesite comparar descarga
el artefacto de la ejecución de referencia y el de la actual. `screens/` está en
`.gitignore`.

Los sha256 de los PNG viven en `screens/index.json`, no en `manifest.json`: son
dependientes de la máquina que renderiza y no deben ensuciar el diff de un
fichero versionado en cada captura.

## Cómo se produce, y qué implica

- Base **SQLite desechable** sembrada por el propio script con datos sintéticos:
  dominios `example.com` (RFC 2606), URLs `.invalid`, nombres genéricos. Ningún
  dato real, ninguna PII.
- Mismo aislamiento que la suite (`tests/isolation.py`): no se lee `.env`, cada
  credencial tiene un valor falso y las conexiones fuera de loopback están
  bloqueadas. El proceso **no puede** alcanzar producción.
- Reloj y namespace de UUID fijos, así que ids y fechas son función del código y
  no del momento de ejecución. Dos ejecuciones seguidas producen `openapi.json`,
  las fixtures, `manifest.json` y `MANIFEST.md` byte a byte idénticos.
- El navegador solo puede hablar con el servidor local: toda petición externa se
  aborta y queda registrada por pantalla en `manifest.json`. La comparación es
  válida porque las dos partes —legacy y React— se capturan con el mismo
  bloqueo.
- El script termina revisando las fixtures contra patrones de JWT, cabeceras
  `Set-Cookie`, hashes de contraseña, claves de proveedor y correos fuera de la
  semilla. Si encuentra algo, falla y no escribe el manifiesto.

## Límites conocidos

- **`/questionnaire` no tiene baseline visual fiable.** Toda su presentación
  viene de `https://cdn.tailwindcss.com` en tiempo de ejecución; bloqueado, la
  página se captura sin estilos. Que una pantalla dependa del play-CDN de
  Tailwind es en sí un hallazgo para su vertical (TASK-047).
- **`/admin` y `/admin/login` pierden la tipografía Inter**, que `admin.css`
  importa de Google Fonts. Estructura y color sí son comparables.
- **SQLite no es PostgreSQL.** `GET /api/v1/profile/cv/{resume_id}/similar` usa
  el operador pgvector `<=>` y no se puede capturar aquí; queda registrado con
  su razón.
- **El object storage está fuera de alcance.** Las dos rutas que descargan el CV
  de un candidato quedan sin fixture por la misma razón.
- Las fixtures cubren métodos **GET**. Las mutaciones necesitan un cuerpo por
  endpoint y su contrato lo fija TASK-043 en CI, no una captura.
- `none` en consumidores del inventario y la ausencia de una fixture no prueban
  ausencia de clientes externos.

## Hallazgo abierto

`GET /api/v1/admin/companies` responde **500** siempre que exista al menos una
empresa: [`app/routes/adminRoute.py:532`](../../../app/routes/adminRoute.py)
lee `c.email` y `Company` no tiene esa columna
([`app/models/companyModel.py:17-24`](../../../app/models/companyModel.py)). La
fixture archiva el 500 porque es el comportamiento actual. Corregirlo es un Bug
Fix rotulado de la vertical de admin (TASK-053); esta tarea captura, no arregla.
