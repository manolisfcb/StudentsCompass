"""Process-level isolation for the test suite.

Imported (and applied) by ``tests/conftest.py`` before any ``app.*`` module is
imported, because ``app.db`` and ``app.app`` call ``load_dotenv()`` at import
time and ``app.db`` builds the engine from ``DATABASE_URL`` at import time.

Three guarantees:

1. ``.env`` is never read, so a developer's real credentials never enter the
   test process.
2. Every credential-shaped setting has an explicit fake value, so a test that
   forgets to patch a provider fails loudly instead of talking to production.
3. Outbound sockets are blocked. Only loopback (and the disposable services the
   integration lane is pointed at) may be dialled.
"""
from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlsplit

__all__ = [
    "ExternalConnectionBlocked",
    "allow_test_service",
    "apply_isolation",
    "assert_local_url",
]


class ExternalConnectionBlocked(RuntimeError):
    """Raised when test code tries to open a non-loopback socket."""


# Credentials are deliberately obvious placeholders: if one ever shows up in a
# request or a log, its origin is unambiguous.
_FAKE_ENV = {
    "ENV": "test",
    "DATABASE_URL": "postgresql+asyncpg://test:test@127.0.0.1:5432/studentscompass_test",
    "DB_DISABLE_POOL": "1",
    "SECRET_KEY": "test-secret-key-not-a-real-secret",
    "GENAI_API_KEY": "test-genai-key-not-a-real-secret",
    "IMAGEKIT_PUBLIC_KEY": "test-imagekit-public",
    "IMAGEKIT_PRIVATE_KEY": "test-imagekit-private",
    "IMAGEKIT_URL_ENDPOINT": "https://imagekit.invalid/test",
    "AWS_ACCESS_KEY_ID": "test-aws-access-key-id",
    "AWS_SECRET_ACCESS_KEY": "test-aws-secret-access-key",
    "AWS_REGION": "us-east-1",
    "BUCKET_NAME": "test-bucket",
    "RESOURCES_BUCKET_NAME": "test-resources-bucket",
    "HF_TOKEN": "test-hf-token",
    "HUGGINGFACE_HUB_TOKEN": "test-hf-token",
    "APIFY_API_TOKEN": "test-apify-token",
    # Offline-only defaults for libraries that phone home on import/first use.
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    # Empty REDIS_URL keeps the in-memory counter store; the Redis lane sets
    # TEST_REDIS_URL instead so the fast lane stays hermetic.
    "REDIS_URL": "",
}

# Loopback is always reachable: SQLite, and the disposable services the
# integration lane starts. Extra hosts are opted into explicitly.
_allowed_hosts: set[str] = {"localhost", "127.0.0.1", "::1", ""}

_real_create_connection = socket.create_connection
_real_socket_connect = socket.socket.connect
_real_socket_connect_ex = socket.socket.connect_ex


def _host_is_local(host: str | None) -> bool:
    if host is None:
        return True
    host = host.strip("[]").lower()
    if host in _allowed_hosts:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _check_address(address) -> None:
    if not isinstance(address, tuple) or not address:
        # AF_UNIX and friends never leave the machine.
        return
    host = address[0]
    if not _host_is_local(host if isinstance(host, str) else None):
        raise ExternalConnectionBlocked(
            f"Blocked outbound connection to {address!r}. Tests must not reach "
            "external services; use a fake/stub, or allow a disposable test "
            "service with tests.isolation.allow_test_service()."
        )


def allow_test_service(url_or_host: str) -> None:
    """Whitelist a disposable service the integration lane is pointed at."""
    host = urlsplit(url_or_host).hostname if "//" in url_or_host else url_or_host
    if host:
        _allowed_hosts.add(host.strip("[]").lower())


def assert_local_url(url: str, *, setting: str) -> str:
    """Reject a test service URL that does not point at a disposable target.

    Guards the integration lane against being aimed at a real deployment by a
    stale environment variable.
    """
    host = urlsplit(url).hostname
    if not _host_is_local(host):
        raise ExternalConnectionBlocked(
            f"{setting} points at non-local host {host!r}. The test lane only "
            "runs against a disposable local service."
        )
    return url


def _install_socket_guard() -> None:
    def guarded_create_connection(address, *args, **kwargs):
        _check_address(address)
        return _real_create_connection(address, *args, **kwargs)

    def guarded_connect(self, address):
        _check_address(address)
        return _real_socket_connect(self, address)

    def guarded_connect_ex(self, address):
        _check_address(address)
        return _real_socket_connect_ex(self, address)

    socket.create_connection = guarded_create_connection
    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex


def _disable_dotenv() -> None:
    """Neutralise ``load_dotenv`` before app modules call it at import time."""
    import dotenv
    import dotenv.main

    def _no_dotenv(*args, **kwargs) -> bool:
        return False

    dotenv.load_dotenv = _no_dotenv
    dotenv.main.load_dotenv = _no_dotenv
    dotenv.find_dotenv = lambda *args, **kwargs: ""
    dotenv.main.find_dotenv = lambda *args, **kwargs: ""


def apply_isolation() -> None:
    _disable_dotenv()
    # setdefault: an explicitly exported value (a CI lane, a debugging run)
    # still wins, but nothing is inherited from .env.
    for key, value in _FAKE_ENV.items():
        os.environ.setdefault(key, value)
    for url_setting in ("TEST_DATABASE_URL_PG", "TEST_REDIS_URL"):
        url = os.environ.get(url_setting, "").strip()
        if url:
            allow_test_service(assert_local_url(url, setting=url_setting))
    _install_socket_guard()
