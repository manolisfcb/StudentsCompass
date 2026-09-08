from datetime import datetime, timedelta

import pytest

from app.models.questionnaireModel import UserQuestionnaire


@pytest.mark.asyncio
async def test_questionnaire_profile_returns_404_without_responses(client, auth_headers):
    response = await client.get("/api/v1/questionnaire/profile", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "No questionnaire responses found"


@pytest.mark.asyncio
async def test_questionnaire_profile_returns_latest_response(client, auth_headers, db_session, test_user):
    older = UserQuestionnaire(
        user_id=test_user.id,
        version="old",
        answers=[{"question_id": "q1", "option_id": "a"}],
        results=[{"career": "old-career", "score": 1}],
        created_at=datetime.utcnow() - timedelta(days=1),
    )
    # A version that is actually on disk. Before TASK-030 this said "latest" and
    # the endpoint answered with whatever definition happened to be current,
    # which is the defect that task fixed: the profile now returns the
    # definition the answers were given under, so the stored version has to be
    # a real one.
    latest = UserQuestionnaire(
        user_id=test_user.id,
        version="v1",
        answers=[{"question_id": "q1", "option_id": "b"}],
        results=[{"career": "latest-career", "score": 10}],
        created_at=datetime.utcnow(),
    )
    db_session.add_all([older, latest])
    await db_session.commit()

    response = await client.get("/api/v1/questionnaire/profile", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(test_user.id)
    assert data["user_name"] == "Test User"
    assert data["user_email"] == "test@example.com"
    assert data["version"] == "v1"
    assert data["answers"] == [{"question_id": "q1", "option_id": "b"}]
    assert data["results"] == [{"career": "latest-career", "score": 10}]
    assert data["questionnaire"]["version"] == "v1"
