#!/usr/bin/env bash
# Which secrets exist, and which runtime identity may read each one.
#
# This file is sourced, never executed. It exists because the list used to live
# in two places — the script that creates the secrets and the script that
# verifies them — and the two drifted: both named APIFY_API_TOKEN, which no code
# reads, and neither named IMAGEKIT_PRIVATE_KEY, which the media service reads on
# every upload. A deployment wired from that list starts clean and fails at the
# first avatar. One list, two consumers, no drift.
#
# Requires config.env to have been sourced already: PROJECT_ID builds the emails.
#
# The list is derived from what the code actually reads (a sweep of os.getenv /
# env_str across backend/app), not from what the live service happens to have
# set. Those two disagree, and the code is the one that decides whether a
# revision works.

API_SA="sc-api@${PROJECT_ID}.iam.gserviceaccount.com"
MIGRATE_SA="sc-migrate@${PROJECT_ID}.iam.gserviceaccount.com"

# name : comma-separated readers
declare -a SECRETS=(
  # The app's connection string. Neon, through the transaction pooler.
  "DATABASE_URL:${API_SA},${MIGRATE_SA}"

  # The migrator's connection string: Neon's *direct* endpoint, not the pooler.
  # PgBouncer in transaction mode cannot hold the session-level locks Alembic
  # takes, so a migration run through the pooler fails or, worse, half-applies.
  # docs/DATABASE_CONFIG.md already carves out ALEMBIC_DATABASE_URL for exactly
  # this case; Neon is what makes it necessary rather than theoretical.
  "ALEMBIC_DATABASE_URL:${MIGRATE_SA}"

  # Session signing. Rotating it logs everyone out, which is the intended blast
  # radius of a compromise and the reason it is not derived from anything else.
  "SECRET_KEY:${API_SA}"

  # Gemini.
  "GENAI_API_KEY:${API_SA}"

  # S3 for resumes and resource files.
  "AWS_ACCESS_KEY_ID:${API_SA}"
  "AWS_SECRET_ACCESS_KEY:${API_SA}"

  # ImageKit. Only the private key is read (mediaStorageService.py:50); the
  # public key and URL endpoint are set on the live service today and read by
  # nothing, so they are not secrets and not here.
  "IMAGEKIT_PRIVATE_KEY:${API_SA}"

  # Shared rate-limit windows. Without it every instance counts on its own, so
  # with max-instances > 1 the per-IP limits are not the limits they claim to be
  # (config.py:100). Optional to boot, required to be correct.
  "REDIS_URL:${API_SA}"
)

# Deliberately absent, so that removing them is a decision and not an oversight:
#
#   APIFY_API_TOKEN         read by nothing (docs/dependencies.md:77)
#   IMAGEKIT_PUBLIC_KEY     read by nothing
#   IMAGEKIT_URL_ENDPOINT   read by nothing, and a public URL besides
#   HF_TOKEN                only used when EMBEDDINGS_PROVIDER=local; the
#   HUGGINGFACE_HUB_TOKEN   default is "hash" and production does not override it
#   INTERNAL_TASKS_SHARED_SECRET
#                           the dev alternative to OIDC. A production deployment
#                           that sets only this is *refused* by the internal
#                           endpoint (config.py:248): a shared secret is not an
#                           identity. Production authenticates with sc-tasks.

SECRET_NAMES=()
for _entry in "${SECRETS[@]}"; do SECRET_NAMES+=("${_entry%%:*}"); done
unset _entry
