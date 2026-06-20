from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from fastapi import Request

from app.config import (
    REGISTER_IP_DAILY_ACCOUNT_CAP,
    REGISTER_RATE_LIMIT_MAX,
    REGISTER_RATE_LIMIT_WINDOW_SECONDS,
    env_int,
)
from app.services.ratelimit.counterStore import (
    CounterStore,
    CounterStoreError,
    get_counter_store,
)

_ONE_DAY_SECONDS = 86_400


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


class RequestRateLimiter:
    """IP-based request rate limiter backed by the shared counter store.

    When ``REDIS_URL`` is configured the sliding windows are shared across every
    replica/worker, so the limits hold under horizontal scaling. The limiter
    *fails open*: a Redis outage must never take the whole site down — the
    per-user AI quota and the global budget guard remain the hard cost ceilings.
    """

    def __init__(
        self,
        rules: Iterable[RateLimitRule],
        *,
        store_factory: Callable[[], CounterStore] = get_counter_store,
    ):
        self.rules = tuple(rules)
        self._store_factory = store_factory
        # Retained so existing test fixtures that call ``_events.clear()`` keep
        # working; real state lives in the shared counter store.
        self._events: dict[str, object] = {}

    @staticmethod
    def _client_ip(request: Request) -> str:
        # Trust the client address resolved by uvicorn. With
        # ``--proxy-headers --forwarded-allow-ips`` configured, uvicorn rewrites
        # this from X-Forwarded-For only when the immediate peer is trusted, so
        # we do not blindly trust a spoofable raw header here.
        if request.client and request.client.host:
            return request.client.host
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        return forwarded or "unknown"

    async def check(self, request: Request) -> tuple[bool, int]:
        path = request.url.path
        method = request.method.upper()
        ip = self._client_ip(request)
        store = self._store_factory()

        for rule in self.rules:
            if not rule.matches(path=path, method=method):
                continue
            try:
                allowed, retry_after = await store.sliding_window_allow(
                    f"rl:{rule.key}:{ip}",
                    max_requests=rule.max_requests,
                    window_seconds=rule.window_seconds,
                )
            except CounterStoreError:
                # Fail open on infrastructure errors.
                continue
            if not allowed:
                return False, retry_after

        return True, 0

    @classmethod
    def from_env(cls) -> "RequestRateLimiter":
        rules = (
            RateLimitRule(
                key="auth_login",
                max_requests=env_int("AUTH_LOGIN_RATE_LIMIT_MAX", 8, minimum=1),
                window_seconds=env_int("AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS", 60, minimum=1),
                methods=("POST",),
                exact_paths=("/auth/jwt/login",),
            ),
            # Registration burst control: stops scripted account farming (each new
            # account would otherwise unlock free LLM quota).
            RateLimitRule(
                key="auth_register_burst",
                max_requests=REGISTER_RATE_LIMIT_MAX,
                window_seconds=REGISTER_RATE_LIMIT_WINDOW_SECONDS,
                methods=("POST",),
                exact_paths=("/api/v1/auth/register",),
            ),
            # Daily cap on accounts created per IP (a 1-day sliding window).
            RateLimitRule(
                key="auth_register_daily",
                max_requests=REGISTER_IP_DAILY_ACCOUNT_CAP,
                window_seconds=_ONE_DAY_SECONDS,
                methods=("POST",),
                exact_paths=("/api/v1/auth/register",),
            ),
            RateLimitRule(
                key="admin_api",
                max_requests=env_int("ADMIN_API_RATE_LIMIT_MAX", 120, minimum=1),
                window_seconds=env_int("ADMIN_API_RATE_LIMIT_WINDOW_SECONDS", 60, minimum=1),
                methods=("GET", "POST", "PUT", "PATCH", "DELETE"),
                path_prefixes=("/api/v1/admin",),
            ),
            RateLimitRule(
                key="admin_pages",
                max_requests=env_int("ADMIN_PAGE_RATE_LIMIT_MAX", 60, minimum=1),
                window_seconds=env_int("ADMIN_PAGE_RATE_LIMIT_WINDOW_SECONDS", 60, minimum=1),
                methods=("GET",),
                exact_paths=("/admin", "/admin/"),
                path_prefixes=("/admin/login",),
            ),
        )
        return cls(rules=rules)
