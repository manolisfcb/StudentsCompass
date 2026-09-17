#!/usr/bin/env bash
# Enable exactly the APIs this deployment uses, and no others.
#
# Idempotent: enabling an already-enabled API is a no-op, so this script is safe
# to re-run and is the first step of a rebuild from nothing.
set -euo pipefail
cd "$(dirname "$0")"
source ./config.env

# artifactregistry - the two images
# run               - the two services and the migrate job
# secretmanager     - every runtime credential
# iamcredentials    - Workload Identity Federation token exchange
# sts               - the federated token exchange itself
# cloudtasks        - the CV-analysis dispatch (TASK-054)
# cloudscheduler    - the reconciliation tick (TASK-054)
# monitoring        - alert policies and notification channels (TASK-057).
#                     Logging is on by default; Monitoring is not, and
#                     70-observability.sh fails on its first call without it.
# billingbudgets    - the spend budget of TASK-057, when BILLING_ACCOUNT_ID is set
# sqladmin          - the managed database, if one is used
gcloud services enable \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  cloudtasks.googleapis.com \
  cloudscheduler.googleapis.com \
  monitoring.googleapis.com \
  billingbudgets.googleapis.com \
  --project "$PROJECT_ID"

echo "APIs enabled for $PROJECT_ID"
