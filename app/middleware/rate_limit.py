from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import os
import time
from typing import Iterable

from fastapi import Request


@dataclass(frozen=True)
class RateLimitRule:
    key: str
    max_requests: int
    window_seconds: int
    methods: tuple[str, ...]
    exact_paths: tuple[str, ...] = ()
    path_prefixes: tuple[str, ...] = ()

    def matches(self, *, path: str, method: str) -> bool:
        if self.methods and method.upper() not in self.methods:
            return False
        if self.exact_paths and path in self.exact_paths:
            return True
        if self.path_prefixes and any(path.startswith(prefix) for prefix in self.path_prefixes):
            return True
        return False


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    value = os.getenv(name, str(default)).strip()
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed >= minimum else default


class RequestRateLimiter:
    def __init__(self, rules: Iterable[RateLimitRule]):
        self.rules = tuple(rules)
        self._events: dict[str, deque[float]] = defaultdict(deque)

    @staticmethod
    def _client_ip(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    def _allow(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        now = time.time()
        events = self._events[key]
        cutoff = now - window_seconds
        while events and events[0] <= cutoff:
            events.popleft()

        if len(events) >= max_requests:
            retry_after = max(1, int(window_seconds - (now - events[0])))
            return False, retry_after

        events.append(now)
        return True, 0

    def check(self, request: Request) -> tuple[bool, int]:
        path = request.url.path
        method = request.method.upper()
        ip = self._client_ip(request)

        for rule in self.rules:
            if not rule.matches(path=path, method=method):
                continue
            allowed, retry_after = self._allow(
                key=f"{rule.key}:{ip}",
                max_requests=rule.max_requests,
                window_seconds=rule.window_seconds,
            )
            if not allowed:
                return False, retry_after

        return True, 0

    @classmethod
    def from_env(cls) -> "RequestRateLimiter":
        rules = (
            RateLimitRule(
                key="auth_login",
                max_requests=_int_env("AUTH_LOGIN_RATE_LIMIT_MAX", 8),
                window_seconds=_int_env("AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS", 60),
                methods=("POST",),
                exact_paths=("/auth/jwt/login",),
            ),
            RateLimitRule(
                key="admin_api",
                max_requests=_int_env("ADMIN_API_RATE_LIMIT_MAX", 120),
                window_seconds=_int_env("ADMIN_API_RATE_LIMIT_WINDOW_SECONDS", 60),
                methods=("GET", "POST", "PUT", "PATCH", "DELETE"),
                path_prefixes=("/api/v1/admin",),
            ),
            RateLimitRule(
                key="admin_pages",
                max_requests=_int_env("ADMIN_PAGE_RATE_LIMIT_MAX", 60),
                window_seconds=_int_env("ADMIN_PAGE_RATE_LIMIT_WINDOW_SECONDS", 60),
                methods=("GET",),
                exact_paths=("/admin", "/admin/"),
                path_prefixes=("/admin/login",),
            ),
        )
        return cls(rules=rules)

