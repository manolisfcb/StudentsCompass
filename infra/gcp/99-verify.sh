#!/usr/bin/env bash
# What TASK-055 claims, checked against the project rather than asserted.
#
# Run after the other scripts. Every check prints PASS or FAIL and the script
# exits non-zero if any failed, so it is usable as a gate rather than as
# something to read.
set -uo pipefail
cd "$(dirname "$0")"
source ./config.env
# Same list 40-secrets.sh creates from, so this asserts the secrets the code
# needs rather than a copy that can quietly fall behind it.
source ./_secrets.sh

FAILURES=0
check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "PASS  $label"
  else
    echo "FAIL  $label"
    FAILURES=$((FAILURES + 1))
  fi
}

echo "--- Artifact Registry ---"
check "repository $REPOSITORY exists" \
  gcloud artifacts repositories describe "$REPOSITORY" --location "$REGION" --project "$PROJECT_ID"

echo
echo "--- No service-account keys anywhere in the project ---"
# The acceptance criterion, checked directly: a user-managed key is the thing
# WIF exists to make unnecessary, and finding one means someone took a shortcut.
for sa in sc-api sc-front sc-migrate sc-tasks sc-deployer; do
  account="${sa}@${PROJECT_ID}.iam.gserviceaccount.com"
  keys="$(gcloud iam service-accounts keys list --iam-account "$account" \
            --managed-by=user --format='value(name)' --project "$PROJECT_ID" 2>/dev/null | wc -l | tr -d ' ')"
  if [ "$keys" = "0" ]; then
    echo "PASS  $sa has no user-managed keys"
  else
    echo "FAIL  $sa has $keys user-managed key(s) — delete them; CI uses WIF"
    FAILURES=$((FAILURES + 1))
  fi
done

echo
echo "--- Workload Identity Federation ---"
check "pool github exists" \
  gcloud iam workload-identity-pools describe github --location=global --project "$PROJECT_ID"
check "provider github-actions exists" \
  gcloud iam workload-identity-pools providers describe github-actions \
    --workload-identity-pool=github --location=global --project "$PROJECT_ID"

condition="$(gcloud iam workload-identity-pools providers describe github-actions \
  --workload-identity-pool=github --location=global --project "$PROJECT_ID" \
  --format='value(attributeCondition)' 2>/dev/null)"
if [[ "$condition" == *"$GITHUB_REPOSITORY"* ]]; then
  echo "PASS  provider is scoped to $GITHUB_REPOSITORY"
else
  echo "FAIL  provider has no repository condition — ANY GitHub repo could impersonate"
  FAILURES=$((FAILURES + 1))
fi

echo
echo "--- Secrets ---"
for name in "${SECRET_NAMES[@]}"; do
  check "secret $name exists" gcloud secrets describe "$name" --project "$PROJECT_ID"
done

# A container with no version is a deploy that fails at start, not at wiring:
# --set-secrets resolves at container start, so an empty secret takes the
# revision down rather than the pipeline.
for name in "${SECRET_NAMES[@]}"; do
  count="$(gcloud secrets versions list "$name" --project "$PROJECT_ID" --format='value(name)' 2>/dev/null | wc -l | tr -d ' ')"
  if [ "$count" = "0" ]; then
    echo "FAIL  secret $name has no version — a revision wired to it will not start"
    FAILURES=$((FAILURES + 1))
  else
    echo "PASS  secret $name has $count version(s)"
  fi
done

# The frontend runtime must not be able to read any of them.
front="sc-front@${PROJECT_ID}.iam.gserviceaccount.com"
leaked=0
for name in "${SECRET_NAMES[@]}"; do
  if gcloud secrets get-iam-policy "$name" --project "$PROJECT_ID" --format=json 2>/dev/null \
      | grep -q "$front"; then
    echo "FAIL  $name is readable by the frontend service account"
    leaked=$((leaked + 1))
  fi
done
if [ "$leaked" = "0" ]; then
  echo "PASS  the frontend identity can read no secret"
else
  FAILURES=$((FAILURES + leaked))
fi

echo
echo "--- Cloud Tasks ---"
check "queue $TASKS_QUEUE exists" \
  gcloud tasks queues describe "$TASKS_QUEUE" --location "$REGION" --project "$PROJECT_ID"

# The queue signs its OIDC token as this identity and the internal endpoint
# accepts that email and no other (app/core/internalAuth.py). If the Cloud Tasks
# service agent cannot impersonate it, every dispatch arrives unauthenticated.
tasks_sa="sc-tasks@${PROJECT_ID}.iam.gserviceaccount.com"
agent="service-$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)' 2>/dev/null)@gcp-sa-cloudtasks.iam.gserviceaccount.com"
if gcloud iam service-accounts get-iam-policy "$tasks_sa" --project "$PROJECT_ID" --format=json 2>/dev/null \
    | grep -q "$agent"; then
  echo "PASS  Cloud Tasks may mint tokens as sc-tasks"
else
  echo "FAIL  the Cloud Tasks service agent cannot impersonate sc-tasks"
  FAILURES=$((FAILURES + 1))
fi

echo
if [ "$FAILURES" = "0" ]; then
  echo "All checks passed."
else
  echo "$FAILURES check(s) failed."
fi
exit "$FAILURES"
