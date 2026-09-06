from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Iterable

from fastapi import Request

from app.config import (
    RECOVERY_RATE_LIMIT_MAX,
    RECOVERY_RATE_LIMIT_WINDOW_SECONDS,
    REGISTER_IP_DAILY_ACCOUNT_CAP,
    REGISTER_RATE_LIMIT_MAX,
    REGISTER_RATE_LIMIT_WINDOW_SECONDS,
    TRUSTED_PROXY_IPS,
    env_int,
    env_str_any,
)
from app.services.ratelimit.counterStore import (
    CounterStore,
    CounterStoreError,
    get_counter_store,
)

_ONE_DAY_SECONDS = 86_400

# Login endpoints for both identities. A shared bucket is deliberate: the cost
# being limited is "credential attempts from this IP", regardless of which of
# the two login forms is being hammered.
LOGIN_PATHS = ("/auth/jwt/login", "/api/v1/auth/company/login")

# Account creation for both identities. Also one shared bucket, because the
# daily cap means "accounts created from this IP", and a company account is an
# account.
REGISTER_PATHS = ("/api/v1/auth/register", "/api/v1/auth/company/register")

# Credential recovery and verification mail, both identities.
RECOVERY_PATHS = (
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/request-verify-token",
    "/api/v1/auth/company/forgot-password",
    "/api/v1/auth/company/reset-password",
    "/api/v1/auth/company/request-verify-token",
)


# What "private" means, spelled out instead of delegating to
# ``ipaddress.is_private``: that property also covers documentation/reserved
# ranges, and this list is a deployment statement ("addresses a load balancer
# can legitimately reach us from"), so it should read as one.
_PRIVATE_NETWORKS = tuple(
    ipaddress.ip_network(cidr)
    for cidr in (
        "127.0.0.0/8",  # loopback (sidecar / same-pod proxy)
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "100.64.0.0/10",  # CGNAT, used by several managed platforms
        "169.254.0.0/16",  # link-local
        "::1/128",
        "fc00::/7",  # unique local
        "fe80::/10",  # link-local
    )
)


@dataclass(frozen=True)
class TrustedProxyPolicy:
    """Who is allowed to speak for the client through ``X-Forwarded-For``.

    Every per-IP limit in the app resolves its key through this policy, so an
    untrusted peer cannot mint a fresh bucket per request by inventing a header.
    Parsing never raises: an unusable token is ignored rather than taking the
    process down at import time.
    """

    trust_all: bool = False
    trust_private: bool = False
    networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = ()

    @classmethod
    def parse(cls, raw: str) -> "TrustedProxyPolicy":
        trust_all = False
        trust_private = False
        networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        for token in (raw or "").split(","):
            token = token.strip().lower()
            if not token or token in {"none", "off", "unix"}:
                continue
            if token == "*":
                trust_all = True
                continue
            if token in {"private", "local"}:
                trust_private = True
                continue
            try:
                networks.append(ipaddress.ip_network(token, strict=False))
            except ValueError:
                # Unparseable entry: ignore it instead of widening trust.
                continue
        return cls(trust_all=trust_all, trust_private=trust_private, networks=tuple(networks))

    @classmethod
    def from_env(cls) -> "TrustedProxyPolicy":
        return _parse_policy(
            env_str_any(("TRUSTED_PROXY_IPS", "FORWARDED_ALLOW_IPS"), TRUSTED_PROXY_IPS)
        )

    def trusts(self, host: str | None) -> bool:
        if self.trust_all:
            return True
        if not host:
            return False
        try:
            ip = ipaddress.ip_address(host.strip())
        except ValueError:
            return False
        if self.trust_private and any(ip in network for network in _PRIVATE_NETWORKS):
            return True
        return any(ip in network for network in self.networks)

    def client_ip(self, request: Request) -> str:
        """Resolve the client IP of ``request`` under this policy.

        The socket peer is the only thing the app can observe directly, so it
        decides whether the forwarded chain may be read at all. When it may, the
        chain is walked right to left — each proxy appends the peer it saw, so
        the rightmost entry that is not itself a trusted proxy is the client;
        anything further left was written by the client and is not evidence.
        """
        peer = request.client.host if request.client else ""
        peer = (peer or "").strip()

        if not self.trusts(peer):
            # Includes "no peer at all" for every policy but ``*``.
            return peer or "unknown"

        forwarded = [
            part.strip()
            for part in request.headers.get("x-forwarded-for", "").split(",")
            if part.strip()
        ]
        for candidate in reversed(forwarded):
            if not self.trusts(candidate):
                return candidate
        # Every hop is trusted (typically ``*``): fall back to what the chain
        # declares, then to the peer.
        if forwarded:
            return forwarded[0]
        return peer or "unknown"


@lru_cache(maxsize=8)
def _parse_policy(raw: str) -> TrustedProxyPolicy:
    return TrustedProxyPolicy.parse(raw)


def resolve_client_ip(request: Request) -> str:
    """Single definition of "the client IP" for every per-IP limit."""
    return TrustedProxyPolicy.from_env().client_ip(request)


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
        # X-Forwarded-For is read only when the immediate peer is a declared
        # proxy (TRUSTED_PROXY_IPS); otherwise the socket peer is the key, so a
        # direct caller cannot hand itself a new bucket per request.
        return resolve_client_ip(request)

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
                exact_paths=LOGIN_PATHS,
            ),
            # Registration burst control: stops scripted account farming (each new
            # account would otherwise unlock free LLM quota).
            RateLimitRule(
                key="auth_register_burst",
                max_requests=REGISTER_RATE_LIMIT_MAX,
                window_seconds=REGISTER_RATE_LIMIT_WINDOW_SECONDS,
                methods=("POST",),
                exact_paths=REGISTER_PATHS,
            ),
            # Daily cap on accounts created per IP (a 1-day sliding window).
            RateLimitRule(
                key="auth_register_daily",
                max_requests=REGISTER_IP_DAILY_ACCOUNT_CAP,
                window_seconds=_ONE_DAY_SECONDS,
                methods=("POST",),
                exact_paths=REGISTER_PATHS,
            ),
            # Password recovery and verification mail for both identities:
            # rationed because each call sends mail and reveals whether an
            # address exists.
            RateLimitRule(
                key="auth_recovery",
                max_requests=RECOVERY_RATE_LIMIT_MAX,
                window_seconds=RECOVERY_RATE_LIMIT_WINDOW_SECONDS,
                methods=("POST",),
                exact_paths=RECOVERY_PATHS,
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
