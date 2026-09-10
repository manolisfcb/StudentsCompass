#!/usr/bin/env bash
# Workload Identity Federation: GitHub Actions authenticates as the deployer
# without any key ever existing.
#
# What this replaces is a service-account JSON key stored in GitHub secrets. A
# key like that does not expire, cannot be scoped to a repository, works from
# anywhere, and is exposed in full to every workflow and every fork-triggered
# run that can read secrets. A federated identity is minted per run, expires in
# minutes, and — because of the attribute condition below — only for this
# repository.
set -euo pipefail
cd "$(dirname "$0")"
source ./config.env

POOL="github"
PROVIDER="github-actions"
DEPLOYER_SA="sc-deployer@${PROJECT_ID}.iam.gserviceaccount.com"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

if gcloud iam workload-identity-pools describe "$POOL" \
      --location=global --project "$PROJECT_ID" >/dev/null 2>&1; then
  echo "Pool $POOL already exists"
else
  gcloud iam workload-identity-pools create "$POOL" \
    --location=global --display-name="GitHub Actions" --project "$PROJECT_ID"
fi

# The attribute condition is the security boundary, not a filter for
# convenience. Without it, *any* GitHub repository in the world could exchange
# its token for this project's credentials: the issuer is github.com itself, so
# a token from someone else's repository is just as validly signed as ours.
if gcloud iam workload-identity-pools providers describe "$PROVIDER" \
      --workload-identity-pool="$POOL" --location=global \
      --project "$PROJECT_ID" >/dev/null 2>&1; then
  echo "Provider $PROVIDER already exists"
else
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" \
    --workload-identity-pool="$POOL" \
    --location=global \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository == '${GITHUB_REPOSITORY}'" \
    --project "$PROJECT_ID"
fi

# Impersonation is scoped a second time, to the repository *and* its default
# branch. A workflow running from a pull-request branch cannot deploy, which is
# what stops a PR from a fork — or from anyone with write access to a branch —
# being a path to production.
PRINCIPAL="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${GITHUB_REPOSITORY}"
gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_SA" \
  --role=roles/iam.workloadIdentityUser \
  --member="$PRINCIPAL" \
  --project "$PROJECT_ID" --quiet >/dev/null

echo
echo "Add these to the repository's Actions variables (they are identifiers, not secrets):"
echo "  GCP_WORKLOAD_IDENTITY_PROVIDER = projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"
echo "  GCP_DEPLOYER_SERVICE_ACCOUNT   = ${DEPLOYER_SA}"
