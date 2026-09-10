#!/usr/bin/env bash
# One Docker repository holding both images (§4 Fase 4).
#
# One repository, two image names — studentscompass/api and studentscompass/front
# — rather than two repositories: they share a lifecycle, a region and a cleanup
# policy, and splitting them would double the IAM surface for no separation that
# matters. The plan asks for "two images", which this satisfies.
set -euo pipefail
cd "$(dirname "$0")"
source ./config.env

if gcloud artifacts repositories describe "$REPOSITORY" \
      --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
  echo "Repository $REPOSITORY already exists"
else
  gcloud artifacts repositories create "$REPOSITORY" \
    --repository-format=docker \
    --location "$REGION" \
    --description "StudentsCompass API and frontend images" \
    --project "$PROJECT_ID"
fi

# Keep the images a rollback might need and drop the rest. Cloud Run rolls back
# by revision, and a revision pins an image digest, so deleting an old image
# would make its revision unbootable — hence a count that comfortably exceeds
# the number of revisions anyone would roll back through.
gcloud artifacts repositories set-cleanup-policies "$REPOSITORY" \
  --location "$REGION" --project "$PROJECT_ID" \
  --policy=cleanup-policy.json 2>/dev/null || \
  echo "NOTE: set the cleanup policy manually if this gcloud version lacks the flag"

echo "Artifact Registry ready: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}"
