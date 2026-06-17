import pytest
from fastapi import HTTPException

from app.services.aiRequestRateLimitService import AI_ANALYSIS_RATE_LIMIT_MESSAGE, AIRequestRateLimitService


def test_ai_request_rate_limiter_blocks_after_limit():
    limiter = AIRequestRateLimitService(max_requests=2, window_seconds=60)

    limiter.check_ip("127.0.0.1")
    limiter.check_ip("127.0.0.1")

    with pytest.raises(HTTPException) as exc_info:
        limiter.check_ip("127.0.0.1")

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == AI_ANALYSIS_RATE_LIMIT_MESSAGE


def test_ai_request_rate_limiter_tracks_ips_independently():
    limiter = AIRequestRateLimitService(max_requests=1, window_seconds=60)

    limiter.check_ip("127.0.0.1")
    limiter.check_ip("10.0.0.2")

    with pytest.raises(HTTPException):
        limiter.check_ip("127.0.0.1")
