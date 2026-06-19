from __future__ import annotations

from collections import deque
from time import monotonic

from fastapi import HTTPException, Request

AI_ANALYSIS_RATE_LIMIT_PER_MINUTE = 5
AI_ANALYSIS_RATE_LIMIT_WINDOW_SECONDS = 60
AI_ANALYSIS_RATE_LIMIT_MESSAGE = "Too many analysis requests right now. Please wait a minute and try again."


class AIRequestRateLimitService:
    def __init__(
        self,
        *,
        max_requests: int = AI_ANALYSIS_RATE_LIMIT_PER_MINUTE,
        window_seconds: int = AI_ANALYSIS_RATE_LIMIT_WINDOW_SECONDS,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = {}

    @staticmethod
    def get_client_ip(request: Request) -> str:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def check_ip(self, ip: str) -> None:
        now = monotonic()
        timestamps = self._events.get(ip)
        if timestamps is None:
            timestamps = deque()
            self._events[ip] = timestamps

        while timestamps and now - timestamps[0] > self.window_seconds:
            timestamps.popleft()

        if len(timestamps) >= self.max_requests:
            raise HTTPException(status_code=429, detail=AI_ANALYSIS_RATE_LIMIT_MESSAGE)

        timestamps.append(now)

    def check_request(self, request: Request) -> None:
        self.check_ip(self.get_client_ip(request))


ai_analysis_rate_limiter = AIRequestRateLimitService()
