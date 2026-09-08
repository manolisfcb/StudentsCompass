"""Browser tests for the CV list and the link sinks (TASK-004 / F-03).

These run the *real* static scripts in a real Chromium via Playwright and
inspect the resulting DOM, rather than grepping the source for a helper name.
Network is stubbed inside the page, so nothing leaves the machine.

Skipped when Playwright or its browser is not installed:

    uv pip install playwright && .venv/bin/python -m playwright install chromium
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser

STATIC_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "js"

# A filename is attacker-controlled: it comes straight from the upload.
HOSTILE_FILENAME = '<img src=x onerror="window.__xss=true">Résumé "final" <b>v2</b>.pdf'


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


PAGE_ORIGIN = "http://profile.test"


@pytest.fixture
def page(browser):
    """A page served from a real http origin, with no network access.

    set_content() on about:blank gives an opaque origin, which is not how the
    app runs and changes how relative URLs resolve. Every request is fulfilled
    locally by the route handler, so nothing leaves the machine.
    """
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(5000)

    holder = {"html": "<!doctype html><html><body></body></html>"}
    page.route(
        "**/*",
        lambda route: route.fulfill(
            status=200, content_type="text/html; charset=utf-8", body=holder["html"]
        ),
    )

    def render(html: str) -> None:
        holder["html"] = html
        page.goto(f"{PAGE_ORIGIN}/user-profile")

    page.render = render  # type: ignore[attr-defined]
    try:
        yield page
    finally:
        context.close()


def _embed_json(value) -> str:
    """JSON safe to place inside an inline <script>.

    A literal "</script>" in the data would close the tag early — an artifact
    of the harness, not of the code under test.
    """
    return json.dumps(value).replace("</", "<\\/")


def _cv_page(resumes: list[dict]) -> str:
    """The CV-list fragment of userProfile.html plus the real scripts.

    The scripts are injected after DOMContentLoaded has fired, so only
    loadResumes() runs — the rest of the profile page is out of scope here.
    """
    return f"""
<!doctype html>
<html><body>
  <p id="cvListEmpty"></p>
  <div id="cvTableWrapper"><table><tbody id="cvTableBody"></tbody></table></div>
  <script>
    window.__xss = false;
    window.__deleteRequests = [];
    window.fetch = async function (url, options) {{
      const method = (options && options.method) || 'GET';
      if (method === 'DELETE') {{
        window.__deleteRequests.push(url);
        return {{ ok: true, status: 200, json: async () => ({{}}) }};
      }}
      return {{
        ok: true,
        status: 200,
        json: async () => {_embed_json(resumes)}
      }};
    }};
  </script>
  <script>{(STATIC_JS / "safeDom.js").read_text()}</script>
  <script>{(STATIC_JS / "userProfile.js").read_text()}</script>
  <script>loadResumes();</script>
</body></html>
"""


def _resume(**overrides) -> dict:
    resume = {
        "id": "11111111-1111-1111-1111-111111111111",
        "original_filename": "cv.pdf",
        "view_url": "https://files.example.com/cv.pdf",
        "created_at": "2026-01-15T10:00:00Z",
    }
    resume.update(overrides)
    return resume


# --- Stored XSS -------------------------------------------------------------

def test_hostile_filename_is_rendered_as_text_not_markup(page):
    page.render(_cv_page([_resume(original_filename=HOSTILE_FILENAME)]))
    page.wait_for_selector("#cvTableBody tr")

    # The payload never becomes an element...
    assert page.locator("#cvTableBody img").count() == 0
    assert page.locator("#cvTableBody b").count() == 0
    assert page.evaluate("window.__xss") is False
    # ...and the whole name, tags and quotes included, is shown literally.
    assert page.locator("#cvTableBody a").inner_text() == HOSTILE_FILENAME


@pytest.mark.parametrize(
    "filename",
    [
        "Curriculum Vitæ – Ünïcodé 简历.pdf",
        "quote\"and'apostrophe.pdf",
        "a & b <script>alert(1)</script>.pdf",
    ],
)
def test_names_with_tags_quotes_and_international_characters_display_literally(
    page, filename
):
    page.render(_cv_page([_resume(original_filename=filename)]))
    page.wait_for_selector("#cvTableBody tr")

    assert page.locator("#cvTableBody a").inner_text() == filename
    assert page.locator("#cvTableBody script").count() == 0


# --- Link targets -----------------------------------------------------------

@pytest.mark.parametrize(
    "hostile_url",
    [
        "javascript:window.__xss=true",
        "JaVaScRiPt:window.__xss=true",
        "data:text/html;base64,PHNjcmlwdD53aW5kb3cuX194c3M9dHJ1ZTwvc2NyaXB0Pg==",
        "vbscript:msgbox(1)",
    ],
)
def test_dangerous_link_schemes_are_rejected(page, hostile_url):
    """The name still shows; it just is not a clickable navigation."""
    page.render(_cv_page([_resume(view_url=hostile_url)]))
    page.wait_for_selector("#cvTableBody tr")

    assert page.locator("#cvTableBody a").count() == 0
    assert page.locator("#cvTableBody td span").inner_text() == "cv.pdf"
    assert page.evaluate("window.__xss") is False


@pytest.mark.parametrize(
    "url",
    [
        "https://files.example.com/cv.pdf",
        "http://files.example.com/cv.pdf",
        "/api/v1/profile/cv/1/download",
    ],
)
def test_http_and_relative_links_still_work(page, url):
    page.render(_cv_page([_resume(view_url=url)]))
    page.wait_for_selector("#cvTableBody tr")

    anchor = page.locator("#cvTableBody a")
    assert anchor.count() == 1
    assert anchor.get_attribute("target") == "_blank"
    assert anchor.get_attribute("rel") == "noopener noreferrer"


# --- The listed flow still works -------------------------------------------

def test_list_and_delete_flow_is_preserved(page):
    page.render(
        _cv_page(
            [
                _resume(id="aaaaaaaa-0000-0000-0000-000000000001", original_filename="one.pdf"),
                _resume(id="aaaaaaaa-0000-0000-0000-000000000002", original_filename="two.pdf"),
            ]
        )
    )
    page.wait_for_selector("#cvTableBody tr")

    rows = page.locator("#cvTableBody tr")
    assert rows.count() == 2
    assert page.locator("#cvTableBody a").nth(0).inner_text() == "one.pdf"
    assert page.locator("#cvTableBody a").nth(1).inner_text() == "two.pdf"
    # Each row keeps its date cell and a wired-up delete button.
    assert page.locator("#cvTableBody .delete-cv-btn").count() == 2

    page.locator("#cvTableBody .delete-cv-btn").nth(0).click()
    page.wait_for_function("window.__deleteRequests.length > 0")

    assert page.evaluate("window.__deleteRequests")[0].endswith(
        "/api/v1/profile/cv/aaaaaaaa-0000-0000-0000-000000000001"
    )


def test_empty_list_shows_the_empty_state(page):
    page.render(_cv_page([]))

    page.wait_for_function(
        "document.getElementById('cvListEmpty').textContent === 'No CV uploaded yet.'"
    )
    assert page.locator("#cvTableBody tr").count() == 0


# --- Shared helper ----------------------------------------------------------

def test_safe_http_url_contract(page):
    page.render(f'<!doctype html><html><body><script>{(STATIC_JS / "safeDom.js").read_text()}</script></body></html>')

    rejected = [
        "javascript:alert(1)",
        " javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "blob:https://example.com/abc",
        "vbscript:msgbox(1)",
        "",
        None,
    ]
    for value in rejected:
        assert page.evaluate("v => SafeDom.safeHttpUrl(v)", value) is None, value

    for value in ("https://a.example/x", "http://a.example/x", "/relative/path"):
        assert page.evaluate("v => SafeDom.safeHttpUrl(v)", value) is not None, value
