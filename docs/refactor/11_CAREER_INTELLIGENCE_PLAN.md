# Plan: Career Lab como copiloto de candidatura

Fecha: 2026-09-20. Revisión local: `2e11e2c` (`main`). Este plan añade una
vertical nueva sobre la arquitectura que dejó
[08_REST_REACT_CLOUD_RUN_PLAN.md](08_REST_REACT_CLOUD_RUN_PLAN.md); no la
reemplaza ni reabre ninguna de sus decisiones. Extiende los controles de coste
documentados en [ai_cost_controls.md](../ai_cost_controls.md), que siguen siendo
la referencia operativa.

## 1. Resultado objetivo

El usuario pega la descripción de una vacante que ya encontró por su cuenta y
Career Lab le responde cuatro preguntas sobre **esa** vacante concreta:

1. ¿Encaja conmigo, y por qué? — score, fortalezas y gaps priorizados.
2. ¿Qué me falta y qué estudio primero? — roadmap ajustado al tiempo disponible.
3. ¿Cómo adapto mi CV a esta oferta? — sin inventar experiencia.
4. ¿Cómo me preparo para la entrevista? — preguntas derivadas de su CV y de esa
   descripción.

Más un registro de candidaturas propio con sus analíticas.


Y, como **plus de pago**, una preparación técnica a fondo para esa vacante: no
una lista de preguntas, sino una guía por tema («para esta vacante de ML repasa
estos modelos, cómo se entrenan, qué es lo que más se pregunta de cada uno y qué
ejercicio práctico te pueden poner»). Mientras no exista pasarela de pago sólo
la usa el admin; el resto de usuarios la ve como *coming soon*. Detalle en §4.4
y §4.5.

**No se construye descubrimiento de vacantes.** Ni scraping, ni crawler, ni pool
compartido de ofertas. El usuario trae la vacante. El §11 explica por qué y qué
camino deja abierto.

El flujo completo es:

```
CV (ya analizado) ──────┐
                        ├─→ Match · Gaps · Roadmap        [$0 LLM]
Oferta pegada ─→ Parse ─┘         ├─→ CV Coach            [1 llamada]
                [1 llamada,       ├─→ Interview Prep      [1 llamada]
                 caché compartida]└─→ Interview Prep técnico  [plus de pago]
                                        ├─ Plan técnico   [1 llamada]
                                        └─ Tema a fondo   [1 llamada/tema]
```

## 2. Línea base comprobada

En el snapshot revisado ya existe, y se reutiliza sin reescribir:

- **Motor de matching completo y desacoplado.**
  `SkillExtractionService.extract_known_skills_from_text` es una función de
  texto, indiferente al origen.
  `SemanticMatchingService.analyze_required_skill_matches` recibe `list[dict]`,
  no modelos ORM. `SkillGapScoringService` prioriza los gaps y ya redacta su
  propia explicación. Ninguno necesita cambios para leer una oferta pegada.
- **Optimizador de rutas de aprendizaje** (`learningRouteOptimizerService.py`,
  1012 líneas) con restricciones de presupuesto, horas y número de cursos.
- **pgvector 384 dimensiones** con índice HNSW coseno sobre `resume_embeddings`,
  y caché por `text_fingerprint` + `fingerprint_version` que evita regenerar un
  vector cuyo texto no cambió.
- **Controles de coste**: `AIUsageService.reserve()` con ciclo
  reserved/committed/released/expired sobre el ledger durable
  `ai_usage_events`; `aiBudgetGuard.ensure_llm_attempt_allowed(attempts=N)` con
  techo diario global, cap por minuto y kill switch.
- **Límites de registro por IP** (ráfaga y cuentas/día) y **gate de email
  verificado** (`REQUIRE_VERIFIED_FOR_AI`), ya implementados y apagados por
  defecto.
- **Cola durable** con leases y `provider_attempted_at`
  (`jobAnalysisModel.py`), que impide que una recuperación vuelva a gastar en el
  proveedor, más el outbox y su worker.
- **Cloud Run en mínimos**: `--min-instances=0 --max-instances=1` en el API.
  Con una sola instancia el contador en proceso es correcto; no hace falta
  Redis, pero sí `AI_ALLOW_UNSHARED_COUNTER=1` o el guard falla cerrado en
  producción.

Y existen cuatro defectos que este plan corrige porque lo bloquean:

- **El matching semántico está apagado de facto.** `EMBEDDINGS_PROVIDER` vale
  `"hash"` por defecto, así que todo vector guardado hoy es un hash de relleno.
  Desde `e6ec0b4`, que retiró el proveedor local, `semantic_matching_ready` vale
  `False` fijo, leído por `_semantic_ready()` en `semanticMatchingService.py`:
  no hay ningún proveedor con el que el matching semántico se encienda.
  *(Corregido en TASK-072/073, 2026-10-05.)*
- **El catálogo canónico tiene 117 skills**, sembradas para tres roles (Data
  Analyst, Business Analyst, Junior Data Scientist) en
  `capstoneAnalyticsSeedService.py:298`. Una oferta fuera de esos roles produce
  omisiones silenciosas: una skill no catalogada no aparece como gap, **no
  aparece en absoluto**.
- **`get_effective_model_name()`** devuelve `hash-v1` siempre, de modo que
  vectores de API compartirían clave `(resume_id, model_name)` con vectores
  hash. *(Corregido en TASK-072: los vectores Gemini se guardan como
  `gemini-embedding-001@384`.)*
- **Los umbrales de similitud son de MiniLM** (detectado al ejecutar C0, no
  estaba en la versión original del plan). `semanticMatchingService.py` decide
  match semántico con coseno ≥ 0,72 y débil ≥ 0,48, y bandas de contexto en
  0,78 / 0,62. Con `gemini-embedding-001` a 384 dos skills sin relación dan
  0,74–0,80: con esos umbrales casi todo sería match. Ver §4.3.

## 3. Decisiones tomadas

| # | Decisión | Razón |
|---|---|---|
| D1 | Sin descubrimiento de vacantes; el usuario pega la oferta | Elimina el riesgo operativo y legal del scraping. El coste y la latencia del descubrimiento eran el cuello de botella real, no el LLM |
| D2 | Embeddings por API, no `sentence-transformers` | La memoria del modelo obliga a pagar instancia; la API cuesta ~$12 de por vida para 10.000 usuarios |
| D3 | Vectores de skills persistidos en base de datos | El catálogo es finito: se embebe cada skill una vez. Evita ~50 llamadas API por análisis |
| D4 | El parse de la oferta va fijado a un modelo server-side | Es lo único cacheable entre usuarios. Si el usuario elige su modelo, la caché deja de ser compartida |
| D5 | Capa de proveedor agnóstica; el cliente manda un slug, nunca un ID de modelo | Los modelos se retiran con calendario (Gemini 2.5 Flash-Lite el 16/10/2026, GPT-5-mini en 12/2026) |
| D6 | El usuario ve *tiers* (Esencial / Completo / Profundo), nunca nombres de modelo | Evita la comparación «¿por qué te pago si me suscribo al proveedor?» y permite cambiar el modelo en silencio |
| D7 | Cuota en créditos ponderados por coste, no en número de análisis | Con modelos variables el coste por análisis va de $0,002 a $0,057. Contar análisis no acota nada |
| D8 | Free: 2 análisis de por vida, luego modo manual gratuito indefinido | Pre-ingresos. El modo manual es determinista y cuesta $0, así que el usuario sigue teniendo producto |
| D9 | El Interview Prep técnico es el tier Profundo del Prep y sólo de pago | Es la pieza de mayor valor percibido y la más cara de generar. Ponerla en Free rompería el techo de $0,012 por cuenta del §7 |
| D10 | Hasta tener pagos, el plus sólo lo usa el admin (`is_superuser`); el resto ve *coming soon* | Permite construirlo, usarlo de verdad y medir su coste real (§13) antes de ponerle precio, sin exponer gasto a usuarios que no pagan |
| D11 | El acceso lo decide el servidor, nunca el cliente | La SPA sólo pinta lo que la API declara. Un cliente modificado no puede desbloquear una llamada de pago |

## 4. Arquitectura del flujo y su coste

### 4.1 Lo que no toca un LLM

Estas partes son deterministas, corren sobre el motor existente y su coste
marginal es cero. Están disponibles en todos los planes, incluido el gratuito
agotado:

- Extracción de skills del CV y de la oferta contra el catálogo.
- Score de compatibilidad, fortalezas, gaps priorizados y su explicación.
- Roadmap de aprendizaje.
- Tracker de candidaturas y analíticas personales.

El score se compone así, sobre las piezas que ya calculan
`SemanticMatchingService` y `SkillGapScoringService`:

```
score = gate × (0,45·cobertura_skills + 0,25·coseno_CV_oferta
              + 0,20·afinidad_título + 0,10·encaje_seniority)
```

`gate` es 0/1 por ubicación y modalidad cuando el usuario las declara. Los pesos
son calibrables y viven en configuración.

El número se muestra **siempre** junto a su banda (`ApplicationMatchStrength`,
que ya existe con `strong_match` / `match` / `weak_match`) y a su desglose por
componente. Nunca desnudo: con una sola vacante el porcentaje es una afirmación
absoluta, no un orden relativo, y no hay con qué calibrarlo.

### 4.2 Lo que sí toca un LLM

Tres llamadas como máximo por par (CV, oferta) en los tiers Esencial y Completo,
y sólo una es automática. El plus técnico (§4.4) añade las suyas, todas a
demanda:

| Llamada | Disparo | Depende de | Caché |
|---|---|---|---|
| Parse de la oferta | Automática al pegar | Sólo de la oferta | `sha256(texto)`, **compartida entre usuarios** |
| CV Coach | Botón | CV + oferta | Por (CV, oferta, tier) |
| Interview Prep | Botón | CV + oferta + gaps | Por (CV, oferta, tier) |
| Plan técnico *(plus)* | Botón | Oferta parseada + skills del CV + gaps | Por (CV, oferta, `prompt_version`) |
| Tema a fondo *(plus)* | Botón, por tema | Plan técnico + tema + nivel del usuario en él | Por (plan, tema, `prompt_version`) |

Reabrir un resultado guardado cuesta cero. Regenerarlo cuesta créditos: si fuera
gratis se convierte en un bucle de gasto.

### 4.3 Embeddings

Se necesitan vectores de tres cosas, y cada texto se embebe **una vez en su
vida**:

| Qué | Dónde se guarda | Cuándo |
|---|---|---|
| CV | `resume_embeddings` (ya existe, con fingerprint) | Al subir o cambiar el CV |
| Oferta | Columna en `job_description_parses` | Al parsear, una vez por hash |
| Skill del catálogo | **`skill_embeddings` (nuevo)** | Al registrar la skill |

El tercero es el que decide la viabilidad. Hoy
`semanticMatchingService.py:100-103` embebe cada skill dentro de un bucle
secuencial: un CV con 30 skills contra una oferta con 20 requisitos son ~50
embeddings por análisis. Con un proveedor local son 50 ms; con API son 50
viajes HTTPS en serie. La caché que lo protege (`_SKILL_EMBEDDING_CACHE`) es un
LRU en proceso, y Cloud Run rota instancias y escala a cero.

Persistidos en base de datos, el análisis típico hace **cero** llamadas de
embedding, y **dos** en el peor caso (CV y oferta ambos nuevos).

**Proveedor**: `gemini-embedding-001` con `output_dimensionality=384`, para no
migrar la columna ni el índice HNSW. Dos condiciones que hay que verificar
empíricamente antes de fijar el esquema:

- Que la API acepte 384. Si no, se migra la columna a 768: como todos los
  vectores actuales son hashes sin valor, la migración es vaciar y regenerar.
- **Normalización L2 manual.** Con reducción dimensional sólo la salida nativa
  viene pre-normalizada; un coseno sobre vectores sin normalizar sale
  sutilmente mal, que es el peor tipo de error aquí.
- `task_type` = `SEMANTIC_SIMILARITY`, **el mismo en ambos lados** de toda
  comparación, o los espacios no alinean.

**Verificado el 2026-10-05** (TASK-072): la API acepta 384 sin migrar nada, y a
esa dimensión devuelve vectores de norma ≈ 0,43, así que la normalización manual
era imprescindible.

**Umbrales por modelo.** Un coseno no es un número portable. Medido con Gemini a
384: sinónimos 0,95–0,99, skills relacionadas 0,88–0,94, sin relación
0,74–0,80; contexto CV↔oferta alineada 0,87, rol adyacente 0,84, otra
tecnología 0,76, otra profesión 0,68. Cada modelo lleva un `SimilarityProfile`
(match semántico ≥ 0,95, débil ≥ 0,88; contexto reescalado entre 0,70 y 0,90) y
un modelo sin perfil **no** activa el matching semántico. El componente
`coseno_CV_oferta` del score de §4.1 usa ese valor reescalado, no el coseno
crudo: en crudo, un CV sin relación con la oferta regalaría ~17 puntos. Los
valores de contexto son provisionales hasta calibrarlos con ofertas reales en
TASK-079. Detalle en `docs/capstone_product/matching_methodology.md`.

### 4.4 Interview Prep técnico — el plus de pago

El Interview Prep de Esencial y Completo responde «qué me pueden preguntar». El
plus responde **«qué tengo que dominar para esta entrevista técnica, y cómo lo
practico»**. Es el tier Profundo del Prep (D9), definido en §6 y construido en
la fase C8.

Ejemplo de lo que tiene que producir, para una vacante de ML junior con un CV
que trae Python y pandas pero poco modelado:

> **Tema 1 — Modelos de árboles y gradient boosting** · prioridad alta · gap
> La oferta pide «XGBoost/LightGBM» como obligatorio y tu CV no los menciona.
> - *Qué dominar*: cómo se construye un árbol (criterio de split, impureza),
>   bagging vs boosting, cómo se entrena el boosting sobre los residuos, learning
>   rate y número de árboles, regularización, early stopping.
> - *Lo que más se pregunta*: «¿Por qué random forest reduce varianza y boosting
>   sesgo?», «¿Cómo evitas overfitting en XGBoost?», «¿Cómo tratas variables
>   categóricas?» — cada una con el esquema de una buena respuesta y las
>   repreguntas habituales.
> - *Ejercicio probable*: take-home de clasificación tabular con desbalance de
>   clases; qué se evalúa (validación, métrica elegida, leakage) y errores
>   típicos.
> - *Cómo lo cuentas con tu CV*: conectar el proyecto X del CV con el tema.
> - *Para estudiarlo*: cursos del catálogo que cubren la skill.

Se genera en **dos niveles**, para que el coste siga al interés real del
usuario y no al tamaño de la guía:

1. **Plan técnico** — una llamada. Devuelve:
   - El **formato de entrevista probable** según rol y seniority (screening,
     live coding, take-home, system design / ML design, caso), etiquetado
     siempre como *probable*, nunca como el proceso real de la empresa.
   - **Entre 4 y 8 temas**, cada uno con: nombre, por qué aparece (cita el
     requisito de la oferta del que sale), prioridad, y si para el usuario es
     **gap**, **refuerzo** (lo tiene pero flojo) o **fortaleza a defender**. La
     prioridad sale de `SkillGapScoringService`, no del LLM: el modelo explica
     y desarrolla, el ranking lo pone el motor determinista.
   - Por tema, 3–5 conceptos clave y 2 preguntas de muestra.
2. **Tema a fondo** — una llamada por tema, a demanda. Devuelve: conceptos con
   la explicación que se espera oír en una entrevista (cómo funciona, cómo se
   entrena, cuándo usarlo y cuándo no, trade-offs), 6–10 preguntas típicas
   teóricas y prácticas con esquema de respuesta y repreguntas, uno o dos
   ejercicios prácticos probables con criterios de evaluación y errores
   comunes, y cómo enlazar el tema con la experiencia que ya trae el CV.

Reglas de contenido, que van en el prompt **y** en validación del schema:

- **Sin inventar sobre la empresa.** Nada de «en Google preguntan X». Las
  preguntas se presentan como habituales para el rol y la tecnología, no como
  filtradas. Es el mismo principio que «sin inventar experiencia» del CV Coach.
- **Sin enlaces generados por el modelo.** Los recursos de estudio salen del
  catálogo de cursos que ya usa el roadmap (`learningRouteOptimizerService`),
  emparejados por `skill_id`. Un modelo que inventa URLs es el fallo más
  visible posible en una función de pago.
- **Anclado a la oferta.** Cada tema cita el requisito del parse del que sale;
  un tema sin requisito de origen se descarta en validación.
- **Nivel ajustado al CV.** El mismo tema se explica distinto si es gap (desde
  la base) que si es fortaleza (a nivel de repregunta difícil).

### 4.5 Acceso al plus: admin ahora, Premium después, *coming soon* para el resto

El acceso lo resuelve el servidor con una sola función, que es la única fuente
de verdad (D11):

```
feature_access(user, "technical_prep") -> "available" | "coming_soon" | "upgrade_required"
```

| Situación | Resultado |
|---|---|
| `user.is_superuser` | `available` — siempre, en todas las fases |
| `TECHNICAL_PREP_PUBLIC` apagado (valor por defecto) | `coming_soon` para todos los demás |
| `TECHNICAL_PREP_PUBLIC` encendido y plan Premium | `available` |
| `TECHNICAL_PREP_PUBLIC` encendido y plan Free | `upgrade_required` |

- **Backend.** Los endpoints del plus llaman a `feature_access` **antes** de
  `AIUsageService.reserve()` y de `aiBudgetGuard`, de modo que un usuario sin
  acceso nunca reserva crédito ni llega al proveedor. Responden 403 con un
  código estable (`feature_coming_soon` / `upgrade_required`), en la línea del
  modelo de errores de [error_model.md](../error_model.md). El patrón ya existe
  en `current_admin_user` (`adminService.py:46`) y en
  `capstoneAnalyticsRoute.py:66`; aquí no se reutiliza tal cual porque la regla
  dejará de ser sólo de admin.
- **Sesión.** La sesión expone un mapa `features: {technical_prep: <estado>}`,
  igual que hoy expone `is_superuser` (`sessionSchema.py:36`) para navegación.
  La SPA **no** deduce el acceso de `is_superuser`: sólo pinta el estado que
  le llega.
- **Frontend.** Con `available`, la sección funciona. Con `coming_soon`, se ve
  una tarjeta dentro del análisis de la vacante con el nombre del plus, una
  descripción de lo que hará y una vista previa estática (un ejemplo genérico
  fijo, nunca generado para el usuario), con la insignia *Coming soon* y sin
  botón de acción. Con `upgrade_required`, la misma tarjeta lleva el CTA de
  Premium. La tarjeta no dispara ninguna petición al backend del plus.
- **Uso del admin.** Se registra en `ai_usage_events` con
  `feature="technical_prep"` y `source="admin_preview"`. No consume créditos de
  usuario, pero **sí** cuenta en el guard global: un admin no es una vía para
  saltarse el techo diario. Esas filas son las que alimentan la medición de
  §13.
- **Abrirlo** es encender `TECHNICAL_PREP_PUBLIC` cuando C7 esté en producción
  y los costes medidos cuadren con los créditos. Es configuración, no
  despliegue.

## 5. Modelo de datos

Tres tablas nuevas. **No se toca `job_postings`** (su `company_id` es
`NOT NULL`, pertenece al lado recruiter) ni `job_skills` (que ya hace doble
función entre postings y semillas de rol; una tercera la vuelve ilegible).

### `job_description_parses` — caché compartida entre usuarios

| Columna | Notas |
|---|---|
| `text_hash` | PK. `sha256` del texto normalizado |
| `parsed` | JSONB: requisitos, obligatorio vs deseable, importancia, seniority |
| `embedding` | `Vector(384)` |
| `model_id`, `prompt_version` | Qué produjo este parse |
| `source` | De dónde vino el texto. Hoy sólo `pasted`; es lo que §11 necesita |
| `created_at` | Para TTL si se decide caducarlos |

Es compartida porque el parse **no depende del CV**. Por eso D4 fija su modelo:
si lo eligiera el usuario, la clave pasaría a ser `(hash, modelo, prompt)` y la
caché perdería casi todo su acierto.

### `job_targets` — la vacante de un usuario

| Columna | Notas |
|---|---|
| `user_id`, `resume_id` | Propiedad |
| `text_hash` | → `job_description_parses` |
| `raw_text` | El texto pegado |
| `source` | `pasted` hoy; abre la puerta a `ats_api` sin migrar (§11) |
| `title`, `company`, `location`, `workplace_type` | Del parse, editables |
| `status` | `pending` / `parsing` / `ready` / `failed` |
| `attempts`, `lease_expires_at`, `provider_attempted_at` | Patrón de `jobAnalysisModel`, copiado tal cual |
| `match_snapshot` | JSONB: score y desglose en el momento del análisis |

### `skill_embeddings`

| Columna | Notas |
|---|---|
| `skill_id` | FK a `skills` |
| `embedding` | `Vector(384)` |
| `model_name`, `text_fingerprint` | Mismo esquema de versionado que `resume_embeddings` |

Índice único por `(skill_id, model_name)` e índice HNSW coseno.

### Tracker de candidaturas

Tabla propia, **separada de `applications`**. `ApplicationStatus` (`applied` →
`in_review` → `interview` → `offer`) es el pipeline real compartido con los
recruiters sobre ofertas internas. El tracker es un diario personal sobre
ofertas externas donde no hay empresa en la plataforma: `saved`, `applied`,
`recruiter_screen`, `technical`, `final`, `offer`, `rejected`. Meter estos
estados en el enum existente rompería el lado recruiter.

### Catálogo auto-alimentado

Cuando el parse encuentra una skill que no está en `skills`, se registra con
`source='llm_jd_v1'` y sigue. `SkillModel` ya tiene la columna `source` y la
restricción `uq_skills_normalized_name`; con `SkillNormalizer` para deduplicar,
la carrera la resuelve la base de datos.

Es necesario porque el motor indexa por `skill["skill_id"]`, un UUID del
catálogo: una skill sin UUID **no puede atravesarlo**. Y tiene el efecto lateral
de que el catálogo crece con el uso real en vez de quedarse en 117 entradas.

Las skills auto-registradas entran con estado revisable, no directamente como
canónicas. Complementariamente, sembrar el catálogo desde ESCO u O*NET —
públicos, con miles de entradas y sus alias — es trabajo de datos puntual con
coste recurrente cero.

## 6. Capa de proveedor agnóstica

La frontera es **estrecha y de alto nivel**, no un chat genérico:

```
generate_structured(task, prompt, schema, tier) -> modelo Pydantic validado
```

El adaptador es dueño de lo que **no** es uniforme entre proveedores:

- **Traducción del schema.** Gemini usa `response_json_schema`; OpenAI usa
  `response_format: {type: "json_schema", strict: true}`, cuyo modo estricto
  rechaza construcciones que `model_json_schema()` de Pydantic genera;
  Anthropic lo hace vía `input_schema` de tool-use. El schema no sobrevive el
  viaje sin traducción.
- **Mapeo de errores.** `is_non_retryable_llm_error`
  (`resume_analyzer/llm_errors.py`) está modelado sobre cadenas de Gemini. Cada
  proveedor nombra distinto cuota, auth y rate.
- **Parámetros de razonamiento**, que no tienen forma común.
- **Reporte del coste real** de cada llamada, que es lo que alimenta el §7.
- **Semáforo de concurrencia por proveedor.** El actual
  (`LLM_SEMAPHORE = asyncio.Semaphore(10)`) es global y con forma de Gemini.

Implementación sugerida: LiteLLM como librería, que ya resuelve interfaz
unificada, cálculo de coste, excepciones normalizadas y schema por proveedor,
sin infraestructura extra. Se envuelve sólo lo que se use. **OpenRouter no**:
mete una capa opaca justo donde la arquitectura está construida sobre saber
exactamente lo que cuesta cada llamada.

### Tiers

El mapeo `tier → modelo` vive en **configuración, no en código**, para cambiarlo
sin desplegar.

| Tier | Coach | Prep | Créditos |
|---|---|---|---|
| **Esencial** | 3 bullets | 5 preguntas | 3 |
| **Completo** | todos los bullets, qué evalúa el entrevistador, estructura de respuesta | 10 preguntas | 5 |
| **Profundo** *(plus, de pago)* | *+ alternativas, respuesta modelo* — no se construye aún | **Interview Prep técnico** (§4.4): plan técnico + temas a fondo | ver §7 |

Del tier Profundo se construye **sólo el lado Prep**, como Interview Prep
técnico (fase C8), con acceso restringido al admin hasta que haya pagos (§4.5).
El lado Coach de Profundo sigue **definido pero no construido** (§10). El
«contexto de empresa» que figuraba aquí se retira: sin descubrimiento ni fuente
verificable, sería contenido inventado sobre una empresa real.

Los tiers difieren en **qué generan**, no sólo en qué modelo corre por detrás.
Si sólo cambiara el modelo, llamar «Profundo» a uno insinuaría que hace más
cuando sólo hace mejor. Cada tier lleva además su propio `max_output_tokens`,
que es lo que justifica su precio en créditos.

### El modelo no se filtra

El usuario nunca ve un nombre de modelo. Los cinco puntos de fuga a cerrar:

1. **Mensajes de error.** `friendly_analysis_error_message`
   (`cvAnalysisService.py:54`) ya es el patrón correcto; hay que extenderlo a
   cada proveedor nuevo.
2. **El propio modelo autoidentificándose** en su salida. Requiere instrucción
   en el prompt **y** un filtro de sanidad; el prompt solo no basta.
3. **La respuesta de la API**: devuelve `tier`, nunca `model`, ni en campos de
   depuración ni en cabeceras.
4. **Logs que lleguen al navegador.**
5. **La política de privacidad**, donde va al revés: los subprocesadores **sí**
   deben declararse. Se nombran en bloque («proveedores de IA de terceros,
   incluidos Google, OpenAI y Anthropic») sin decir qué tier usa cuál.

Internamente, cada artefacto guardado registra su `model_id` real: hace falta
para soporte, contabilidad de coste y decidir qué modelo mover de tier.

## 7. Control de coste

Tres cercos concéntricos. Cada uno tapa el fallo del anterior, y hacen falta los
tres.

### Cerco 1 — Por llamada: acota el peor caso

- **`max_output_tokens` por tarea.** El output cuesta entre 4× y 10× más que el
  input. Sin tope, un interview prep de 2,5k tokens esperados que se desmadre a
  16k pasa de $0,025 a $0,160 en el tier más caro. Con tope en 4k queda en
  $0,040. Acota el peor caso, no la media, que es lo que arruina un mes.
- **Cap de longitud de la oferta**, al modo de `MAX_RESUME_CHARS = 60_000` que ya
  existe para el CV.
- **Razonamiento apagado en el parse**, donde los tokens de thinking se
  facturan como output y no aportan a una extracción estructurada.

### Cerco 2 — Por usuario: créditos ponderados

**1 crédito = $0,002 de inferencia.** Cada acción consume lo que cuesta:

| Acción | Créditos |
|---|---|
| Parse de la oferta | 1 — y **0 si la oferta ya está en caché** |
| Coach + Prep, Esencial | 2 |
| Coach + Prep, Completo | 4 |
| Análisis completo, Esencial | **3** |
| Análisis completo, Completo | **5** |
| Plan técnico *(plus)* | **10** *(estimado)* |
| Tema a fondo *(plus)*, por tema | **15** *(estimado)* |

El parse consume crédito para que nadie pegue 500 ofertas sin tocar el resto.

Una guía técnica completa típica (plan + 5 temas) son ~85 créditos, ≈ $0,17:
cabe holgada en los 1.000 créditos/mes de Premium y no cambia su coste máximo,
que sigue acotado por la cuota. Los dos valores del plus son **estimaciones**
hasta que el uso del admin dé cifras reales (§13). Cada llamada lleva su propio
`max_output_tokens` (Cerco 1): el tema a fondo es la salida más larga de todo
el producto y la que más necesita el tope.

`AIUsageService.reserve()` ya tiene el ciclo de reserva; sólo tiene que reservar
**N unidades en vez de 1**. `ensure_llm_attempt_allowed(attempts=N)` ya acepta
el parámetro.

### Cerco 3 — Global: el que ya existe, corregido

`aiBudgetGuard` cuenta **intentos**, y su propio docstring advierte que es un
proxy del dinero. Con modelos variables un intento vale entre $0,002 y $0,057,
y el techo deja de significar nada. Pasa a contar **créditos**.

### Planes

| | Free | Premium ($9,99/mes) |
|---|---|---|
| Tiers | Esencial | Esencial y Completo |
| Interview Prep técnico | *Coming soon* → luego CTA de Premium | **Sí** (cuando se abra, §4.5) |
| Cuota | **2 análisis de por vida** | 1.000 créditos/mes |
| Al agotarse | **Modo manual, gratis, indefinido** | Renueva |
| Coste máximo para nosotros | **$0,012** (2 análisis × 3 créditos × $0,002) | **$2,00** |
| Margen bruto | — | 80% |

Exposición total con 10.000 usuarios gratuitos: **$120 de por vida** en LLM, más
los ~$12 de embeddings de D2.

### La cuota de por vida se cuenta en el ledger, no en Redis

`AIUsageService` está construido por días (`today_utc_bounds`, claves con fecha,
TTL de 36 h), que es correcto para cuotas diarias. Una cuota **de por vida** en
un contador efímero se resetea sola en cada reinicio o flush.

La fuente de verdad es el ledger durable `ai_usage_events`: el conteo de filas
`committed` del usuario. Redis sigue siendo para rate limiting; la titularidad
de la cuenta es un hecho de la cuenta.

### Defensa del tier gratuito

Con cuota de por vida el abuso no está en el uso — está en **crear cuentas**.
Una cuota mensual se limita sola porque esperar cuesta; una de por vida se
resetea registrándose otra vez.

| Defensa | Estado | Acción |
|---|---|---|
| Gate de email verificado | **Ya implementado**, apagado | Poner `REQUIRE_VERIFIED_FOR_AI=1` tras hacer backfill de `is_verified` |
| Límite de cuentas por IP | **Ya implementado** | Revisar umbrales |
| Blocklist de dominios desechables | Falta | Lista pública mantenida |
| Google OAuth en el plan gratuito | Falta | La defensa más fuerte; los usuarios son estudiantes y todos tienen Google |

### Fugas a tapar

1. **Regenerar cuesta créditos.** Reabrir, no.
2. **Un reintento por bug propio no lo paga el usuario.** El guard global cuenta
   los tres intentos; el crédito del usuario, uno.
3. **Reservas huérfanas**: aplicar el settle/release y el reclamo de expiradas
   que `AIUsageService` ya implementa.
4. **Doble gasto en recuperación**: `provider_attempted_at` copiado a
   `job_targets`.
5. **Fallback que sube de precio**: si el modelo elegido falla, se cae sólo
   hacia igual o más barato, y sin cobrar créditos extra por la caída.

## 8. Fases

**C1 es lanzable y no gasta un céntimo en LLM.** Ese es el punto de la
secuencia: hay producto en la calle antes de la primera llamada de pago.

| Fase | Qué entrega | Coste LLM | ¿Lanzable? |
|---|---|---|---|
| **C0** | Embeddings por API, `skill_embeddings`, defectos del §2 corregidos | ~$0 | No (interno) |
| **C1** | Pegar oferta → match, gaps, roadmap, todo por reglas | **$0** | **Sí** |
| **C2** | Capa de proveedor, tiers, créditos, cercos de coste | $0 | No (interno) |
| **C3** | Parse de la oferta por LLM + catálogo auto-alimentado | 1 llamada/oferta nueva | Sí |
| **C4** | CV Coach | 1 llamada/click | Sí |
| **C5** | Interview Prep | 1 llamada/click | Sí |
| **C6** | Tracker de candidaturas y analíticas | $0 | Sí |
| **C7** | Planes, pasarela de pago, gates de tier | $0 | Sí |
| **C8** | Interview Prep técnico (plus): acceso por `feature_access`, plan técnico, temas a fondo, tarjeta *coming soon* | 1 llamada/plan + 1/tema, sólo admin | Sí, como *coming soon*; uso real sólo admin |

**Condición de salida obligatoria de C2**, que bloquea todo lo posterior:
ninguna feature de C3 en adelante llega a usuarios hasta que estén vivos el
límite de 2 de por vida contado sobre el ledger, `REQUIRE_VERIFIED_FOR_AI=1` y
los tres cercos del §7.

**C8 no espera a C7.** Depende de C5 (reutiliza el Prep y su schema) y de C2
(capa de proveedor y cercos), pero no de los pagos: mientras sólo lo use el
admin no hay nada que cobrar. Lo que sí espera a C7 es **abrirlo** (TASK-102).

## 9. Tareas

Se añaden al tablero [TASKS.md](TASKS.md) siguiendo su protocolo. IDs desde
TASK-072; el último ocupado es TASK-071.

| ID | Tarea | Fase | Depende de |
|---|---|---|---|
| TASK-072 | Proveedor de embeddings por API con dimensión 384 y normalización L2 | C0 | — |
| TASK-073 | Corregir `semantic_matching_ready` y `get_effective_model_name` para proveedores no locales | C0 | TASK-072 |
| TASK-074 | Tabla `skill_embeddings`, generación por lotes y backfill del catálogo | C0 | TASK-072 |
| TASK-075 | Leer vectores de skill desde base de datos en `SemanticMatchingService` | C0 | TASK-074 |
| TASK-076 | Alerta sobre `fallback_to_hash_count` y `provider_failure_count` | C0 | TASK-073 |
| TASK-077 | Tablas `job_targets` y `job_description_parses` con su ciclo de lease | C1 | — |
| TASK-078 | Endpoint de alta de oferta por texto pegado, con cap de longitud | C1 | TASK-077 |
| TASK-079 | Análisis determinista oferta↔CV: score, bandas, fortalezas y gaps | C1 | TASK-077, TASK-075 |
| TASK-080 | Roadmap desde los gaps con días hasta la entrevista como restricción | C1 | TASK-079 |
| TASK-081 | Pantalla React de análisis de vacante | C1 | TASK-079 |
| TASK-082 | Sembrar el catálogo de skills desde ESCO/O\*NET | C1 | — |
| TASK-083 | Capa `generate_structured` agnóstica con traducción de schema y mapeo de errores | C2 | — |
| TASK-084 | Registro de tiers en configuración y resolución server-side por slug | C2 | TASK-083 |
| TASK-085 | Créditos ponderados en `AIUsageService` y `aiBudgetGuard` | C2 | TASK-084 |
| TASK-086 | Cuota de por vida contada sobre el ledger durable | C2 | TASK-085 |
| TASK-087 | `max_output_tokens` y caps de entrada por tarea | C2 | TASK-083 |
| TASK-088 | Cerrar las cinco fugas de nombre de modelo hacia el cliente | C2 | TASK-084 |
| TASK-089 | Parse de oferta por LLM con caché compartida por hash | C3 | TASK-083, TASK-077 |
| TASK-090 | Auto-registro de skills no catalogadas con estado revisable | C3 | TASK-089 |
| TASK-091 | CV Coach | C4 | TASK-089 |
| TASK-092 | Interview Prep | C5 | TASK-089 |
| TASK-093 | Tracker de candidaturas con estados propios | C6 | TASK-077 |
| TASK-094 | Analíticas personales de candidatura | C6 | TASK-093 |
| TASK-095 | Planes, gates de tier y pasarela de pago | C7 | TASK-085 |
| TASK-096 | Activar gate de verificación y blocklist de dominios desechables | C7 | TASK-086 |
| TASK-097 | `feature_access` server-side, flag `TECHNICAL_PREP_PUBLIC`, mapa `features` en la sesión y 403 con código estable | C8 | — |
| TASK-098 | Plan técnico: schema, prompt, validación (tema anclado a requisito, sin URLs) y caché por (CV, oferta, `prompt_version`) | C8 | TASK-092, TASK-097, TASK-087 |
| TASK-099 | Tema a fondo por tema, a demanda, con `max_output_tokens` propio | C8 | TASK-098 |
| TASK-100 | Recursos de estudio por tema desde el catálogo de cursos, emparejados por `skill_id` | C8 | TASK-098, TASK-080 |
| TASK-101 | UI React del plus: guía navegable por tema y tarjeta *coming soon* / *upgrade* según `features` | C8 | TASK-097, TASK-081 |
| TASK-102 | Abrir el plus a Premium: encender `TECHNICAL_PREP_PUBLIC`, fijar créditos con costes medidos | C7 | TASK-095, TASK-099 |

## 10. Qué queda fuera, deliberadamente

- **Descubrimiento de vacantes en cualquier forma.** Ni scraping de LinkedIn, ni
  APIs de agregadores, ni lectura de career pages. §11 explica el camino.
- **Lado Coach del tier Profundo.** Definido en §6, no construido. Del tier
  Profundo sólo se construye el Interview Prep técnico (C8).
- **Contexto de empresa** y cualquier afirmación sobre el proceso real de una
  empresa concreta. El plus técnico habla de lo habitual para el rol y la
  tecnología, no de lo que «pregunta» una empresa.
- **Simulador de entrevista interactivo** (chat de mock interview con
  corrección de respuestas). Es la evolución natural del plus, pero multiplica
  llamadas por sesión y necesita su propio diseño de coste.
- **Entrada por URL o por fichero.** Sólo texto pegado. Es lo que el usuario
  tiene delante en la otra pestaña, y no añade infraestructura ni riesgo de
  bloqueo.
- **Redis en producción.** Con `max-instances=1` el contador en proceso es
  correcto. Exige `AI_ALLOW_UNSHARED_COUNTER=1` explícito.
- **Renombrar o migrar nada de `applications`, `job_postings` o `job_skills`.**

## 11. El camino de vuelta al descubrimiento

Cada oferta pegada queda en `job_description_parses`. En unos meses eso es un corpus
de ofertas reales que usuarios reales consideraron — exactamente lo que
`market_demand_score` (`skillGapScoringService.py:27`) espera y hoy no tiene con
qué alimentarse.

Si algún día se retoma el descubrimiento, se construye sobre ese corpus y sobre
las APIs públicas de los ATS (Greenhouse, Lever, Ashby, Workable), que devuelven
JSON estructurado sin scraping ni riesgo de bloqueo. Nada de este plan cierra
esa puerta; lo único que hace falta es que las tablas nacieran con `source`, que
es lo que hace el §5.

## 12. Riesgos

| Riesgo | Cómo se cierra |
|---|---|
| La API de embeddings no acepta 384 dimensiones | Migrar la columna a 768. Los vectores actuales son hashes sin valor: vaciar y regenerar. Se verifica en TASK-072, antes de fijar esquema |
| Omisiones silenciosas por catálogo pobre | TASK-082 lo siembra desde ESCO/O\*NET y TASK-090 lo hace crecer con el uso |
| Un modelo se retira a mitad de trimestre | El mapeo tier→modelo es configuración y el usuario nunca vio el nombre (D5, D6) |
| Un fallo de coste se come el presupuesto | Tres cercos independientes (§7). El global ya existe y fallará cerrado |
| Granja de cuentas contra el tier gratuito | Verificación de email, límite por IP, blocklist y Google OAuth. Exposición acotada en $0,012 por cuenta |
| El porcentaje transmite una precisión que no tenemos | Nunca se muestra desnudo: banda y desglose obligatorios (§4.1) |
| El plus técnico inventa preguntas «de la empresa», URLs o contenido técnico incorrecto | Reglas de contenido del §4.4 en prompt y en validación; recursos sólo del catálogo; el uso del admin en C8 sirve de revisión manual antes de abrirlo |
| El plus se filtra a usuarios sin acceso | `feature_access` en servidor antes de reservar crédito (§4.5); la tarjeta *coming soon* no llama al backend del plus; test de 403 para usuario no admin |

## 13. Números a validar antes de fijar precios

Las estimaciones de tokens por llamada (~2k de entrada en el parse, ~4,6k en el
coach, ~5,5k en el prep) son estimadas, no medidas. Hay que medirlas con 20 ofertas
reales en cuanto C3 funcione y reajustar el valor del crédito. La estructura de
§7 no cambia; sólo su constante.

Lo mismo vale para el plus técnico, con una ventaja: durante C8 el admin es su
único usuario, y cada llamada queda en `ai_usage_events` con
`source="admin_preview"` y su `model_id` real. Antes de TASK-102 se calculan
sobre esas filas el coste medio y el p95 del plan técnico y del tema a fondo, y
se fijan sus créditos definitivos (hoy 10 y 15, estimados).

Los precios de proveedor usados en este plan proceden de agregadores públicos
consultados el 2026-09-20, no de las páginas oficiales. Contrastar contra
`ai.google.dev/gemini-api/docs/pricing` y
`developers.openai.com/api/docs/pricing` antes de publicar un plan de pago.
