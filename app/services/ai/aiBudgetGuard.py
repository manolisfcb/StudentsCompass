"""Global LLM cost circuit breaker.

Two cross-replica ceilings protect against runaway spend regardless of how many
users (or how much abuse) hit the AI endpoints:

* a **daily budget** — total LLM calls/day across ALL users; and
* a **call-rate** cap — LLM calls per minute, smoothing concurrency/cost.

Plus a manual ``AI_KILL_SWITCH`` that disables LLM calls instantly. Counters
live in the shared :class:`CounterStore` (Redis in prod). This guard **fails
closed**: if the store is unreachable we'd rather show "Manual mode" than risk
an unbounded bill.
"""
from __future__ import annotations

import logging
from datetime import datetime

from app.config import AI_GLOBAL_DAILY_BUDGET, AI_LLM_CALLS_PER_MIN
from app.services.ratelimit.counterStore import CounterStoreError, get_counter_store

LOGGER = logging.getLogger(__name__)

# Marker words ("quota"/"limit") are intentional: downstream
# friendly_analysis_error_message maps them to the user-facing "Manual mode"
# message without any extra wiring.
_BUDGET_MESSAGE = "AI is temporarily over its global quota/limit. Please use Manual mode."

_BUDGET_TTL_SECONDS = 36 * 3600
_RATE_WINDOW_SECONDS = 60


class AIBudgetExhausted(RuntimeError):
    """Raised when a global ceiling (kill switch, budget or rate) is hit."""

    def __init__(self, message: str = _BUDGET_MESSAGE) -> None:
        super().__init__(message)


def _global_budget_key() -> str:
    day = datetime.utcnow().strftime("%Y%m%d")
    return f"ai:budget:global:{day}"


def is_kill_switch_enabled() -> bool:
    # Read fresh from config module so it reflects the current process env.
    from app import config

    return config.AI_KILL_SWITCH


async def ensure_llm_budget(*, units: int = 1) -> None:
    """Gate to call immediately before any LLM request. Raises
    :class:`AIBudgetExhausted` when a global ceiling is reached."""
    if is_kill_switch_enabled():
        LOGGER.warning("AI kill switch is enabled; refusing LLM call.")
        raise AIBudgetExhausted()

    store = get_counter_store()

    # Per-minute call-rate ceiling (cross-replica smoothing).
    try:
        allowed, _ = await store.sliding_window_allow(
            "ai:llm:rate",
            max_requests=AI_LLM_CALLS_PER_MIN,
            window_seconds=_RATE_WINDOW_SECONDS,
        )
    except CounterStoreError:
        LOGGER.error("Budget store unavailable on rate check; failing closed.")
        raise AIBudgetExhausted()
    if not allowed:
        LOGGER.warning("Global LLM call-rate ceiling reached.")
        raise AIBudgetExhausted()

    # Daily global budget ceiling.
    try:
        new_total = await store.incr(_global_budget_key(), ttl_seconds=_BUDGET_TTL_SECONDS, amount=units)
    except CounterStoreError:
        LOGGER.error("Budget store unavailable on budget check; failing closed.")
        raise AIBudgetExhausted()
    if new_total > AI_GLOBAL_DAILY_BUDGET:
        LOGGER.error(
            "Global daily AI budget exhausted: %s/%s", new_total, AI_GLOBAL_DAILY_BUDGET
        )
        raise AIBudgetExhausted()
