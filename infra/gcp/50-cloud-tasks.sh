#!/usr/bin/env bash
# The queue that carries CV analysis off the request path (TASK-054).
#
# Nothing created this before: 00-enable-apis.sh turned the API on and
# 20-service-accounts.sh created the identity Cloud Tasks signs its OIDC token
# for, but the queue itself was missing, so a deployment wired for
# TASK_DISPATCH_TRANSPORT=cloud_tasks had nowhere to enqueue.
set -euo pipefail
cd "$(dirname "$0")"
source ./config.env

TASKS_SA="sc-tasks@${PROJECT_ID}.iam.gserviceaccount.com"

if gcloud tasks queues describe "$TASKS_QUEUE" \
     --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
  echo "Queue $TASKS_QUEUE already exists — reconciling its limits"
  ACTION=update
else
  ACTION=create
fi

# Why these numbers, rather than the defaults:
#
# max-concurrent-dispatches 5
#   Every dispatch becomes a request to the API that calls Gemini and holds a
#   database connection for as long as the analysis takes. The default (1000)
#   would let the queue alone saturate max-instances and exhaust the connection
#   budget, and the users whose requests were merely trying to load a page would
#   be the ones who noticed.
#
# max-dispatches-per-second 5
#   Paced against the AI daily limits the app already enforces (AI_BASE_DAILY_LIMIT)
#   rather than against what the queue can physically push.
#
# max-attempts 5 with backoff 10s → 300s
#   The outbox retries its own delivery up to TASK_OUTBOX_MAX_ATTEMPTS (8), so
#   these two ladders compose. Five attempts over ~10 minutes covers a restart or
#   a cold start; past that the failure is not transient and retrying is just
#   paying to fail repeatedly. The row stays FAILED and visible.
gcloud tasks queues "$ACTION" "$TASKS_QUEUE" \
  --location "$REGION" \
  --project "$PROJECT_ID" \
  --max-concurrent-dispatches=5 \
  --max-dispatches-per-second=5 \
  --max-attempts=5 \
  --min-backoff=10s \
  --max-backoff=300s

echo
echo "Queue ready. The API service needs these (they are configuration, not secrets):"
echo "  TASK_DISPATCH_TRANSPORT=cloud_tasks"
echo "  CLOUD_TASKS_QUEUE=projects/${PROJECT_ID}/locations/${REGION}/queues/${TASKS_QUEUE}"
echo "  CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL=${TASKS_SA}"
echo "  INTERNAL_TASKS_BASE_URL=<public URL of ${API_SERVICE}>"
echo "  INTERNAL_TASKS_AUDIENCE=<same URL, pinned separately so a redirect cannot move it>"
echo
echo "INTERNAL_TASKS_SHARED_SECRET must NOT be set in production: the internal"
echo "endpoint refuses a production deployment that authenticates with it."
