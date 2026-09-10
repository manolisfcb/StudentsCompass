#!/usr/bin/env bash
# Create the secret *containers* and grant per-secret access. Values are not in
# this file, are not passed as arguments, and are never printed.
#
# The distinction that matters: this script creates named, versioned secrets and
# says who may read each one. Putting a value in is a separate, deliberate act
# performed by a human from a terminal — see the runbook — because a value that
# flows through a script flows through that script's logs and shell history.
#
# Nothing here reads a secret. Neither does CI: the deploy wires *references*
# (projects/…/secrets/NAME/versions/latest) into the service definition, and
# Cloud Run resolves them at start. A literal value in a service definition
# would be readable by anyone with run.viewer, forever, in plain text.
set -euo pipefail
cd "$(dirname "$0")"
source ./config.env

# The list of secrets and their readers lives in _secrets.sh, which 99-verify.sh
# also sources. Two copies of this list is how the old one grew a secret nobody
# reads and lost one the app needs on every upload.
source ./_secrets.sh

for entry in "${SECRETS[@]}"; do
  name="${entry%%:*}"
  readers="${entry#*:}"

  if gcloud secrets describe "$name" --project "$PROJECT_ID" >/dev/null 2>&1; then
    echo "Secret $name already exists"
  else
    # Automatic replication: this is a single-region deployment and pinning
    # locations buys nothing here beyond a constraint to forget about.
    gcloud secrets create "$name" --replication-policy=automatic --project "$PROJECT_ID"
    echo "Secret $name created (no version yet — add one from a terminal)"
  fi

  IFS=',' read -ra accounts <<< "$readers"
  for account in "${accounts[@]}"; do
    # Per secret, not project-wide: the frontend account appears nowhere in this
    # loop, and the API cannot read a secret that is not on its list.
    gcloud secrets add-iam-policy-binding "$name" \
      --member "serviceAccount:${account}" \
      --role roles/secretmanager.secretAccessor \
      --project "$PROJECT_ID" --quiet >/dev/null
    echo "  $name readable by $account"
  done
done

echo
echo "Secrets with no version yet:"
for entry in "${SECRETS[@]}"; do
  name="${entry%%:*}"
  count="$(gcloud secrets versions list "$name" --project "$PROJECT_ID" --format='value(name)' 2>/dev/null | wc -l | tr -d ' ')"
  [ "$count" = "0" ] && echo "  $name"
done
echo "Add a value with:  gcloud secrets versions add NAME --data-file=- --project $PROJECT_ID"
echo "(type the value, then Ctrl-D. --data-file=- keeps it out of argv and history.)"
