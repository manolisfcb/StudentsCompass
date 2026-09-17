# Paridad de las ocho verticales — TASK-046 a TASK-053

Esta carpeta es la evidencia de las tres casillas que ninguna vertical de la
migración podía marcar por sí sola:

- paridad funcional y visual contra la baseline de [TASK-035](../baseline/README.md),
- permisos y errores por rol,
- cero tráfico del frontend al contrato legacy.

Sin ella, «se ve igual», «los permisos están bien» y «ya no llama a lo viejo»
eran tres opiniones. [`REPORT.md`](REPORT.md) es el veredicto.

## Cómo se regenera

```bash
cd frontend && npm run build            # el arnés sirve dist/, no levanta Vite
cd ../backend && ../.venv/bin/python scripts/verify_parity.py
```

Una sola vertical:

```bash
cd backend && ../.venv/bin/python scripts/verify_parity.py --only V5-TASK-050
```

Sin navegador, solo el barrido de permisos:

```bash
cd backend && ../.venv/bin/python scripts/verify_parity.py --skip-screens
```

El comando termina en 0 si no hay tráfico legacy ni violaciones de permisos, y
en 1 si hay alguno, así que sirve como gate.

## Qué produce

| Ruta | Versionado | Contenido |
| --- | --- | --- |
| `REPORT.md` | sí | El veredicto por vertical: pantallas, tráfico legacy, permisos, hallazgos |
| `report.json` | sí | Lo mismo en bruto, incluida la lista de peticiones de cada pantalla |
| `screens/*.png` | **no** | 48 capturas del SPA (24 pantallas × desktop/mobile) |
| `sidebyside/*.png` | **no** | 42 tiras `legacy | React` para revisión humana |

Los PNG no se versionan por la misma razón que los de la baseline: pesan ~39 MB
por pasada y se reconstruyen con un comando. Lo que se revisa en un PR es el
informe.

## Cómo está montado, y por qué así

**Una sola semilla.** El arnés importa `scripts/capture_baseline.py` en vez de
reimplementar el sembrado. No es ahorro de código: si los datos del SPA no
fueran exactamente los de la baseline, una pantalla distinta podría serlo por
los datos y la comparación no significaría nada.

**Un solo origen, sin Docker.** `SpaMirror` copia el regex de
[`frontend/nginx.conf`](../../../frontend/nginx.conf): lo que casa va a la API,
el resto es `dist/` con fallback a `index.html`. El navegador ve un origen, que
es la condición que hace comparables cookies, CSRF y navegación con lo que
correrá en Cloud Run. Levantar el compose daría lo mismo para lo que se mide y
costaría dos imágenes por iteración.

**El tráfico se mide en la misma visita que la captura.** Medirlo en una pasada
aparte significaría que ni la captura prueba lo que pidió la pantalla ni el
tráfico corresponde a lo que se ve en la captura.

**Qué cuenta como legacy no se escribe a mano.** Sale de las filas `retire` de
[`route_targets.csv`](../route_targets.csv), que es donde TASK-034 decidió el
destino de cada ruta. Si una ruta cambia de destino, la comprobación cambia con
ella.

## Los dos números que son un veredicto, y los que no

`layout_rms` y las proporciones de paleta **no son umbrales de aprobado**. La
migración cambió el DOM y el motor de layout; un diff de píxel a cero sería
sospechoso, no bueno. Sirven para ordenar la revisión humana de `sidebyside/`.

Sí son veredicto:

- **Peticiones al contrato legacy.** Cero o no cero.
- **Violaciones de permisos.** Un actor que no es del tipo exigido y no recibe
  401/403, o uno que sí lo es y recibe 401.
- **Marca preservada.** ADR-002 congela la paleta («los valores no se
  rediseñan»); que el teal siga en la pantalla es comprobable.

## Lo que no demuestra

Que **ningún otro consumidor** use el contrato legacy. Esto mide lo que pide el
SPA, que es lo que dice el criterio («cero tráfico *del frontend*»). Que nadie
más lo llame solo se sabe con el servicio desplegado y sus logs —TASK-056/057—
y es la condición de retiro de TASK-059.
