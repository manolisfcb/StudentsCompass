"""Shared classification of LLM provider errors.

Retrying a quota/billing/auth failure just multiplies cost and latency without
any chance of success, so those are treated as non-retryable.
"""
from __future__ import annotations

# Substrings (lowercased) that indicate retrying would not help — and would
# only burn more provider quota/credits.
_NON_RETRYABLE_MARKERS = (
    "quota",
    "credit",
    "resource_exhausted",
    "insufficient",
    "billing",
    "rate limit",
    "429",
    "permission",
    "api key",
    "api_key",
    "unauthenticated",
    "unauthorized",
)


def is_non_retryable_llm_error(error: Exception | None) -> bool:
    raw = str(error or "").lower()
    return any(marker in raw for marker in _NON_RETRYABLE_MARKERS)
