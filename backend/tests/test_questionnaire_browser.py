"""The real questionnaire script, driven in Chromium, against the new 422s.

TASK-030 makes the endpoint refuse duplicate and unknown answers. That is only
safe if the shipped client cannot produce them, and reading the source is not
proof: this drives ``questionnaire.js`` in a real browser, answers every
question — changing some answers on the way back, which is exactly how a
duplicate would be produced by a naive client — and inspects the payload the
page actually posts.

Network is stubbed inside the page, so nothing leaves the machine.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser

STATIC_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "js"
PAGE_ORIGIN = "http://questionnaire.test"

DEFINITION = {
    "version": "v3",
    "title": "Career questionnaire",
    "questions": [
        {
            "id": f"q{index}",
            "title": f"Question {index}",
            "subtitle": "Pick one.",
            "kind": "single",
            "options": [
                {"id": f"q{index}_a", "label": "First"},
                {"id": f"q{index}_b", "label": "Second"},
            ],
        }
        for index in range(1, 4)
    ],
}


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
        page.goto(f"{PAGE_ORIGIN}/questionnaire")

    page.render = render  # type: ignore[attr-defined]
    try:
        yield page
    finally:
        context.close()


def _embed_json(value) -> str:
    return json.dumps(value).replace("</", "<\\/")


def _questionnaire_page() -> str:
    """The questionnaire template's ids plus the real script, network stubbed."""
    return f"""
<!doctype html>
<html><body>
  <div id="loading"><p></p></div>
  <div id="header-section" class="hidden"></div>
  <div id="question-view" class="hidden">
    <h2 id="question-title"></h2>
    <p id="question-subtitle"></p>
    <div id="options-list"></div>
    <button id="btn-prev"></button>
    <button id="btn-next" disabled></button>
  </div>
  <div id="results-view" class="hidden">
    <div id="top-careers-list"></div>
    <button id="questionnaire-reload"></button>
    <button id="questionnaire-go-dashboard"></button>
  </div>
  <div id="progress-bar"></div>
  <span id="step-counter"></span>
  <span id="progress-text"></span>
  <script>
    window.__posted = [];
    window.fetch = async function (url, options) {{
      const method = (options && options.method) || 'GET';
      if (method === 'POST') {{
        window.__posted.push(JSON.parse(options.body));
        return {{
          ok: true, status: 200,
          json: async () => ({{ id: 'x', version: 'v3', top_careers: [], created_at: '2026-01-01T00:00:00Z' }})
        }};
      }}
      return {{ ok: true, status: 200, json: async () => ({_embed_json(DEFINITION)}) }};
    }};
  </script>
  <script>{(STATIC_JS / "questionnaire.js").read_text()}</script>
</body></html>
"""


def _answer_current_question(page, option_index: int) -> None:
    page.wait_for_selector("#options-list .option-card")
    options = page.query_selector_all("#options-list .option-card")
    assert options, "the script rendered no options"
    options[option_index].click()


def test_the_shipped_client_cannot_post_a_duplicate_or_unknown_answer(page):
    """Walk the quiz, change answers on the way back, inspect what is posted."""
    page.render(_questionnaire_page())
    # ``let`` at script scope does not become a window property, so the wait is
    # on the DOM the script produces rather than on the variable it holds.
    page.wait_for_selector("#options-list .option-card")

    # Answer all three, going forward.
    for _ in range(3):
        _answer_current_question(page, 0)
        page.click("#btn-next")

    posted = page.evaluate("() => window.__posted")
    assert len(posted) == 1, f"expected one submission, got {len(posted)}"
    answers = posted[0]["answers"]

    question_ids = [answer["question_id"] for answer in answers]
    assert len(question_ids) == len(set(question_ids)), (
        f"the client posted a duplicate question: {question_ids}"
    )

    known_questions = {question["id"] for question in DEFINITION["questions"]}
    options_by_question = {
        question["id"]: {option["id"] for option in question["options"]}
        for question in DEFINITION["questions"]
    }
    for answer in answers:
        assert answer["question_id"] in known_questions
        assert answer["option_id"] in options_by_question[answer["question_id"]]


def test_going_back_and_changing_an_answer_replaces_it_rather_than_adding_one(page):
    """The case that would have produced a duplicate under a list-based client."""
    page.render(_questionnaire_page())
    # ``let`` at script scope does not become a window property, so the wait is
    # on the DOM the script produces rather than on the variable it holds.
    page.wait_for_selector("#options-list .option-card")

    _answer_current_question(page, 0)
    page.click("#btn-next")
    _answer_current_question(page, 0)
    # Back to question 1 and pick the other option.
    page.click("#btn-prev")
    _answer_current_question(page, 1)
    page.click("#btn-next")
    page.click("#btn-next")
    _answer_current_question(page, 0)
    page.click("#btn-next")

    posted = page.evaluate("() => window.__posted")
    assert len(posted) == 1
    answers = posted[0]["answers"]

    question_ids = [answer["question_id"] for answer in answers]
    assert question_ids == sorted(set(question_ids), key=question_ids.index)
    assert len(question_ids) == 3, question_ids
    # The changed answer is the second option, not both options.
    first = next(answer for answer in answers if answer["question_id"] == "q1")
    assert first["option_id"] == "q1_b"
