#!/usr/bin/env bash
# One service account per workload, each with the permissions that workload
# needs and none it does not.
#
# The separation is not bureaucracy: the frontend serves static files and must
# not be able to read a database password; the migrate job must be able to reach
# the database and must not be able to publish images; the deployer must be able
# to deploy and must not be able to read the secrets it wires up. When one of
# these is compromised, what it can do is what this file says.
set -euo pipefail
cd "$(dirname "$0")"
source ./config.env

API_SA="sc-api@${PROJECT_ID}.iam.gserviceaccount.com"
FRONT_SA="sc-front@${PROJECT_ID}.iam.gserviceaccount.com"
MIGRATE_SA="sc-migrate@${PROJECT_ID}.iam.gserviceaccount.com"
TASKS_SA="sc-tasks@${PROJECT_ID}.iam.gserviceaccount.com"
DEPLOYER_SA="sc-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

create_sa() {
  local account="$1" display="$2"
  local id="${account%%@*}"
  if gcloud iam service-accounts describe "$account" --project "$PROJECT_ID" >/dev/null 2>&1; then
    echo "Service account $id already exists"
  else
    gcloud iam service-accounts create "$id" \
      --display-name "$display" --project "$PROJECT_ID"
  fi
}

create_sa "$API_SA"      "StudentsCompass API runtime"
create_sa "$FRONT_SA"    "StudentsCompass frontend runtime"
create_sa "$MIGRATE_SA"  "StudentsCompass migration job"
create_sa "$TASKS_SA"    "StudentsCompass Cloud Tasks dispatcher"
create_sa "$DEPLOYER_SA" "StudentsCompass CI deployer"

grant() {
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member "serviceAccount:$1" --role "$2" --condition=None --quiet >/dev/null
  echo "  $1 -> $2"
}

echo "Granting project-level roles:"

# --- API runtime -----------------------------------------------------------
# cloudsql.client       reaches the managed database over the connector
# cloudtasks.enqueuer   creates the CV-analysis task (TASK-054)
# NOT secretmanager.secretAccessor at project level: access is granted per
# secret in 40-secrets.sh, so the API can read the six values it needs and
# not every secret the project will ever hold.
grant "$API_SA" roles/cloudsql.client
grant "$API_SA" roles/cloudtasks.enqueuer

# --- Frontend runtime ------------------------------------------------------
# Nothing. It serves a compiled bundle and proxies to the API; it holds no
# credential, reads no secret and touches no Google API. An empty list here is
# the point, not an omission.

# --- Migration job ---------------------------------------------------------
grant "$MIGRATE_SA" roles/cloudsql.client

# --- Cloud Tasks dispatcher -------------------------------------------------
# The identity Cloud Tasks mints the OIDC token for. It needs no project role:
# being able to be *impersonated by the queue* is granted below, and the API
# verifies this exact email (app/core/internalAuth.py).
gcloud iam service-accounts add-iam-policy-binding "$TASKS_SA" \
  --member "serviceAccount:service-$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')@gcp-sa-cloudtasks.iam.gserviceaccount.com" \
  --role roles/iam.serviceAccountTokenCreator \
  --project "$PROJECT_ID" --quiet >/dev/null
echo "  cloudtasks service agent -> tokenCreator on $TASKS_SA"

# --- CI deployer -----------------------------------------------------------
# artifactregistry.writer  push images
# run.developer            deploy revisions and execute the migrate job
# iam.serviceAccountUser   act as the runtime accounts when deploying
# NOT secretAccessor: CI wires secret *references* into the service definition
# and never reads a value. A deploy pipeline that can read production secrets is
# a deploy pipeline whose logs are a liability.
grant "$DEPLOYER_SA" roles/artifactregistry.writer
grant "$DEPLOYER_SA" roles/run.developer
grant "$DEPLOYER_SA" roles/iam.serviceAccountUser

echo
echo "Service accounts ready. Runtime identities:"
echo "  api      $API_SA"
echo "  front    $FRONT_SA"
echo "  migrate  $MIGRATE_SA"
echo "  tasks    $TASKS_SA"
echo "  deployer $DEPLOYER_SA"
