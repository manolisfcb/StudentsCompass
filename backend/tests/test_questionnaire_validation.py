"""An answer the questionnaire cannot account for must be refused, not scored as zero.

``submit_questionnaire`` looked every answer up with ``.get(..., {})`` and added
whatever came back. Three defects were silent at once:

* a ``question_id`` that does not exist contributed nothing and looked like a
  legitimate answer;
* an ``option_id`` belonging to a different question did the same;
* the same question answered twice was **counted twice**, so repeating one
  answer inflated a career score.

Separately, the profile endpoint rendered stored answers against whatever
definition happened to be current, so after a revision an old profile showed
questions the user never saw.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest

from app.models.questionnaireModel import UserQuestionnaire
from app.services.accounts import questionnaireCatalog
from app.services.accounts.questionnaireCatalog import (
    QuestionnaireVersionNotFound,
    available_versions,
    load_current_definition,
    load_definition_for_version,
)


@pytest.fixture
def definition():
    return load_current_definition()


@pytest.fixture
def valid_answers(definition):
    """One valid answer per question, in definition order."""
    return [
        {"question_id": question["id"], "option_id": question["options"][0]["id"]}
        for question in definition["questions"]
    ]


async def _submit(client, answers):
    return await client.post("/api/v1/questionnaire", json={"answers": answers})


# ---------------------------------------------------------------------------
# The catalogue
# ---------------------------------------------------------------------------


def test_definitions_are_indexed_by_the_version_they_declare():
    """The current file is v1/v2.json and declares v3; the path is not the key."""
    assert load_current_definition()["version"] == "v3"
    assert set(available_versions()) >= {"v1", "v3"}
    assert load_definition_for_version("v1")["version"] == "v1"
    assert load_definition_for_version("v3")["version"] == "v3"


def test_an_unknown_version_is_refused_rather_than_substituted():
    with pytest.raises(QuestionnaireVersionNotFound) as raised:
        load_definition_for_version("v99")
    assert raised.value.version == "v99"
    assert "v1" in raised.value.available


# ---------------------------------------------------------------------------
# Valid submissions keep working
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_valid_submission_keeps_its_scores(client, auth_headers, valid_answers):
    response = await _submit(client, valid_answers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["version"] == "v3"
    assert payload["top_careers"], "a fully answered questionnaire scored nothing"
    scores = [entry["score"] for entry in payload["top_careers"]]
    assert scores == sorted(scores, reverse=True), "the descending order changed"


@pytest.mark.asyncio
async def test_the_scores_are_the_sum_of_the_selected_option_weights(
    client, auth_headers, definition, valid_answers
):
    """Parity with the arithmetic the endpoint has always done."""
    expected: dict[str, int] = {}
    by_id = {question["id"]: question for question in definition["questions"]}
    for answer in valid_answers:
        question = by_id[answer["question_id"]]
        option = next(o for o in question["options"] if o["id"] == answer["option_id"])
        for career, weight in option.get("weights", {}).items():
            expected[career] = expected.get(career, 0) + weight

    response = await _submit(client, valid_answers)
    returned = {entry["career"]: entry["score"] for entry in response.json()["top_careers"]}

    assert returned == expected


@pytest.mark.asyncio
async def test_a_partial_submission_is_accepted_and_scores_only_what_it_answered(
    client, auth_headers, definition, valid_answers
):
    """The optional-question policy, stated rather than inferred.

    Leaving questions unanswered has always been allowed and simply scores
    nothing for them. This test is what makes that a decision instead of an
    accident, so a future change to it has to be deliberate.
    """
    half = valid_answers[: len(valid_answers) // 2]

    response = await _submit(client, half)
    assert response.status_code == 200, response.text

    full = await _submit(client, valid_answers)
    partial_total = sum(entry["score"] for entry in response.json()["top_careers"])
    full_total = sum(entry["score"] for entry in full.json()["top_careers"])
    assert 0 < partial_total < full_total


@pytest.mark.asyncio
async def test_an_empty_submission_is_accepted_and_scores_nothing(client, auth_headers):
    response = await _submit(client, [])

    assert response.status_code == 200, response.text
    assert response.json()["top_careers"] == []


# ---------------------------------------------------------------------------
# Invalid submissions are refused
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_unknown_question_id_is_a_422_not_a_silent_zero(
    client, auth_headers, valid_answers
):
    answers = valid_answers[:2] + [{"question_id": "no_such_question", "option_id": "a"}]

    response = await _submit(client, answers)

    assert response.status_code == 422
    assert "no_such_question" in response.json()["detail"]


@pytest.mark.asyncio
async def test_an_option_from_another_question_is_a_422(
    client, auth_headers, definition, valid_answers
):
    """An option id that exists, but not on the question it was sent for."""
    first, second = definition["questions"][0], definition["questions"][1]
    answers = [{"question_id": first["id"], "option_id": second["options"][0]["id"]}]

    response = await _submit(client, answers)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert first["id"] in detail
    assert second["options"][0]["id"] in detail


@pytest.mark.asyncio
async def test_the_same_question_answered_twice_is_a_422(client, auth_headers, valid_answers):
    """The one that inflated scores: repeating an answer used to add twice."""
    answers = valid_answers[:3] + [valid_answers[0]]

    response = await _submit(client, answers)

    assert response.status_code == 422
    assert "more than once" in response.json()["detail"]
    assert valid_answers[0]["question_id"] in response.json()["detail"]


@pytest.mark.asyncio
async def test_a_repeated_question_with_a_different_option_is_also_refused(
    client, auth_headers, definition, valid_answers
):
    question = definition["questions"][0]
    answers = [
        {"question_id": question["id"], "option_id": question["options"][0]["id"]},
        {"question_id": question["id"], "option_id": question["options"][1]["id"]},
    ]

    response = await _submit(client, answers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_nothing_is_persisted_when_the_submission_is_refused(
    client, auth_headers, db_session, test_user, valid_answers
):
    from sqlalchemy import func, select

    await _submit(client, valid_answers + [{"question_id": "ghost", "option_id": "x"}])

    stored = await db_session.scalar(
        select(func.count(UserQuestionnaire.id)).where(
            UserQuestionnaire.user_id == test_user.id
        )
    )
    assert stored == 0


# ---------------------------------------------------------------------------
# The profile uses the version it was answered under
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_older_profile_is_rendered_with_the_older_definition(
    client, auth_headers, db_session, test_user
):
    """The v1 questions, not the current v3 ones."""
    v1 = load_definition_for_version("v1")
    db_session.add(
        UserQuestionnaire(
            id=uuid.uuid4(),
            user_id=test_user.id,
            version="v1",
            answers=[
                {
                    "question_id": v1["questions"][0]["id"],
                    "option_id": v1["questions"][0]["options"][0]["id"],
                }
            ],
            results=[{"career": "analyst", "score": 3}],
            created_at=datetime.utcnow(),
        )
    )
    await db_session.commit()

    payload = (await client.get("/api/v1/questionnaire/profile", headers=auth_headers)).json()

    assert payload["version"] == "v1"
    assert payload["questionnaire"]["version"] == "v1"
    assert payload["questionnaire_definition_available"] is True

    returned_ids = [question["id"] for question in payload["questionnaire"]["questions"]]
    assert returned_ids == [question["id"] for question in v1["questions"]]

    current_ids = {question["id"] for question in load_current_definition()["questions"]}
    assert set(returned_ids) != current_ids, "the profile fell back to the current definition"
    # The answered question is one the user was actually asked.
    assert payload["answers"][0]["question_id"] in returned_ids


@pytest.mark.asyncio
async def test_a_profile_whose_definition_is_gone_says_so_instead_of_substituting(
    client, auth_headers, db_session, test_user
):
    """Losing the questions is bad; showing different ones as if they were the same is worse."""
    db_session.add(
        UserQuestionnaire(
            id=uuid.uuid4(),
            user_id=test_user.id,
            version="v0-retired",
            answers=[{"question_id": "q1", "option_id": "a"}],
            results=[{"career": "analyst", "score": 3}],
            created_at=datetime.utcnow(),
        )
    )
    await db_session.commit()

    response = await client.get("/api/v1/questionnaire/profile", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "v0-retired"
    assert payload["questionnaire"] is None
    assert payload["questionnaire_definition_available"] is False
    # The user's own record is still returned in full.
    assert payload["answers"] == [{"question_id": "q1", "option_id": "a"}]
    assert payload["results"] == [{"career": "analyst", "score": 3}]


@pytest.mark.asyncio
async def test_a_stored_result_is_never_recomputed_from_the_current_definition(
    client, auth_headers, db_session, test_user
):
    """The snapshot is the record: it is returned as stored, not re-derived."""
    stored_results = [{"career": "made-up-career", "score": 999}]
    db_session.add(
        UserQuestionnaire(
            id=uuid.uuid4(),
            user_id=test_user.id,
            version="v1",
            answers=[{"question_id": "energy_source", "option_id": "build"}],
            results=stored_results,
            created_at=datetime.utcnow(),
        )
    )
    await db_session.commit()

    payload = (await client.get("/api/v1/questionnaire/profile", headers=auth_headers)).json()

    assert payload["results"] == stored_results


# ---------------------------------------------------------------------------
# The catalogue is robust to what is on disk
# ---------------------------------------------------------------------------


def test_a_definition_without_a_version_is_ignored_not_crashed_on(tmp_path, monkeypatch):
    monkeypatch.setattr(questionnaireCatalog, "QUESTIONNAIRE_ROOT", tmp_path)
    questionnaireCatalog.reset_cache()
    try:
        (tmp_path / "broken.json").write_text(json.dumps({"title": "no version"}))
        (tmp_path / "good.json").write_text(
            json.dumps({"version": "vX", "title": "T", "questions": []})
        )

        assert available_versions() == ("vX",)
    finally:
        questionnaireCatalog.reset_cache()


def test_unreadable_json_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(questionnaireCatalog, "QUESTIONNAIRE_ROOT", tmp_path)
    questionnaireCatalog.reset_cache()
    try:
        (tmp_path / "corrupt.json").write_text("{not json at all")
        (tmp_path / "good.json").write_text(
            json.dumps({"version": "vY", "title": "T", "questions": []})
        )

        assert available_versions() == ("vY",)
    finally:
        questionnaireCatalog.reset_cache()


def test_the_weights_are_never_sent_to_the_client():
    """Unchanged, and worth keeping stated: the read schema drops them."""
    from app.schemas.questionnaireSchema import QuestionnaireRead

    rendered = QuestionnaireRead(**load_current_definition()).model_dump()
    for question in rendered["questions"]:
        for option in question["options"]:
            assert "weights" not in option
