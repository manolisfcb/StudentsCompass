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

**No se construye descubrimiento de vacantes.** Ni scraping, ni crawler, ni pool
compartido de ofertas. El usuario trae la vacante. El §11 explica por qué y qué
camino deja abierto.

El flujo completo es:

```
CV (ya analizado) ──────┐
                        ├─→ Match · Gaps · Roadmap        [$0 LLM]
Oferta pegada ─→ Parse ─┘         ├─→ CV Coach            [1 llamada]
                [1 llamada,       └─→ Interview Prep      [1 llamada]
                 caché compartida]
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

Y existen tres defectos que este plan corrige porque lo bloquean:

- **El matching semántico está apagado de facto.** `EMBEDDINGS_PROVIDER` vale
  `"hash"` por defecto (`embeddingService.py:30`), así que todo vector guardado
  hoy es un hash de relleno. Además `semantic_matching_ready` se define como
  `local_configured and local_package_available`
  (`embeddingService.py:115`), leído por `_semantic_ready()`
  (`semanticMatchingService.py:289`): con cualquier proveedor que no sea el
  local, el matching semántico se desactiva **sin error**.
- **El catálogo canónico tiene 117 skills**, sembradas para tres roles (Data
  Analyst, Business Analyst, Junior Data Scientist) en
  `capstoneAnalyticsSeedService.py:298`. Una oferta fuera de esos roles produce
  omisiones silenciosas: una skill no catalogada no aparece como gap, **no
  aparece en absoluto**.
- **`get_effective_model_name()`** (`embeddingService.py:104`) etiqueta como
  `hash-v1` cualquier vector que no venga del proveedor local, de modo que
  vectores de API compartirían clave `(resume_id, model_name)` con vectores
  hash.

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

Tres llamadas como máximo por par (CV, oferta), y sólo una es automática:

| Llamada | Disparo | Depende de | Caché |
|---|---|---|---|
| Parse de la oferta | Automática al pegar | Sólo de la oferta | `sha256(texto)`, **compartida entre usuarios** |
| CV Coach | Botón | CV + oferta | Por (CV, oferta, tier) |
| Interview Prep | Botón | CV + oferta + gaps | Por (CV, oferta, tier) |

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
| *Profundo* | *+ alternativas, respuesta modelo, contexto de empresa* | *+ repreguntas* | *45* |

Profundo queda **definido pero no construido** (§10). Añadirlo después es
configuración.

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

El parse consume crédito para que nadie pegue 500 ofertas sin tocar el resto.

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
| Cuota | **2 análisis de por vida** | 1.000 créditos/mes |
| Al agotarse | **Modo manual, gratis, indefinido** | Renueva |
| Coste máximo para nosotros | **$0,006** | **$2,00** |
| Margen bruto | — | 80% |

Exposición total con 10.000 usuarios gratuitos: **$62 de por vida**.

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

**Condición de salida obligatoria de C2**, que bloquea todo lo posterior:
ninguna feature de C3 en adelante llega a usuarios hasta que estén vivos el
límite de 2 de por vida contado sobre el ledger, `REQUIRE_VERIFIED_FOR_AI=1` y
los tres cercos del §7.

## 9. Tareas

Se añaden al tablero [TASKS.md](TASKS.md) siguiendo su protocolo. IDs desde
TASK-072; el último ocupado es TASK-071.

| ID | Tarea | Fase | Depende de |
|---|---|---|---|
| TASK-072 | Proveedor de embeddings por API con dimensión 384 y normalización L2 | C0 | — |
| TASK-073 | Corregir `semantic_matching_ready` y `get_effective_model_name` para proveedores no locales | C0 | TASK-072 |
| TASK-074 | Tabla `skill_embeddings`, generación por lotes y backfill del catálogo | C0 | TASK-072 |
| TASK-075 | Leer vectores de skill desde base de datos en `SemanticMatchingService` | C0 | TASK-074 |
| TASK-076 | Alerta sobre `fallback_to_hash_count` y `local_failure_count` | C0 | TASK-073 |
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

## 10. Qué queda fuera, deliberadamente

- **Descubrimiento de vacantes en cualquier forma.** Ni scraping de LinkedIn, ni
  APIs de agregadores, ni lectura de career pages. §11 explica el camino.
- **Tier Profundo.** Definido en §6, no construido. Es configuración.
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
| Granja de cuentas contra el tier gratuito | Verificación de email, límite por IP, blocklist y Google OAuth. Exposición acotada en $0,006 por cuenta |
| El porcentaje transmite una precisión que no tenemos | Nunca se muestra desnudo: banda y desglose obligatorios (§4.1) |

## 13. Números a validar antes de fijar precios

Las estimaciones de tokens por llamada (~2k de entrada en el parse, ~4,6k en el
coach, ~5,5k en el prep) son estimadas, no medidas. Hay que medirlas con 20 ofertas
reales en cuanto C3 funcione y reajustar el valor del crédito. La estructura de
§7 no cambia; sólo su constante.

Los precios de proveedor usados en este plan proceden de agregadores públicos
consultados el 2026-09-20, no de las páginas oficiales. Contrastar contra
`ai.google.dev/gemini-api/docs/pricing` y
`developers.openai.com/api/docs/pricing` antes de publicar un plan de pago.
