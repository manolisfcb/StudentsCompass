# ADR-002 — Estrategia de estilos e i18n del frontend React

- Fecha: 2026-09-08
- Estado: **Aceptada**
- Origen: TASK-038 del [tablero de refactor](TASKS.md)
- Decide: §7 de [08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md), que dejaba ambas opciones abiertas
- Implementan: TASK-044 (componentes base y shells) y las ocho verticales, TASK-046 a TASK-053. **No las re-deciden.**

## Contexto

§7 del plan 08 enuncia dos alternativas sin elegir: «Tailwind v4 **o** tokens CSS
extraídos del diseño existente; elegir uno y evitar convivir indefinidamente con
23 hojas CSS por pantalla», y condiciona i18n a un supuesto: «i18next desde el
inicio **si** se mantendrán varios idiomas». Ninguna de las dos frases decide.

TASK-038 tiene la decisión en Scope y en Acceptance Criteria («La estrategia de
estilos e i18n está elegida y escrita, no pendiente») porque es lo que fija cómo
se escriben las ocho verticales. Decidirlo al empezar la tercera vertical
significaría reescribir las dos primeras.

### Lo que hay hoy, medido

`backend/app/static/css/` son 23 hojas y 13 787 líneas. Tres de ellas declaran su
propio bloque `:root`, y los mismos colores aparecen con tres nombres distintos:

| Concepto | `style.css` | `community_feed.css` | `admin.css` |
| --- | --- | --- | --- |
| Teal de marca | `--primary-color: #0F766E` | `--clr-teal-dark: #0F766E` | `--admin-primary: #6366f1` |
| Teal claro | `--secondary-color: #5EEAD4` | `--clr-teal-light: #5EEAD4` | `--admin-accent-teal: #14b8a6` |
| Tinta | `--text-color: #0F172A` | `--clr-text: #0F172A` | `--admin-text: #f1f5f9` |
| Tinta secundaria | `--text-secondary: #475569` | `--clr-subtle: #475569` | `--admin-text-secondary: #94a3b8` |

Dos hojas coinciden en el valor y discrepan en el nombre; la tercera derivó a
otra paleta sobre fondo oscuro. No es un sistema de diseño con variantes: son
tres fuentes de verdad para un color, que es exactamente la clase de duplicación
que la Definition of Done global del tablero prohíbe introducir en el código
nuevo.

Sobre idiomas, el producto es monolingüe hoy: `base.html` declara `<html
lang="en">`, es el único `lang=` del árbol, y no hay contenido traducido ni
selector de idioma en los 27 templates ni en los 23 archivos JS.

## Decisión 1 — Estilos: Tailwind v4 con los tokens actuales en `@theme`

Se adopta **Tailwind v4**, y la paleta que ya existe se declara una sola vez en
`frontend/src/styles/index.css` dentro de `@theme`.

Las dos opciones de §7 no son excluyentes en Tailwind v4, y esa es la razón de
elegirlo: `@theme` compila a custom properties CSS *y* genera utilidades, así que
`--color-brand: #0f766e` es a la vez `bg-brand` desde un componente y
`var(--color-brand)` desde cualquier CSS que aún lo necesite. La opción «tokens
CSS» se obtiene entera; lo que añade Tailwind por encima es que el estilo de una
pantalla deja de necesitar un archivo propio, que es el mecanismo concreto por el
que se llegó a 23 hojas.

Los valores no se rediseñan. Se toman literales de `style.css`, que es la hoja
base que carga `base.html`, y de `community_feed.css` donde coincide. `#0F766E`
es el teal de marca en las dos.

Consecuencias que las verticales heredan y no vuelven a decidir:

- Una pantalla nueva no crea un archivo CSS. Si necesita CSS propio —una
  animación, un `grid-template-areas` largo— usa los tokens, nunca un hex suelto.
- El fondo oscuro del admin es un **scope sobre los mismos tokens**, no una
  cuarta paleta. TASK-053 lo rellena contra la baseline capturada en TASK-035.
- La paridad visual se demuestra contra esa baseline. Que el token exista no
  prueba que la pantalla se vea igual.

### Por qué no la alternativa

CSS Modules más tokens a mano habría exigido inventar una convención de nombres,
una de composición y una disciplina de revisión para sostenerlas, para terminar
en el mismo sitio con más trabajo. La restricción de §7 no es «no usar
utilidades»: es no acabar con una hoja por pantalla.

## Decisión 2 — i18n: i18next desde el inicio, con `en` como único locale

Se adopta **i18next + react-i18next** ya, con un solo catálogo (`en`) y todo el
texto de interfaz pasando por `t()`.

El supuesto de §7 —«si se mantendrán varios idiomas»— no está confirmado, así
que la decisión no se toma por el idioma sino por el coste de equivocarse en cada
dirección. Adoptarlo ahora cuesta un provider y un JSON, y si nunca llega un
segundo idioma eso es todo lo que se pagó. No adoptarlo cuesta, si llega,
reabrir las ocho verticales una por una. Las dos ramas no son simétricas.

Hay además una señal en el propio plan: §10 ya lista «validación i18n» como paso
de la lane de frontend en CI. El pipeline que el plan describe da por supuesto
que existe un catálogo que validar.

Consecuencias:

- Ninguna cadena visible se escribe literal en un componente.
- `frontend/tools/check-i18n.mjs` valida el catálogo: ninguna clave vacía, todos
  los locales con el mismo conjunto de claves que `en`, y ninguna `t("…")`
  literal del código ausente del catálogo. TASK-039 lo conecta a la lane.
- En desarrollo y en tests, una clave ausente **lanza**. Una etiqueta en blanco
  en producción es peor que un fallo ruidoso al escribirla.
- `SUPPORTED_LOCALES` tiene un elemento. Añadir el segundo es añadir un
  directorio y una entrada; no toca las pantallas.

## Límites conocidos del stack local

Registrados aquí porque se descubrieron al validar TASK-038 y afectan a quien
levante el compose, no porque esta ficha los resuelva:

- **CV analysis no funciona sin credenciales de storage.** Cada barrido del
  runner construye un `S3Service`, que lanza `ValueError` si faltan
  `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` o `BUCKET_NAME`. `api` y `worker`
  registran el fallo y siguen vivos —el runner nunca muere por un barrido
  fallido—, así que el stack arranca y el resto del producto funciona. El
  compose pasa esas variables desde el shell del desarrollador y no las
  versiona. Un MinIO local no serviría sin tocar el backend: `S3Service` no
  admite `endpoint_url`. Le corresponde a TASK-054, que es dueña del worker.
- **`/healthz` y `/readyz` todavía no existen.** Nginx ya los proxea y el
  healthcheck del compose usa mientras tanto una ruta que no toca base de datos
  ni proveedores. TASK-045 los publica y entonces el healthcheck apunta ahí.
- **Dos runners a la vez en local.** El proceso `api` arranca el runner en su
  lifespan y el servicio `worker` arranca otro. Es seguro porque reclamar un job
  es un único UPDATE condicional, así que exactamente uno lo empieza
  (`app/services/ai/cvAnalysisRunner.py`). TASK-054 saca el loop del proceso web
  y deja un solo consumidor.
