"""Global LLM cost circuit breaker, counted in **provider attempts**.

Three units are deliberately kept apart (see ``app/config.py``):

* **user units** — what one person may spend per day. Enforced elsewhere, by
  ``AIUsageService``;
* **provider attempts** — every single request handed to Gemini, *retries
  included*. That is what this guard counts;
* **money** — real provider spend. Nothing here measures money. An attempt
  count is only a proxy for it, so the ceilings are named after attempts and
  never called a budget in currency terms.

One user unit can cost several attempts (an evaluator retries), which is why
the ceiling has to be applied immediately before each individual attempt
rather than once per user request.

Two cross-replica ceilings:

* a **daily attempt ceiling** — total provider attempts/day across ALL users;
* an **attempt-rate** cap — attempts per minute, smoothing concurrency/cost.

Plus a manual ``AI_KILL_SWITCH`` that disables LLM calls instantly.

Counters live in the shared :class:`CounterStore`. This guard **fails closed**
in every degraded mode: if the store is unreachable, or if it is not shared
while running in production, we would rather show "Manual mode" than let a
ceiling silently become per-process — a per-process ceiling multiplies by the
number of replicas and resets on every restart, which is no ceiling at all.
"""
from __future__ import annotations

import logging
from datetime import datetime

from app.services.ratelimit.counterStore import CounterStoreError, get_counter_store

LOGGER = logging.getLogger(__name__)

# Marker words ("quota"/"limit") are intentional: downstream
# friendly_analysis_error_message maps them to the user-facing "Manual mode"
# message without any extra wiring.
_BUDGET_MESSAGE = "AI is temporarily over its global quota/limit. Please use Manual mode."

_ATTEMPTS_TTL_SECONDS = 36 * 3600
_RATE_WINDOW_SECONDS = 60


class AIBudgetExhausted(RuntimeError):
    """Raised when a global ceiling (kill switch, attempts or rate) is hit."""

    def __init__(self, message: str = _BUDGET_MESSAGE) -> None:
        super().__init__(message)


def _global_attempts_key() -> str:
    day = datetime.utcnow().strftime("%Y%m%d")
    # Key name kept from the previous revision on purpose: renaming it would
    # silently reset the live ceiling to zero on the deploy that ships this.
    return f"ai:budget:global:{day}"


def is_kill_switch_enabled() -> bool:
    # Read fresh from config module so it reflects the current process env.
    from app import config

    return config.AI_KILL_SWITCH


def _require_shared_store(store) -> None:
    """Refuse to authorize spend on a per-process counter in production."""
    from app import config

    if store.is_shared or not config.IS_PRODUCTION:
        return
    if config.AI_ALLOW_UNSHARED_COUNTER:
        # Explicitly accepted single-process deployment.
        return
    LOGGER.error(
        "No shared counter store in production (REDIS_URL missing or Redis init "
        "failed); refusing LLM attempts instead of spending against a "
        "per-process ceiling. Set REDIS_URL, or AI_ALLOW_UNSHARED_COUNTER=1 if "
        "this really is a single process."
    )
    raise AIBudgetExhausted()


async def ensure_llm_attempt_allowed(*, attempts: int = 1) -> None:
    """Gate to call immediately before **each** provider attempt.

    ``attempts`` is a number of provider requests, never an amount of money and
    never a user's daily allowance. Raises :class:`AIBudgetExhausted` when a
    global ceiling is reached or when the ceiling cannot be trusted.
    """
    # Read fresh from the config module so tests and a restarted process see
    # the current values rather than import-time snapshots.
    from app import config

    if is_kill_switch_enabled():
        LOGGER.warning("AI kill switch is enabled; refusing LLM call.")
        raise AIBudgetExhausted()

    store = get_counter_store()
    _require_shared_store(store)

    # Per-minute attempt-rate ceiling (cross-replica smoothing).
    try:
        allowed, _ = await store.sliding_window_allow(
            "ai:llm:rate",
            max_requests=config.AI_LLM_ATTEMPTS_PER_MIN,
            window_seconds=_RATE_WINDOW_SECONDS,
        )
    except CounterStoreError:
        LOGGER.error("Attempt counter unavailable on rate check; failing closed.")
        raise AIBudgetExhausted()
    if not allowed:
        LOGGER.warning("Global LLM attempt-rate ceiling reached.")
        raise AIBudgetExhausted()

    # Daily global attempt ceiling.
    try:
        new_total = await store.incr(
            _global_attempts_key(), ttl_seconds=_ATTEMPTS_TTL_SECONDS, amount=attempts
        )
    except CounterStoreError:
        LOGGER.error("Attempt counter unavailable on daily check; failing closed.")
        raise AIBudgetExhausted()
    if new_total > config.AI_GLOBAL_DAILY_ATTEMPTS:
        LOGGER.error(
            "Global daily AI attempt ceiling exhausted: %s/%s",
            new_total,
            config.AI_GLOBAL_DAILY_ATTEMPTS,
        )
        raise AIBudgetExhausted()
