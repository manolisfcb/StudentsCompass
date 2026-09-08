"""Four integers and five rows should not cost the user's whole history.

The dashboard selected every application a user had ever made, counted the
statuses in Python and sorted the list to take the top five. So opening it got
slower and heavier for exactly the users who had used the product most, and the
five rows shown were a slice of a list that had already been fully materialised
and serialised into ORM objects.

The counts are now one aggregate query and the recent list is ordered and
limited by the database. The tests below hold the new implementation against
the old one on the same data — including the cases the Python version got away
with by accident, like ties on ``application_date``.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

from app.models.applicationModel import ApplicationModel, ApplicationStatus
from app.models.companyModel import Company
from app.services.applications.dashboardService import DashboardService
from tests.harness import count_queries

ALL_STATUSES = list(ApplicationStatus)


async def _company(session):
    company = Company(id=uuid.uuid4(), company_name="Dashboard Co")
    session.add(company)
    await session.flush()
    return company


async def _seed_applications(session, user_id, count, *, company=None, tie_dates=False):
    """``count`` applications cycling through every status.

    With ``tie_dates`` every application shares one ``application_date``, which
    is the case that decides whether "the five most recent" is stable.
    """
    if company is None:
        company = await _company(session)
    base = datetime.utcnow() - timedelta(days=count + 1)
    rows = []
    for index in range(count):
        rows.append(
            ApplicationModel(
                id=uuid.uuid4(),
                user_id=user_id,
                company_id=company.id,
                job_title=f"Role {index:05d}",
                status=ALL_STATUSES[index % len(ALL_STATUSES)],
                application_date=base if tie_dates else base + timedelta(days=index),
                notes=f"note-{index}",
            )
        )
    session.add_all(rows)
    await session.commit()
    return company, rows


async def _legacy_stats_and_recent(session, user_id):
    """The pre-TASK-025 implementation, kept here only to compare against."""
    from sqlalchemy import select

    result = await session.execute(
        select(ApplicationModel).where(ApplicationModel.user_id == user_id)
    )
    applications = list(result.scalars().all())
    stats = DashboardService._build_student_application_stats(applications)
    recent = DashboardService._serialize_recent_applications(
        sorted(applications, key=lambda app: app.application_date, reverse=True)[:5]
    )
    return stats, recent


# ---------------------------------------------------------------------------
# Parity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, 1, 100, 10_000])
async def test_the_aggregated_counts_match_the_python_counts_exactly(
    db_session, test_user, count
):
    await _seed_applications(db_session, test_user.id, count)

    aggregated = await DashboardService._aggregate_student_application_stats(
        test_user.id, db_session
    )
    legacy, _recent = await _legacy_stats_and_recent(db_session, test_user.id)

    assert aggregated == legacy
    assert aggregated["total_applications"] == count


@pytest.mark.asyncio
async def test_every_status_is_counted_under_the_right_name(db_session, test_user):
    """One application per status: each bucket must see exactly its own."""
    company = await _company(db_session)
    base = datetime.utcnow()
    db_session.add_all(
        [
            ApplicationModel(
                id=uuid.uuid4(),
                user_id=test_user.id,
                company_id=company.id,
                job_title=status.value,
                status=status,
                application_date=base - timedelta(days=index),
            )
            for index, status in enumerate(ALL_STATUSES)
        ]
    )
    await db_session.commit()

    stats = await DashboardService._aggregate_student_application_stats(
        test_user.id, db_session
    )

    assert stats["total_applications"] == len(ALL_STATUSES)
    assert stats["in_review"] == 1
    assert stats["interviews"] == 1
    assert stats["offers"] == 1
    assert stats["applied"] == 1


@pytest.mark.asyncio
async def test_another_users_applications_are_not_counted(db_session, test_user):
    """The aggregate keeps the same ownership filter the list had."""
    from app.models.userModel import User

    stranger = User(
        id=uuid.uuid4(),
        email=f"other-{uuid.uuid4().hex[:8]}@example.invalid",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(stranger)
    await db_session.commit()

    company, _ = await _seed_applications(db_session, test_user.id, 3)
    await _seed_applications(db_session, stranger.id, 7, company=company)

    mine = await DashboardService._aggregate_student_application_stats(test_user.id, db_session)
    theirs = await DashboardService._aggregate_student_application_stats(stranger.id, db_session)

    assert mine["total_applications"] == 3
    assert theirs["total_applications"] == 7


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, 3, 100, 10_000])
async def test_the_recent_five_match_the_python_slice(db_session, test_user, count):
    await _seed_applications(db_session, test_user.id, count)

    fetched = DashboardService._serialize_recent_applications(
        await DashboardService._fetch_recent_applications(test_user.id, db_session)
    )
    _stats, legacy = await _legacy_stats_and_recent(db_session, test_user.id)

    assert fetched == legacy
    assert len(fetched) == min(count, DashboardService.RECENT_APPLICATIONS_LIMIT)


@pytest.mark.asyncio
async def test_ties_on_the_application_date_produce_a_stable_five(db_session, test_user):
    """A bulk apply session must not reshuffle the dashboard on every refresh."""
    await _seed_applications(db_session, test_user.id, 40, tie_dates=True)

    answers = [
        DashboardService._serialize_recent_applications(
            await DashboardService._fetch_recent_applications(test_user.id, db_session)
        )
        for _ in range(5)
    ]

    assert all(answer == answers[0] for answer in answers), "the top five moved between reads"
    assert len(answers[0]) == 5


# ---------------------------------------------------------------------------
# Cost
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_dashboard_query_count_does_not_grow_with_the_history(db_session, test_user):
    from tests.conftest import test_engine

    company, _ = await _seed_applications(db_session, test_user.id, 10)
    with count_queries(test_engine) as small:
        await DashboardService.get_user_dashboard_data(test_user.id, db_session)

    await _seed_applications(db_session, test_user.id, 10_000, company=company)
    with count_queries(test_engine) as large:
        await DashboardService.get_user_dashboard_data(test_user.id, db_session)

    assert small.selects == large.selects
    assert large.writes == 0, "a dashboard read wrote to the database"


@pytest.mark.asyncio
async def test_the_recent_query_asks_for_five_rows_not_the_history(db_session, test_user):
    """The bound is in the SQL, not in a Python slice afterwards."""
    from tests.conftest import test_engine

    await _seed_applications(db_session, test_user.id, 5_000)

    with count_queries(test_engine) as counter:
        rows = await DashboardService._fetch_recent_applications(test_user.id, db_session)

    assert len(rows) == 5
    statements = counter.matching("applications")
    assert statements, counter.statements
    assert any("LIMIT" in statement.upper() for statement in statements)


@pytest.mark.asyncio
async def test_the_counts_never_load_an_application_row(db_session, test_user):
    """The aggregate must be a count, not a select the service then counts."""
    from tests.conftest import test_engine

    await _seed_applications(db_session, test_user.id, 500)

    with count_queries(test_engine) as counter:
        await DashboardService._aggregate_student_application_stats(test_user.id, db_session)

    assert counter.selects == 1
    statement = counter.statements[0].upper()
    assert "COUNT" in statement
    assert "LIMIT" not in statement


# ---------------------------------------------------------------------------
# The payload is unchanged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_dashboard_payload_keeps_its_shape(db_session, test_user):
    await _seed_applications(db_session, test_user.id, 30)

    payload = await DashboardService.get_user_dashboard_data(test_user.id, db_session)

    assert set(payload) == {"stats", "progress", "recent_applications"}
    assert set(payload["stats"]) == {
        "total_applications",
        "in_review",
        "interviews_scheduled",
        "offers_received",
    }
    assert payload["stats"]["total_applications"] == 30
    assert len(payload["recent_applications"]) == 5
    assert set(payload["recent_applications"][0]) == {
        "id",
        "job_title",
        "company_id",
        "status",
        "application_date",
    }


@pytest.mark.asyncio
async def test_the_student_dashboard_keeps_its_notes_and_its_five(db_session, test_user):
    await _seed_applications(db_session, test_user.id, 30)

    payload = await DashboardService.get_student_dashboard(test_user.id, db_session)

    assert payload["stats"]["total_applications"] == 30
    recent = payload["recent_applications"]
    assert len(recent) == 5
    assert "notes" in recent[0], "the student dashboard includes notes; the other does not"


@pytest.mark.asyncio
async def test_a_user_with_no_applications_reports_zeroes(db_session, test_user):
    payload = await DashboardService.get_user_dashboard_data(test_user.id, db_session)

    assert payload["stats"] == {
        "total_applications": 0,
        "in_review": 0,
        "interviews_scheduled": 0,
        "offers_received": 0,
    }
    assert payload["recent_applications"] == []
