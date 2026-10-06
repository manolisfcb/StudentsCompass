"""What to study first for one vacancy, before the interview (TASK-080)."""
from __future__ import annotations

import uuid

import pytest

from app.models.jobTargetModel import JobTargetModel
from app.services.analytics.capstoneAnalyticsSeedService import seed_capstone_analytics_minimum
from app.services.careerLab import jobTargetRoadmapService as roadmap
from tests.test_career_lab_job_targets import POSTING, _resume


@pytest.fixture
def hash_provider(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "hash")


async def _target_id(client, db_session, user_id, headers) -> str:
    """POSTING read against a CV that lacks Data Cleaning, Power BI, Sales and Statistics."""
    await seed_capstone_analytics_minimum(db_session)
    resume = await _resume(db_session, user_id)
    response = await client.post(
        "/api/v1/career-lab/job-targets",
        json={"text": POSTING, "resume_id": str(resume.id)},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _roadmap(client, target_id, headers, **body):
    return await client.post(f"/api/v1/career-lab/job-targets/{target_id}/roadmap", json=body, headers=headers)


# ---------------------------------------------------------------------------
# The day plan
# ---------------------------------------------------------------------------


def test_courses_are_laid_end_to_end_in_days():
    steps = roadmap.schedule_steps(
        [{"duration_hours": 8}, {"duration_hours": 22}, {"duration_hours": 0}, {"duration_hours": 3}],
        hours_per_day=3,
    )
    # 8h → days 1–3 (day 3 only part used); 22h starts on day 3 and ends on 10;
    # a course with no recorded duration takes no day of its own.
    assert [(step["order"], step["start_day"], step["end_day"]) for step in steps] == [
        (1, 1, 3),
        (2, 3, 10),
        (3, 11, 11),
        (4, 11, 11),
    ]


def test_a_day_used_up_starts_the_next_course_on_the_next_day():
    steps = roadmap.schedule_steps([{"duration_hours": 4}, {"duration_hours": 2}], hours_per_day=2)
    assert [(step["start_day"], step["end_day"]) for step in steps] == [(1, 2), (3, 3)]


# ---------------------------------------------------------------------------
# The endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_route_works_the_vacancy_gaps_in_the_time_left(
    client, db_session, test_user, auth_headers, hash_provider
):
    target_id = await _target_id(client, db_session, test_user.id, auth_headers)

    response = await _roadmap(client, target_id, auth_headers, days_until_interview=30, hours_per_day=3)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["constraints"]["available_hours"] == 90
    assert body["total_hours"] <= 90
    steps = body["steps"]
    assert [step["order"] for step in steps] == list(range(1, len(steps) + 1))
    assert steps[0]["start_day"] == 1 and steps[-1]["end_day"] <= 30
    taught = {skill["display_name"] for step in steps for skill in step["skills"]}
    assert {"Data Cleaning", "Power BI", "Statistics"} <= taught
    # Every skill a step names is one of this vacancy's gaps.
    assert taught <= {"Data Cleaning", "Power BI", "Sales", "Statistics"}
    covered = {gap["display_name"]: gap for gap in body["covered_gaps"]}
    assert covered["Data Cleaning"]["requirement"] == "required"
    assert covered["Data Cleaning"]["priority_rank"] == 1
    # No course in the catalogue teaches Sales: no amount of time fixes that.
    assert body["uncovered_gaps"] == [
        {
            "skill_id": body["uncovered_gaps"][0]["skill_id"],
            "display_name": "Sales",
            "requirement": "preferred",
            "kind": "gap",
            "priority_rank": 3,
            "reason": "no_course",
        }
    ]
    assert 0 < body["gap_coverage"] < 1
    # The optimiser's projection is of role readiness, not of this vacancy.
    assert "projected_match_score_after" not in body


@pytest.mark.asyncio
async def test_fewer_days_fit_fewer_courses(client, db_session, test_user, auth_headers, hash_provider):
    target_id = await _target_id(client, db_session, test_user.id, auth_headers)

    roomy = (await _roadmap(client, target_id, auth_headers, days_until_interview=30, hours_per_day=3)).json()
    tight = (await _roadmap(client, target_id, auth_headers, days_until_interview=3, hours_per_day=4)).json()
    none_fit = (await _roadmap(client, target_id, auth_headers, days_until_interview=2, hours_per_day=1)).json()

    assert tight["total_hours"] <= 12
    assert len(none_fit["steps"]) < len(tight["steps"]) < len(roomy["steps"])
    # The one course that fits goes to the top-priority gap.
    assert [skill["display_name"] for skill in tight["steps"][0]["skills"]] == ["Data Cleaning"]
    assert none_fit["gap_coverage"] == 0
    reasons = {gap["display_name"]: gap["reason"] for gap in none_fit["uncovered_gaps"]}
    assert reasons == {
        "Data Cleaning": "out_of_reach",
        "Power BI": "out_of_reach",
        "Statistics": "out_of_reach",
        "Sales": "no_course",
    }


@pytest.mark.asyncio
async def test_a_budget_and_a_course_cap_also_bound_it(client, db_session, test_user, auth_headers, hash_provider):
    target_id = await _target_id(client, db_session, test_user.id, auth_headers)

    response = await _roadmap(
        client, target_id, auth_headers, days_until_interview=60, hours_per_day=4, budget=0, max_courses=1
    )

    body = response.json()
    assert len(body["steps"]) == 1
    assert body["total_cost"] == 0
    assert body["constraints"] == {
        "days_until_interview": 60,
        "hours_per_day": 4,
        "available_hours": 240,
        "budget": 0,
        "max_courses": 1,
    }


@pytest.mark.asyncio
async def test_a_vacancy_without_gaps_gets_an_empty_route(
    client, db_session, test_user, auth_headers, hash_provider
):
    target_id = await _target_id(client, db_session, test_user.id, auth_headers)
    target = await db_session.get(JobTargetModel, uuid.UUID(target_id))
    target.match_snapshot = {**target.match_snapshot, "gaps": []}
    await db_session.commit()

    body = (await _roadmap(client, target_id, auth_headers, days_until_interview=5, hours_per_day=2)).json()

    assert body["steps"] == [] and body["uncovered_gaps"] == [] and body["gap_coverage"] is None


@pytest.mark.asyncio
async def test_a_vacancy_without_analysis_is_a_conflict(client, db_session, test_user, auth_headers, hash_provider):
    target_id = await _target_id(client, db_session, test_user.id, auth_headers)
    target = await db_session.get(JobTargetModel, uuid.UUID(target_id))
    target.status = "failed"
    target.match_snapshot = None
    await db_session.commit()

    response = await _roadmap(client, target_id, auth_headers, days_until_interview=5, hours_per_day=2)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


@pytest.mark.asyncio
async def test_only_the_owner_can_plan_from_a_vacancy(client, db_session, auth_headers):
    from app.models.userModel import User

    stranger = User(
        id=uuid.uuid4(), email="stranger@example.invalid", hashed_password="x",
        is_active=True, is_superuser=False, is_verified=True,
    )
    db_session.add(stranger)
    await db_session.commit()
    other_user_target = JobTargetModel(
        user_id=stranger.id, text_hash="0" * 64, raw_text=POSTING, status="ready", match_snapshot={"gaps": []}
    )
    db_session.add(other_user_target)
    await db_session.commit()

    foreign = await _roadmap(client, other_user_target.id, auth_headers, days_until_interview=5, hours_per_day=2)
    missing = await _roadmap(client, uuid.uuid4(), auth_headers, days_until_interview=5, hours_per_day=2)

    assert foreign.status_code == 404 and missing.status_code == 404
    assert foreign.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"days_until_interview": 0, "hours_per_day": 2},
        {"days_until_interview": 5, "hours_per_day": 0},
        {"days_until_interview": 5, "hours_per_day": 17},
        {"days_until_interview": 5, "hours_per_day": 2, "max_courses": 0},
    ],
)
async def test_the_time_left_is_bounded(client, auth_headers, body):
    response = await _roadmap(client, uuid.uuid4(), auth_headers, **body)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_a_retried_request_does_not_solve_twice(
    client, db_session, test_user, auth_headers, hash_provider, monkeypatch
):
    target_id = await _target_id(client, db_session, test_user.id, auth_headers)
    solves = []
    real_build = roadmap.JobTargetRoadmapService.build

    async def counting_build(self, **kwargs):
        solves.append(kwargs["constraints"])
        return await real_build(self, **kwargs)

    monkeypatch.setattr(roadmap.JobTargetRoadmapService, "build", counting_build)
    headers = {**auth_headers, "Idempotency-Key": str(uuid.uuid4())}
    body = {"days_until_interview": 10, "hours_per_day": 2}

    first = await _roadmap(client, target_id, headers, **body)
    second = await _roadmap(client, target_id, headers, **body)

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert len(solves) == 1
