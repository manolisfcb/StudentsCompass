#!/usr/bin/env bash
# TASK-057. Alertas sobre las métricas que TASK-028/TASK-045 ya emiten — nunca
# una segunda fuente de telemetría (plan 08 §6.4, nota de reconciliación en
# TASKS.md junto a TASK-028).
#
# Dos orígenes de datos, no uno:
#
#   1. Métricas nativas de Cloud Run (5xx, p95): Cloud Monitoring ya las
#      calcula por servicio sin que la aplicación haga nada. Repetirlas como
#      métrica basada en logs sería la fuente duplicada que la nota de
#      reconciliación prohíbe.
#   2. Métricas basadas en logs, sobre los campos que
#      backend/app/logging.py::CloudLoggingFormatter ya escribe en cada línea
#      JSON (`status`, `external_failures`, y desde este mismo cambio de
#      TASK-057, `stale_job_recovery`/`failed_after_spend`). Un campo que el
#      request log o el logger de dominio no escriben no puede alertarse desde
#      aquí sin inventar ese origen — ver la sección "Lo que no se cubre" más
#      abajo, en vez de fingir cobertura con un filtro que nunca hace match.
set -euo pipefail
cd "$(dirname "$0")"
source ./config.env

if [ -z "${ALERT_EMAIL:-}" ]; then
  echo "ALERT_EMAIL no está definido en config.env." >&2
  exit 1
fi

API_LOG_FILTER='resource.type="cloud_run_revision" AND resource.labels.service_name="'"$API_SERVICE"'"'

# --- Canal de notificación ---------------------------------------------------
CHANNEL_NAME="$(gcloud beta monitoring channels list \
  --project "$PROJECT_ID" \
  --filter="displayName='StudentsCompass on-call' AND type='email'" \
  --format='value(name)' | head -n1)"

if [ -z "$CHANNEL_NAME" ]; then
  CHANNEL_NAME="$(gcloud beta monitoring channels create \
    --project "$PROJECT_ID" \
    --display-name="StudentsCompass on-call" \
    --type=email \
    --channel-labels="email_address=${ALERT_EMAIL}" \
    --format='value(name)')"
  echo "Canal de notificación creado: $CHANNEL_NAME"
else
  echo "Canal de notificación ya existe: $CHANNEL_NAME"
fi

# --- Métricas basadas en logs ------------------------------------------------
#
# Cada una se crea solo si no existe: `gcloud logging metrics create` no es
# idempotente por sí mismo (falla si el nombre ya existe), así que la
# comprobación es explícita en vez de dejar que el segundo `./70-...sh` de
# alguien rompa a mitad de camino.
create_log_metric() {
  local name="$1" description="$2" filter="$3"
  if gcloud logging metrics describe "$name" --project "$PROJECT_ID" >/dev/null 2>&1; then
    echo "Métrica de log $name ya existe"
  else
    gcloud logging metrics create "$name" \
      --project "$PROJECT_ID" \
      --description="$description" \
      --log-filter="$filter"
    echo "Métrica de log $name creada"
  fi
}

create_log_metric "cloud_run_429_responses" \
  "Respuestas 429 de la API (plan 08 §6.4)." \
  "${API_LOG_FILTER} AND jsonPayload.status=429"

create_log_metric "cloud_run_external_call_failures" \
  "Llamadas a un proveedor externo (Gemini, S3, ImageKit) que fallaron, contadas por request_context.py. Cubre 'reintentos y errores de storage' de §6.4: ambos pasan por app.core.observability.external_call sin distinguir proveedor a nivel de alerta — el desglose por proveedor vive en los campos provider.<nombre>.failures de la misma línea, consultable en Logs Explorer cuando esta alerta dispara." \
  "${API_LOG_FILTER} AND jsonPayload.external_failures>0"

create_log_metric "cv_analysis_jobs_failed_after_spend" \
  "Jobs de análisis de CV cuyo worker desapareció después de llamar al proveedor de IA: ya costó dinero y no produjo un resultado almacenado (cvAnalysisService.recover_stale_jobs, INTERRUPTED_AFTER_SPEND_MESSAGE). Es la única de las tres salidas de la recuperación de jobs vencidos que no es limpieza rutinaria." \
  "${API_LOG_FILTER} AND jsonPayload.stale_job_recovery=true AND jsonPayload.failed_after_spend>0"

create_log_metric "ai_budget_ceiling_reached" \
  "El guard de TASK-007 (aiBudgetGuard) rechazó una llamada a un proveedor de IA por techo de tasa o de cuota diaria alcanzado. Proxy de presión de gasto: no hay una cifra en dólares emitida a logs (el ledger de TASK-012 vive en la tabla ai_usage_event, no en una línea de log), así que esto alerta sobre el guard actuando, que es lo que TASK-057 pide 'apoyado en' — no sobre el gasto en sí." \
  "${API_LOG_FILTER} AND jsonPayload.logger=\"app.services.ai.aiBudgetGuard\" AND severity=\"WARNING\""

# --- Políticas de alerta ------------------------------------------------------
#
# Cada política referencia el canal de arriba y trae su propio runbook: un
# umbral sin la pregunta "y ahora qué hago" es ruido, no una alerta (TASK-057,
# Proposed Solution).
apply_policy() {
  local display_name="$1" policy_file="$2"
  local existing
  existing="$(gcloud alpha monitoring policies list \
    --project "$PROJECT_ID" \
    --filter="displayName='${display_name}'" \
    --format='value(name)' | head -n1)"
  if [ -n "$existing" ]; then
    gcloud alpha monitoring policies update "$existing" \
      --project "$PROJECT_ID" --policy-from-file="$policy_file" >/dev/null
    echo "Política '$display_name' actualizada ($existing)"
  else
    gcloud alpha monitoring policies create \
      --project "$PROJECT_ID" --policy-from-file="$policy_file" >/dev/null
    echo "Política '$display_name' creada"
  fi
}

POLICY_DIR="$(mktemp -d)"
trap 'rm -rf "$POLICY_DIR"' EXIT

# 1. Tasa de 5xx — métrica nativa de Cloud Run, no de logs.
cat > "$POLICY_DIR/5xx.yaml" <<EOF
displayName: "StudentsCompass API — tasa de 5xx"
combiner: OR
notificationChannels: ["$CHANNEL_NAME"]
documentation:
  content: |
    5xx sostenidos en $API_SERVICE. Runbook: revisar Logs Explorer filtrando
    severity>=WARNING y resource.labels.service_name="$API_SERVICE"; el campo
    endpoint (no path) agrupa por ruta. Si coincide con un job_id repetido,
    sospechar del runner de CV (TASK-054) antes que de una petición aislada.
  mimeType: text/markdown
conditions:
  - displayName: "5xx > 1% durante 5 minutos"
    conditionThreshold:
      filter: >-
        resource.type="cloud_run_revision"
        AND resource.labels.service_name="$API_SERVICE"
        AND metric.type="run.googleapis.com/request_count"
        AND metric.labels.response_code_class="5xx"
      comparison: COMPARISON_GT
      thresholdValue: 0.01
      duration: 300s
      aggregations:
        - alignmentPeriod: 300s
          perSeriesAligner: ALIGN_RATE
EOF
apply_policy "StudentsCompass API — tasa de 5xx" "$POLICY_DIR/5xx.yaml"

# 2. p95 de latencia — métrica nativa de Cloud Run.
cat > "$POLICY_DIR/p95.yaml" <<EOF
displayName: "StudentsCompass API — p95 de latencia"
combiner: OR
notificationChannels: ["$CHANNEL_NAME"]
documentation:
  content: |
    p95 por encima de 2s durante 10 minutos. Runbook: comparar contra
    sql_statements y provider.*.ms del request log del mismo periodo — un p95
    alto con sql_statements normal apunta a un proveedor externo lento
    (Gemini, S3), no a la base.
  mimeType: text/markdown
conditions:
  - displayName: "p95 > 2000ms durante 10 minutos"
    conditionThreshold:
      filter: >-
        resource.type="cloud_run_revision"
        AND resource.labels.service_name="$API_SERVICE"
        AND metric.type="run.googleapis.com/request_latencies"
      comparison: COMPARISON_GT
      thresholdValue: 2000
      duration: 600s
      aggregations:
        - alignmentPeriod: 600s
          perSeriesAligner: ALIGN_PERCENTILE_95
EOF
apply_policy "StudentsCompass API — p95 de latencia" "$POLICY_DIR/p95.yaml"

# 3. 429 sostenidos.
cat > "$POLICY_DIR/429.yaml" <<EOF
displayName: "StudentsCompass API — respuestas 429"
combiner: OR
notificationChannels: ["$CHANNEL_NAME"]
documentation:
  content: |
    Alguien está siendo limitado de forma sostenida. Runbook: si es un solo
    actor (campo actor del request log), probablemente legítimo (rate limit
    funcionando); si son muchos actores distintos en poco tiempo, revisar si
    Redis (REDIS_URL) está disponible — sin él cada instancia cuenta sola y
    max-instances > 1 hace los límites más laxos de lo que parecen, no más
    estrictos.
  mimeType: text/markdown
conditions:
  - displayName: "Al menos una 429 en 5 minutos"
    conditionThreshold:
      filter: >-
        resource.type="cloud_run_revision"
        AND resource.labels.service_name="$API_SERVICE"
        AND metric.type="logging.googleapis.com/user/cloud_run_429_responses"
      comparison: COMPARISON_GT
      thresholdValue: 0
      duration: 300s
      aggregations:
        - alignmentPeriod: 300s
          perSeriesAligner: ALIGN_COUNT
EOF
apply_policy "StudentsCompass API — respuestas 429" "$POLICY_DIR/429.yaml"

# 4. Fallos de llamadas externas (reintentos y errores de storage).
cat > "$POLICY_DIR/external.yaml" <<EOF
displayName: "StudentsCompass API — fallos de proveedor externo"
combiner: OR
notificationChannels: ["$CHANNEL_NAME"]
documentation:
  content: |
    Una petición registró al menos un fallo hacia un proveedor externo
    (Gemini, S3, ImageKit). Runbook: en Logs Explorer, ordenar por
    provider.<nombre>.failures del mismo periodo para identificar cuál; un
    solo proveedor fallando es su incidente, no el nuestro — verificar su
    status page antes de escalar.
  mimeType: text/markdown
conditions:
  - displayName: "Al menos un fallo externo en 5 minutos"
    conditionThreshold:
      filter: >-
        resource.type="cloud_run_revision"
        AND resource.labels.service_name="$API_SERVICE"
        AND metric.type="logging.googleapis.com/user/cloud_run_external_call_failures"
      comparison: COMPARISON_GT
      thresholdValue: 0
      duration: 300s
      aggregations:
        - alignmentPeriod: 300s
          perSeriesAligner: ALIGN_COUNT
EOF
apply_policy "StudentsCompass API — fallos de proveedor externo" "$POLICY_DIR/external.yaml"

# 5. Jobs de CV interrumpidos después de gastar.
cat > "$POLICY_DIR/stale-jobs.yaml" <<EOF
displayName: "StudentsCompass — jobs de CV fallidos tras gastar"
combiner: OR
notificationChannels: ["$CHANNEL_NAME"]
documentation:
  content: |
    Un job de análisis de CV llamó al proveedor de IA y su worker desapareció
    antes de guardar el resultado (deploy a medio camino, OOM, crash). El
    usuario ve un error y puede reintentar; esto no se recupera solo.
    Runbook: confirmar en job_analysis que el estado es FAILED con
    error_message = INTERRUPTED_AFTER_SPEND_MESSAGE; si el volumen es alto,
    sospechar de un despliegue reciente que interrumpió jobs en vuelo — este
    es exactamente el escenario que el smoke pre-promoción de deploy.yml
    (TASK-056) existe para no dejar pasar en el propio despliegue, pero un
    job que ya estaba en PROCESSING antes del despliegue no pasa por ese
    smoke.
  mimeType: text/markdown
conditions:
  - displayName: "Al menos un job fallido tras gastar en 15 minutos"
    conditionThreshold:
      filter: >-
        resource.type="cloud_run_revision"
        AND resource.labels.service_name="$API_SERVICE"
        AND metric.type="logging.googleapis.com/user/cv_analysis_jobs_failed_after_spend"
      comparison: COMPARISON_GT
      thresholdValue: 0
      duration: 900s
      aggregations:
        - alignmentPeriod: 900s
          perSeriesAligner: ALIGN_COUNT
EOF
apply_policy "StudentsCompass — jobs de CV fallidos tras gastar" "$POLICY_DIR/stale-jobs.yaml"

# 6. Techo de gasto de IA alcanzado.
cat > "$POLICY_DIR/ai-budget.yaml" <<EOF
displayName: "StudentsCompass — techo de gasto de IA alcanzado"
combiner: OR
notificationChannels: ["$CHANNEL_NAME"]
documentation:
  content: |
    aiBudgetGuard (TASK-007) rechazó una llamada por techo de tasa o cuota
    diaria. Runbook: si es esperado (pico legítimo de uso), no hay acción; si
    no, revisar ai_usage_event (el ledger de TASK-012) por actor para
    descartar un bucle de reintento del lado cliente o abuso. AI_KILL_SWITCH
    corta las llamadas en seco si hace falta actuar antes de investigar.
  mimeType: text/markdown
conditions:
  - displayName: "Al menos un rechazo del guard de IA en 15 minutos"
    conditionThreshold:
      filter: >-
        resource.type="cloud_run_revision"
        AND resource.labels.service_name="$API_SERVICE"
        AND metric.type="logging.googleapis.com/user/ai_budget_ceiling_reached"
      comparison: COMPARISON_GT
      thresholdValue: 0
      duration: 900s
      aggregations:
        - alignmentPeriod: 900s
          perSeriesAligner: ALIGN_COUNT
EOF
apply_policy "StudentsCompass — techo de gasto de IA alcanzado" "$POLICY_DIR/ai-budget.yaml"

# --- Budget de facturación ----------------------------------------------------
#
# Un budget de proyecto, no solo de un SKU de IA: Gemini no es el único coste
# variable (Cloud Run escala con tráfico), y un budget que solo mirara IA
# dejaría un pico de tráfico normal sin ningún aviso.
if [ -n "${BILLING_ACCOUNT_ID:-}" ] && [ -n "${BUDGET_AMOUNT:-}" ]; then
  EXISTING_BUDGET="$(gcloud billing budgets list \
    --billing-account="$BILLING_ACCOUNT_ID" \
    --filter="displayName='StudentsCompass monthly'" \
    --format='value(name)' 2>/dev/null | head -n1 || true)"
  if [ -n "$EXISTING_BUDGET" ]; then
    echo "Budget de facturación ya existe: $EXISTING_BUDGET"
  else
    gcloud billing budgets create \
      --billing-account="$BILLING_ACCOUNT_ID" \
      --display-name="StudentsCompass monthly" \
      --budget-amount="${BUDGET_AMOUNT}" \
      --filter-projects="projects/${PROJECT_ID}" \
      --threshold-rule=percent=0.5 \
      --threshold-rule=percent=0.9 \
      --threshold-rule=percent=1.0 \
      --notifications-rule-monitoring-notification-channels="$CHANNEL_NAME"
    echo "Budget de facturación creado: ${BUDGET_AMOUNT} (avisos en 50/90/100%)"
  fi
else
  echo "BILLING_ACCOUNT_ID o BUDGET_AMOUNT no definidos en config.env — budget omitido."
fi

echo
echo "--- Lo que no se cubre, y por qué ---"
echo "Pool de DB: no hay una métrica de tamaño de pool en uso emitida a logs ni"
echo "a Cloud Monitoring (SQLAlchemy no la expone y Neon no es Cloud SQL, así"
echo "que no hay métrica nativa tampoco). Su síntoma —conexiones agotadas— sale"
echo "como 5xx o timeouts, ya cubiertos por la alerta de 5xx. Añadir la métrica"
echo "real requeriría instrumentar app/db.py; no se ha hecho aquí para no"
echo "inventar una fuente de telemetría que TASK-028 no decidió emitir."
