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


ENV = env_str("ENV", "development").lower()
IS_PRODUCTION = ENV in {"production", "prod"}

# --- Shared infra ----------------------------------------------------------
# Empty REDIS_URL keeps a per-process in-memory fallback (fine for dev/tests).
REDIS_URL = env_str("REDIS_URL")

# --- AI quota / budget -----------------------------------------------------
# Base free daily AI requests per user, per feature. Paid plans add units via
# AIQuotaGrantModel on top of this base.
AI_BASE_DAILY_LIMIT = env_int("AI_BASE_DAILY_LIMIT", 3, minimum=0)
# Hard ceiling on total LLM calls/day across ALL users (cost circuit breaker).
AI_GLOBAL_DAILY_BUDGET = env_int("AI_GLOBAL_DAILY_BUDGET", 2000, minimum=1)
# Cross-replica cap on LLM call rate (smooths provider spend / concurrency).
AI_LLM_CALLS_PER_MIN = env_int("AI_LLM_CALLS_PER_MIN", 60, minimum=1)
# Instant manual kill switch: when true, no LLM call is attempted at all.
AI_KILL_SWITCH = env_flag("AI_KILL_SWITCH", "0")
# Future-proof gate: when true, AI endpoints require a verified email. Kept off
# until a real email provider is wired so existing users are not locked out.
REQUIRE_VERIFIED_FOR_AI = env_flag("REQUIRE_VERIFIED_FOR_AI", "0")

# --- Uploads ---------------------------------------------------------------
# Hard cap on resume upload size to prevent memory exhaustion / storage abuse.
MAX_UPLOAD_BYTES = env_int("MAX_UPLOAD_BYTES", 5_000_000, minimum=1)

# --- Registration abuse controls ------------------------------------------
REGISTER_RATE_LIMIT_MAX = env_int("REGISTER_RATE_LIMIT_MAX", 5, minimum=1)
REGISTER_RATE_LIMIT_WINDOW_SECONDS = env_int("REGISTER_RATE_LIMIT_WINDOW_SECONDS", 3600, minimum=1)
REGISTER_IP_DAILY_ACCOUNT_CAP = env_int("REGISTER_IP_DAILY_ACCOUNT_CAP", 5, minimum=1)
