"""TASK-010 — company authentication coverage and trusted-proxy resolution.

Two defects are covered here:

* the request limiter only knew the *student* login/registration paths, so
  ``/api/v1/auth/company/login`` and company registration were unlimited;
* the client IP was whatever ``X-Forwarded-For`` said whenever uvicorn was told
  to trust every peer (``FORWARDED_ALLOW_IPS=*``), so a caller that can reach
  the container directly got a fresh limiter bucket per request.
"""
from __future__ import annotations

import uuid
from typing import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.csrf_client import CSRFAsyncClient
from starlette.requests import Request

from app.app import app, rate_limiter
from app.db import get_session
from app.middleware.rate_limit import (
    RequestRateLimiter,
    TrustedProxyPolicy,
    resolve_client_ip,
)
from app.models.companyRecruiterModel import CompanyRecruiter
from app.services.ratelimit.counterStore import reset_counter_store
from tests.conftest import TestSessionLocal

# Defaults from app.config; the tests assert against the shipped configuration.
LOGIN_MAX = 8
REGISTER_BURST_MAX = 5
RECOVERY_MAX = 5

PUBLIC_PEER = "203.0.113.9"  # TEST-NET-3: a caller reaching the app directly.
PRIVATE_PEER = "10.0.0.5"  # What a managed load balancer looks like inside.


def make_request(peer: str | None, forwarded: str | None = None) -> Request:
    headers = [(b"host", b"test")]
    if forwarded is not None:
        headers.append((b"x-forwarded-for", forwarded.encode()))
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/api/v1/auth/company/login",
        "raw_path": b"/api/v1/auth/company/login",
        "query_string": b"",
        "scheme": "http",
        "server": ("test", 80),
        "headers": headers,
        "client": (peer, 41234) if peer else None,
    }
    return Request(scope)


class TestTrustedProxyPolicy:
    """`X-Forwarded-For` is evidence only when the peer that wrote it is one of
    ours; otherwise the socket peer is the only thing the app can believe."""

    def test_untrusted_peer_cannot_declare_its_own_ip(self):
        policy = TrustedProxyPolicy.parse("private")

        resolved = policy.client_ip(make_request(PUBLIC_PEER, "1.1.1.1"))

        assert resolved == PUBLIC_PEER

    def test_trusted_proxy_yields_the_client_it_saw(self):
        policy = TrustedProxyPolicy.parse("private")

        # Chain written by the edge: "<client>, <hop>"; the rightmost hop is a
        # trusted proxy, so the client is the entry before it.
        resolved = policy.client_ip(make_request(PRIVATE_PEER, "198.51.100.7, 10.0.0.9"))

        assert resolved == "198.51.100.7"

    def test_client_supplied_prefix_is_ignored_behind_a_trusted_proxy(self):
        policy = TrustedProxyPolicy.parse("private")

        # The caller sent "1.2.3.4" itself; the proxy appended what it actually
        # saw. Only the appended value is evidence.
        resolved = policy.client_ip(make_request(PRIVATE_PEER, "1.2.3.4, 203.0.113.9"))

        assert resolved == "203.0.113.9"

    def test_explicit_cidr_does_not_imply_private_ranges(self):
        policy = TrustedProxyPolicy.parse("192.0.2.0/24, 198.51.100.4")

        assert policy.trusts("192.0.2.77")
        assert policy.trusts("198.51.100.4")
        assert not policy.trusts(PRIVATE_PEER)
        assert not policy.trusts(PUBLIC_PEER)
        assert policy.client_ip(make_request(PRIVATE_PEER, "1.1.1.1")) == PRIVATE_PEER
        assert policy.client_ip(make_request("192.0.2.77", "1.1.1.1")) == "1.1.1.1"

    def test_trust_all_keeps_the_previous_forwarded_allow_ips_behaviour(self):
        policy = TrustedProxyPolicy.parse("*")

        assert policy.client_ip(make_request(PUBLIC_PEER, "1.1.1.1, 2.2.2.2")) == "1.1.1.1"
        assert policy.client_ip(make_request(PUBLIC_PEER)) == PUBLIC_PEER

    def test_none_trusts_nobody(self):
        policy = TrustedProxyPolicy.parse("none")

        assert policy.client_ip(make_request(PRIVATE_PEER, "1.1.1.1")) == PRIVATE_PEER

    def test_unparseable_entries_never_widen_trust(self):
        policy = TrustedProxyPolicy.parse("not-an-ip, , 300.1.1.1")

        assert policy == TrustedProxyPolicy()
        assert not policy.trusts(PRIVATE_PEER)

    def test_missing_peer_is_not_a_free_identity(self):
        assert TrustedProxyPolicy.parse("private").client_ip(make_request(None, "1.1.1.1")) == "unknown"

    def test_env_selects_the_policy_and_honours_the_legacy_name(self, monkeypatch):
        monkeypatch.delenv("TRUSTED_PROXY_IPS", raising=False)
        monkeypatch.setenv("FORWARDED_ALLOW_IPS", "*")
        assert resolve_client_ip(make_request(PUBLIC_PEER, "1.1.1.1")) == "1.1.1.1"

        monkeypatch.setenv("TRUSTED_PROXY_IPS", "private")
        assert resolve_client_ip(make_request(PUBLIC_PEER, "1.1.1.1")) == PUBLIC_PEER

    def test_limiter_uses_the_shared_resolution(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXY_IPS", "private")

        assert RequestRateLimiter._client_ip(make_request(PUBLIC_PEER, "1.1.1.1")) == PUBLIC_PEER


@pytest_asyncio.fixture
async def public_peer_client(setup_db) -> AsyncIterator[AsyncClient]:
    """A client whose socket peer is a public address, i.e. someone reaching the
    container directly instead of through the load balancer."""

    async def override_get_session():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    rate_limiter._events.clear()
    await reset_counter_store()

    async with CSRFAsyncClient(
        transport=ASGITransport(app=app, client=(PUBLIC_PEER, 41234)),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


async def _company_login(client: AsyncClient, **kwargs):
    return await client.post(
        "/api/v1/auth/company/login",
        data={"username": "nobody@example.com", "password": "WrongPass123!"},
        **kwargs,
    )


def _company_payload(index: int) -> dict:
    return {
        "company_name": f"Company {index}",
        "email": f"farm{index}-{uuid.uuid4().hex[:8]}@example.com",
        "password": "StrongPass123!",
        "contact_person": "Ada Lovelace",
    }


class TestCompanyAuthIsCovered:
    @pytest.mark.asyncio
    async def test_company_login_is_rate_limited(self, client: AsyncClient):
        statuses = [(await _company_login(client)).status_code for _ in range(LOGIN_MAX + 1)]

        assert statuses[-1] == 429
        assert statuses.count(429) == 1  # only the attempt past the limit

    @pytest.mark.asyncio
    async def test_login_limit_is_shared_by_both_identities(self, client: AsyncClient):
        for _ in range(LOGIN_MAX):
            response = await client.post(
                "/auth/jwt/login",
                data={"username": "nobody@example.com", "password": "WrongPass123!"},
            )
            assert response.status_code != 429

        # Credential stuffing cannot switch to the other login form for a fresh
        # allowance: the bucket is "attempts from this IP".
        assert (await _company_login(client)).status_code == 429

    @pytest.mark.asyncio
    async def test_legitimate_company_login_keeps_its_contract(
        self, client: AsyncClient, test_company_recruiter: CompanyRecruiter
    ):
        response = await client.post(
            "/api/v1/auth/company/login",
            data={"username": test_company_recruiter.email, "password": "password123"},
        )

        assert response.status_code in (200, 204)
        assert any(cookie for cookie in client.cookies.jar)

    @pytest.mark.asyncio
    async def test_company_registration_is_rate_limited(self, client: AsyncClient):
        statuses = []
        for i in range(REGISTER_BURST_MAX + 1):
            response = await client.post("/api/v1/auth/company/register", json=_company_payload(i))
            statuses.append(response.status_code)

        assert statuses[:REGISTER_BURST_MAX] == [201] * REGISTER_BURST_MAX
        assert statuses[-1] == 429

    @pytest.mark.asyncio
    async def test_company_registration_counts_against_the_per_ip_account_cap(
        self, client: AsyncClient
    ):
        for i in range(REGISTER_BURST_MAX):
            response = await client.post(
                "/api/v1/auth/register",
                json={"email": f"student{i}@example.com", "password": "StrongPass123!"},
            )
            assert response.status_code != 429

        # Account farming cannot continue by creating company accounts instead.
        response = await client.post("/api/v1/auth/company/register", json=_company_payload(99))
        assert response.status_code == 429

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/company/forgot-password",
            "/api/v1/auth/company/request-verify-token",
        ],
    )
    async def test_recovery_endpoints_are_rate_limited(self, client: AsyncClient, path: str):
        statuses = []
        for _ in range(RECOVERY_MAX + 1):
            response = await client.post(path, json={"email": "someone@example.com"})
            statuses.append(response.status_code)

        assert statuses[:RECOVERY_MAX] == [202] * RECOVERY_MAX
        assert statuses[-1] == 429

    @pytest.mark.asyncio
    async def test_recovery_limit_is_shared_across_both_identities(self, client: AsyncClient):
        for _ in range(RECOVERY_MAX):
            response = await client.post(
                "/api/v1/auth/forgot-password", json={"email": "someone@example.com"}
            )
            assert response.status_code != 429

        response = await client.post(
            "/api/v1/auth/company/forgot-password", json={"email": "someone@example.com"}
        )
        assert response.status_code == 429


class TestForwardedHeaderCannotBypassTheLimiter:
    @pytest.mark.asyncio
    async def test_direct_caller_cannot_mint_a_bucket_per_request(
        self, public_peer_client: AsyncClient, monkeypatch
    ):
        monkeypatch.setenv("TRUSTED_PROXY_IPS", "private")

        statuses = []
        for i in range(LOGIN_MAX + 1):
            response = await _company_login(
                public_peer_client, headers={"X-Forwarded-For": f"198.51.100.{i}"}
            )
            statuses.append(response.status_code)

        assert statuses[-1] == 429

    @pytest.mark.asyncio
    async def test_trusted_peer_still_separates_real_clients(
        self, client: AsyncClient, monkeypatch
    ):
        # Control for the test above: the conftest client's peer is loopback, so
        # it *is* a trusted proxy and the header is honoured. Otherwise every
        # user behind the load balancer would share one bucket.
        monkeypatch.setenv("TRUSTED_PROXY_IPS", "private")

        for i in range(LOGIN_MAX + 1):
            response = await _company_login(client, headers={"X-Forwarded-For": f"198.51.100.{i}"})
            assert response.status_code != 429
