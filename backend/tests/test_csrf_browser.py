"""Browser lane for the CSRF shim (TASK-042).

The middleware is proven in ``test_auth_session_csrf.py``. What that cannot
prove is the other half of a double submit: that the *page* actually copies the
cookie into the header. The shim wraps ``fetch``, reads ``document.cookie`` and
decides on the request's origin - three things a Python client does not have -
so it is checked in a real browser, running the real file, against a real
cookie on a real origin.

Skipped when Playwright or its browser is not installed:

    uv pip install playwright && .venv/bin/python -m playwright install chromium
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.browser

STATIC_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "js"

PAGE_ORIGIN = "http://compass.test"
FOREIGN_ORIGIN = "http://attacker.test"
COOKIE_NAME = "studentscompass_csrf"
TOKEN = "token-issued-by-the-server"


@pytest.fixture(scope="module")
def browser():
    playwright = pytest.importorskip(
        "playwright.sync_api", reason="playwright is not installed"
    )
    try:
        with playwright.sync_playwright() as p:
            try:
                instance = p.chromium.launch()
            except Exception as exc:  # noqa: BLE001
                pytest.skip(f"chromium is not available: {exc}")
            try:
                yield instance
            finally:
                instance.close()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"playwright could not start: {exc}")


@pytest.fixture
def page(browser):
    """A page on a real origin, holding the CSRF cookie, with no network access.

    Every request is fulfilled locally and recorded, so the assertions can read
    the headers the page actually sent and nothing leaves the machine.
    """
    context = browser.new_context()
    context.add_cookies(
        [{"name": COOKIE_NAME, "value": TOKEN, "url": PAGE_ORIGIN}]
    )
    page = context.new_page()
    page.set_default_timeout(5000)

    sent: list[dict] = []

    def handle(route, request):
        sent.append({"url": request.url, "method": request.method, "headers": request.headers})
        route.fulfill(status=200, content_type="application/json", body="{}")

    page.route("**/*", handle)
    page.goto(f"{PAGE_ORIGIN}/dashboard")
    page.add_script_tag(content=(STATIC_JS / "csrf.js").read_text())

    page.sent = sent  # type: ignore[attr-defined]
    try:
        yield page
    finally:
        context.close()


def _last(page, url_fragment: str) -> dict:
    matches = [entry for entry in page.sent if url_fragment in entry["url"]]
    assert matches, f"no request to {url_fragment} reached the router"
    return matches[-1]


def test_a_same_origin_mutation_carries_the_token(page):
    page.evaluate("fetch('/api/v1/profile', {method: 'POST', body: '{}'})")
    page.wait_for_function("() => true")

    assert _last(page, "/api/v1/profile")["headers"].get("x-csrf-token") == TOKEN


def test_a_cross_origin_request_does_not_leak_the_token(page):
    """The token is an authorization secret for this origin only.

    Attaching it to a third-party request would hand the other host exactly the
    value it cannot otherwise read - and that is the whole defense.
    """
    page.evaluate(
        f"fetch('{FOREIGN_ORIGIN}/collect', {{method: 'POST', body: '{{}}'}}).catch(() => {{}})"
    )
    page.wait_for_function("() => true")

    assert "x-csrf-token" not in _last(page, FOREIGN_ORIGIN)["headers"]


def test_an_explicit_header_is_not_overwritten(page):
    """A caller that sets its own token keeps it - that is how a retry works."""
    page.evaluate(
        "fetch('/api/v1/profile', {method: 'POST', headers: {'X-CSRF-Token': 'mine'}})"
    )
    page.wait_for_function("() => true")

    assert _last(page, "/api/v1/profile")["headers"].get("x-csrf-token") == "mine"


def test_a_read_is_left_alone(page):
    """A GET is not wrapped, so nothing about existing pages changes."""
    page.evaluate("fetch('/api/v1/dashboard')")
    page.wait_for_function("() => true")

    read = _last(page, "/api/v1/dashboard")
    assert read["method"] == "GET"
    assert "x-csrf-token" not in read["headers"]
