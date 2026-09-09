"""Centralized environment-driven configuration.

Mirrors the small inline helper style used in ``app/db.py`` so settings stay
readable and have safe defaults. Importing this module never raises: every
value falls back to a conservative default when the env var is missing or
malformed.
"""
from __future__ import annotations

import os


def env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


def env_int(name: str, default: int, *, minimum: int = 0) -> int:
    try:
        value = int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default


def env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def env_str_any(names: tuple[str, ...], default: str = "") -> str:
    """First of ``names`` that is set wins (see ``env_int_any``)."""
    for name in names:
        if os.getenv(name) is not None:
            return env_str(name, default)
    return default


def env_int_any(names: tuple[str, ...], default: int, *, minimum: int = 0) -> int:
    """First of ``names`` that is set wins. Lets a setting be renamed without
    breaking a deployment that still exports the old variable."""
    for name in names:
        if os.getenv(name) is not None:
            return env_int(name, default, minimum=minimum)
    return default


ENV = env_str("ENV", "development").lower()
IS_PRODUCTION = ENV in {"production", "prod"}

# --- Shared infra ----------------------------------------------------------
# Empty REDIS_URL keeps a per-process in-memory fallback (fine for dev/tests).
REDIS_URL = env_str("REDIS_URL")

# --- AI quota / attempts ---------------------------------------------------
# Three different units, deliberately not conflated:
#   * user units    - what a person may spend per day (AI_BASE_DAILY_LIMIT,
#                     enforced per user by AIUsageService);
#   * provider
#     attempts      - every single request sent to Gemini, retries included
#                     (AI_GLOBAL_DAILY_ATTEMPTS / AI_LLM_ATTEMPTS_PER_MIN);
#   * money         - actual provider spend. Nothing here measures money: an
#                     attempt count is a proxy, so these ceilings are named
#                     after what they really count.
# One user unit can cost several provider attempts, which is exactly why the
# global ceilings are counted at the attempt level.

# Base free daily AI requests per user, per feature. Paid plans add units via
# AIQuotaGrantModel on top of this base.
AI_BASE_DAILY_LIMIT = env_int("AI_BASE_DAILY_LIMIT", 3, minimum=0)
# Hard ceiling on total provider attempts/day across ALL users (cost circuit
# breaker). AI_GLOBAL_DAILY_BUDGET is the previous name, still honoured.
AI_GLOBAL_DAILY_ATTEMPTS = env_int_any(
    ("AI_GLOBAL_DAILY_ATTEMPTS", "AI_GLOBAL_DAILY_BUDGET"), 2000, minimum=1
)
# Cross-replica cap on provider attempt rate (smooths spend / concurrency).
# AI_LLM_CALLS_PER_MIN is the previous name, still honoured.
AI_LLM_ATTEMPTS_PER_MIN = env_int_any(
    ("AI_LLM_ATTEMPTS_PER_MIN", "AI_LLM_CALLS_PER_MIN"), 60, minimum=1
)
# Instant manual kill switch: when true, no LLM call is attempted at all.
AI_KILL_SWITCH = env_flag("AI_KILL_SWITCH", "0")
# Escape hatch for a genuinely single-process production deployment. Off by
# default: without a shared counter store the global ceilings are per process,
# so they multiply by replicas and reset on restart. Turning this on says "I
# know this runs as exactly one process and I accept a per-process ceiling".
AI_ALLOW_UNSHARED_COUNTER = env_flag("AI_ALLOW_UNSHARED_COUNTER", "0")
# Future-proof gate: when true, AI endpoints require a verified email. Kept off
# until a real email provider is wired so existing users are not locked out.
REQUIRE_VERIFIED_FOR_AI = env_flag("REQUIRE_VERIFIED_FOR_AI", "0")

# --- Uploads ---------------------------------------------------------------
# Every budget below is per request and enforced twice: once on the raw ASGI
# body, before the multipart parser can spool it, and once on the parsed part,
# so the route can answer precisely. See app/core/uploads.py.

# Hard cap on resume upload size to prevent memory exhaustion / storage abuse.
MAX_UPLOAD_BYTES = env_int("MAX_UPLOAD_BYTES", 5_000_000, minimum=1)

# Post media is larger than a CV but still bounded: it is copied to disk and
# then pushed to a paid provider, so an unbounded body costs RAM, disk and money.
MAX_POST_UPLOAD_BYTES = env_int("MAX_POST_UPLOAD_BYTES", 10_000_000, minimum=1)

# Everything that is not an upload route. JSON payloads are small; a request
# this large on a non-upload path is a flood, not a user.
MAX_REQUEST_BODY_BYTES = env_int("MAX_REQUEST_BODY_BYTES", 1_000_000, minimum=1)

# A DOCX is a ZIP: a few kilobytes can declare gigabytes of XML. The archive
# being small says nothing about what extracting it costs, so the *expanded*
# size is what has to be bounded.
MAX_DOCX_EXPANDED_BYTES = env_int("MAX_DOCX_EXPANDED_BYTES", 20_000_000, minimum=1)
# A ratio this far above the ~10:1 that real prose achieves is a zip bomb.
MAX_DOCX_COMPRESSION_RATIO = env_int("MAX_DOCX_COMPRESSION_RATIO", 200, minimum=1)

# Media accepted by the post endpoint. Anything outside this is rejected before
# it reaches disk or the provider.
POST_MEDIA_CONTENT_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "video/mp4",
        "video/quicktime",
        "video/webm",
    }
)

# --- Ingress / trusted proxies --------------------------------------------
# Which immediate peers may speak for the real client through X-Forwarded-For.
# Everything that keys on a client IP (request rate limits, AI per-IP limits)
# resolves it through this policy, so the answer to "what is the client IP" has
# exactly one definition.
#
# Accepted values:
#   "private"  (default) - loopback + RFC1918/CGNAT/link-local/ULA peers. A
#                          managed platform (Cloud Run, Fly, ECS, an ingress
#                          controller) always reaches the container from such an
#                          address, while a *direct* hit from the internet
#                          arrives from a public peer and is therefore not
#                          allowed to declare its own IP.
#   "none"/""            - trust nobody; the socket peer is the client.
#   "*"                  - trust any peer. Only correct when the container is
#                          provably unreachable except through the proxy.
#   list                 - comma-separated IPs and/or CIDRs (the tightest
#                          option: the load balancer's own range).
# FORWARDED_ALLOW_IPS is the previous name and is still read, so a deployment
# that already exports it keeps working.
TRUSTED_PROXY_IPS = env_str_any(("TRUSTED_PROXY_IPS", "FORWARDED_ALLOW_IPS"), "private")

# --- Registration abuse controls ------------------------------------------
REGISTER_RATE_LIMIT_MAX = env_int("REGISTER_RATE_LIMIT_MAX", 5, minimum=1)
REGISTER_RATE_LIMIT_WINDOW_SECONDS = env_int("REGISTER_RATE_LIMIT_WINDOW_SECONDS", 3600, minimum=1)
REGISTER_IP_DAILY_ACCOUNT_CAP = env_int("REGISTER_IP_DAILY_ACCOUNT_CAP", 5, minimum=1)

# --- Credential-recovery abuse controls ------------------------------------
# forgot-password / reset-password / request-verify-token send mail and let an
# attacker probe which addresses exist, for both identities (students and
# company recruiters). Low volume by nature, so the cap is tight.
RECOVERY_RATE_LIMIT_MAX = env_int("RECOVERY_RATE_LIMIT_MAX", 5, minimum=1)
RECOVERY_RATE_LIMIT_WINDOW_SECONDS = env_int(
    "RECOVERY_RATE_LIMIT_WINDOW_SECONDS", 3600, minimum=1
)


# --- Asynchronous task dispatch (TASK-054) ---------------------------------
# Plan 08 §6.3: the durable CV-analysis runner must not be a loop inside every
# web replica. A replica scaled to zero runs no loop at all, so queued work
# would simply not happen; N replicas run N loops competing for the same rows.
#
# The web process therefore does **not** start the runner by default. This flag
# exists for the one case where that is still the right answer — a single-process
# deployment with no task queue in front of it — and it is off unless a
# deployment says otherwise, so the default is the safe topology rather than the
# convenient one.
CV_ANALYSIS_INLINE_RUNNER = env_flag("CV_ANALYSIS_INLINE_RUNNER", "0")

# How the outbox delivers a dispatch:
#   "cloud_tasks" - create a Cloud Tasks HTTP task with an OIDC token (prod)
#   "http"        - POST the internal endpoint directly (compose worker, dev)
#   "disabled"    - do not deliver; rows accumulate and are visible
# Default "disabled": a deployment that has not been configured must not
# silently invent a delivery mechanism, and tests must not reach the network.
TASK_DISPATCH_TRANSPORT = env_str("TASK_DISPATCH_TRANSPORT", "disabled").lower()

# Where the task is delivered. For Cloud Tasks this is the *public* URL of the
# API service; for the HTTP transport it is whatever the worker can reach.
INTERNAL_TASKS_BASE_URL = env_str("INTERNAL_TASKS_BASE_URL")

# Cloud Tasks queue, fully qualified:
#   projects/<project>/locations/<region>/queues/<queue>
CLOUD_TASKS_QUEUE = env_str("CLOUD_TASKS_QUEUE")
# The service account Cloud Tasks mints the OIDC token for. The internal
# endpoint accepts tokens from this identity and no other.
CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL = env_str("CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL")
# The audience the token must carry, and the one the endpoint checks. Distinct
# from the base URL so an audience can be pinned even behind a redirect.
INTERNAL_TASKS_AUDIENCE = env_str("INTERNAL_TASKS_AUDIENCE")

# Local/dev alternative to OIDC. A deployment with ENV=production that sets
# only this is refused by the endpoint: a shared secret is not an identity.
INTERNAL_TASKS_SHARED_SECRET = env_str("INTERNAL_TASKS_SHARED_SECRET")

# A dispatch that keeps failing must stop, or it becomes an infinite retry paid
# for by the queue. The row stays FAILED and visible rather than disappearing.
TASK_OUTBOX_MAX_ATTEMPTS = env_int("TASK_OUTBOX_MAX_ATTEMPTS", 8, minimum=1)
# Base for the exponential backoff between delivery attempts, in seconds.
TASK_OUTBOX_RETRY_BASE_SECONDS = env_int("TASK_OUTBOX_RETRY_BASE_SECONDS", 5, minimum=1)
# How long the local worker waits between sweeps of the outbox.
TASK_OUTBOX_POLL_SECONDS = env_int("TASK_OUTBOX_POLL_SECONDS", 5, minimum=1)
