"""The analytics constraints, on the engine that enforces them.

SQLite will happily store ``status = 'banana'`` and ``rating = 99``; Pydantic
never sees these writes, because the extraction services build the rows
themselves. So a CHECK is either tested here or it is not tested.

The point of each constraint is the same: today an out-of-range score is
**accepted and then silently reinterpreted**. The optimiser reads every score
through ``_clamp(value, 0.0, 1.0)`` and the rating as ``rating / 5.0`` clamped
the same way, so a stored 9 and a stored 5 are the same five stars and a stored
−3 is the same as 0. The number the product acts on stops being the number that
was stored, and nothing anywhere says so.
"""
from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


@pytest.fixture
def _models():
    import tests.conftest  # noqa: F401

    from app.db import Base

    return Base


@pytest.fixture
async def schema(pg_engine, _models):
    """The mapped schema. ``pg_engine`` hands it over empty (see the lane's
    ``reset_public_schema``), which matters here: every test in this module
    provokes an ``IntegrityError`` on purpose, and an aborted transaction used
    to block the teardown's ``drop_all`` and leave tables behind."""
    async with pg_engine.begin() as conn:
        await conn.run_sync(_models.metadata.create_all)
    yield


def _migration():
    path = Path("alembic/versions/e7c2d940ab15_add_analytics_range_and_status_checks.py")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _skill(session):
    skill_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO skills (id, normalized_name, display_name, source, created_at, updated_at) "
            "VALUES (:id, :name, :name, 'test', now(), now())"
        ),
        {"id": skill_id, "name": f"skill-{skill_id.hex[:8]}"},
    )
    return skill_id


async def _resume(session):
    user_id, resume_id = uuid.uuid4(), uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO users (id, email, hashed_password, is_active, is_superuser, "
            "is_verified, created_at, updated_at) "
            "VALUES (:id, :email, 'x', true, false, true, now(), now())"
        ),
        {"id": user_id, "email": f"c-{user_id.hex[:8]}@example.invalid"},
    )
    await session.execute(
        text(
            "INSERT INTO resumes (id, user_id, view_url, storage_file_id, original_filename, "
            "folder_id, created_at, updated_at) VALUES (:id, :user, 'https://e.invalid/a', :sid, "
            "'cv.pdf', 'resumes', now(), now())"
        ),
        {"id": resume_id, "user": user_id, "sid": uuid.uuid4().hex},
    )
    return user_id, resume_id


async def _course(session, **overrides):
    course_id = uuid.uuid4()
    values = {
        "id": course_id,
        "title": f"Course {course_id.hex[:6]}",
        "provider": "Test",
        "cost": 10.0,
        "duration_hours": 4.0,
        "rating": 4.5,
    }
    values.update(overrides)
    await session.execute(
        text(
            "INSERT INTO courses (id, title, provider, cost, currency, duration_hours, rating, "
            "is_active, created_at, updated_at) VALUES (:id, :title, :provider, :cost, 'CAD', "
            ":duration_hours, :rating, true, now(), now())"
        ),
        values,
    )
    return course_id


# ---------------------------------------------------------------------------
# Valid rows are untouched
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_value_the_product_actually_writes_is_still_accepted(schema, pg_sessionmaker):
    """The constraints must not refuse anything the services produce."""
    async with pg_sessionmaker() as session:
        skill_id = await _skill(session)
        _user_id, resume_id = await _resume(session)

        # The four statuses the service defines, and its default confidence.
        for status in ("detected", "confirmed", "rejected", "manual"):
            await session.execute(
                text(
                    "INSERT INTO resume_skills (id, resume_id, skill_id, confidence_score, "
                    "extraction_method, status, created_at) VALUES (:id, :resume, :skill, 0.75, "
                    ":method, :status, now())"
                ),
                {
                    "id": uuid.uuid4(),
                    "resume": resume_id,
                    "skill": skill_id,
                    "method": f"m-{status}",
                    "status": status,
                },
            )

        # The boundaries, which must be inside the range, not outside it.
        for score in (0.0, 1.0, None):
            await session.execute(
                text(
                    "INSERT INTO job_skills (id, skill_id, importance_score, extraction_method, "
                    "created_at) VALUES (:id, :skill, :score, :method, now())"
                ),
                {
                    "id": uuid.uuid4(),
                    "skill": skill_id,
                    "score": score,
                    "method": f"b-{score}",
                },
            )

        course_id = await _course(session, cost=0.0, duration_hours=0.0, rating=5.0)
        await _course(session, cost=None, duration_hours=None, rating=None)
        await session.execute(
            text(
                "INSERT INTO course_skills (id, course_id, skill_id, coverage_score, "
                "is_prerequisite, created_at) VALUES (:id, :course, :skill, 1.0, false, now())"
            ),
            {"id": uuid.uuid4(), "course": course_id, "skill": skill_id},
        )
        await session.commit()

        assert int(await session.scalar(text("SELECT COUNT(*) FROM resume_skills"))) == 4
        assert int(await session.scalar(text("SELECT COUNT(*) FROM job_skills"))) == 3
        assert int(await session.scalar(text("SELECT COUNT(*) FROM courses"))) == 2


# ---------------------------------------------------------------------------
# Invalid rows are refused
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["banana", "", "DETECTED", "pending"])
async def test_an_undefined_resume_skill_status_is_refused(schema, pg_sessionmaker, status):
    async with pg_sessionmaker() as session:
        skill_id = await _skill(session)
        _user_id, resume_id = await _resume(session)
        await session.commit()

        with pytest.raises(IntegrityError) as raised:
            await session.execute(
                text(
                    "INSERT INTO resume_skills (id, resume_id, skill_id, extraction_method, "
                    "status, created_at) VALUES (:id, :resume, :skill, 'm', :status, now())"
                ),
                {"id": uuid.uuid4(), "resume": resume_id, "skill": skill_id, "status": status},
            )
            await session.commit()
        assert "ck_resume_skills_status" in str(raised.value)
        await session.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("score", [-0.1, 1.1, 42.0, float("nan")])
async def test_a_score_outside_the_fraction_is_refused(schema, pg_sessionmaker, score):
    """Including NaN: ``NaN <= 1`` is false in PostgreSQL, so the range excludes it."""
    async with pg_sessionmaker() as session:
        skill_id = await _skill(session)
        await session.commit()

        with pytest.raises(IntegrityError) as raised:
            await session.execute(
                text(
                    "INSERT INTO job_skills (id, skill_id, importance_score, extraction_method, "
                    "created_at) VALUES (:id, :skill, :score, 'm', now())"
                ),
                {"id": uuid.uuid4(), "skill": skill_id, "score": score},
            )
            await session.commit()
        assert "ck_job_skills_importance_score_fraction" in str(raised.value)
        await session.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("column", "value", "constraint"),
    [
        ("cost", -1.0, "ck_courses_cost_non_negative"),
        ("duration_hours", -0.5, "ck_courses_duration_hours_non_negative"),
        ("rating", 9.0, "ck_courses_rating_five_star"),
        ("rating", -1.0, "ck_courses_rating_five_star"),
    ],
)
async def test_negative_money_time_and_impossible_ratings_are_refused(
    schema, pg_sessionmaker, column, value, constraint
):
    async with pg_sessionmaker() as session:
        with pytest.raises(IntegrityError) as raised:
            await _course(session, **{column: value})
            await session.commit()
        assert constraint in str(raised.value)
        await session.rollback()


@pytest.mark.asyncio
async def test_a_coverage_score_outside_the_fraction_is_refused(schema, pg_sessionmaker):
    async with pg_sessionmaker() as session:
        skill_id = await _skill(session)
        course_id = await _course(session)
        await session.commit()

        with pytest.raises(IntegrityError) as raised:
            await session.execute(
                text(
                    "INSERT INTO course_skills (id, course_id, skill_id, coverage_score, "
                    "is_prerequisite, created_at) VALUES (:id, :course, :skill, 3.0, false, now())"
                ),
                {"id": uuid.uuid4(), "course": course_id, "skill": skill_id},
            )
            await session.commit()
        assert "ck_course_skills_coverage_score_fraction" in str(raised.value)
        await session.rollback()


@pytest.mark.asyncio
async def test_a_confidence_score_outside_the_fraction_is_refused(schema, pg_sessionmaker):
    async with pg_sessionmaker() as session:
        skill_id = await _skill(session)
        _user_id, resume_id = await _resume(session)
        await session.commit()

        with pytest.raises(IntegrityError) as raised:
            await session.execute(
                text(
                    "INSERT INTO resume_skills (id, resume_id, skill_id, confidence_score, "
                    "extraction_method, status, created_at) VALUES (:id, :resume, :skill, 5.0, "
                    "'m', 'detected', now())"
                ),
                {"id": uuid.uuid4(), "resume": resume_id, "skill": skill_id},
            )
            await session.commit()
        assert "ck_resume_skills_confidence_score_fraction" in str(raised.value)
        await session.rollback()


# ---------------------------------------------------------------------------
# The migration inventories rather than deletes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_inventory_counts_violations_without_touching_them(
    schema, pg_engine, pg_sessionmaker
):
    """Bad rows are reported and left in place; the operator decides, not the migration."""
    migration = _migration()

    # Drop the constraints so bad rows can be written, as they could before.
    async with pg_engine.begin() as conn:
        for table, name, _predicate in migration.CHECKS:
            await conn.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}"))

    async with pg_sessionmaker() as session:
        skill_id = await _skill(session)
        _user_id, resume_id = await _resume(session)
        await session.execute(
            text(
                "INSERT INTO resume_skills (id, resume_id, skill_id, confidence_score, "
                "extraction_method, status, created_at) VALUES (:id, :resume, :skill, 7.0, 'm', "
                "'banana', now())"
            ),
            {"id": uuid.uuid4(), "resume": resume_id, "skill": skill_id},
        )
        await _course(session, rating=99.0, cost=-5.0)
        await session.commit()

    async with pg_engine.begin() as conn:
        findings = await conn.run_sync(lambda c: migration.inventory(c))

    by_constraint = {finding["constraint"]: finding["violations"] for finding in findings}
    assert by_constraint["ck_resume_skills_status"] == 1
    assert by_constraint["ck_resume_skills_confidence_score_fraction"] == 1
    assert by_constraint["ck_courses_rating_five_star"] == 1
    assert by_constraint["ck_courses_cost_non_negative"] == 1
    assert by_constraint["ck_job_skills_importance_score_fraction"] == 0

    # And the rows are still there: nothing was deleted or rewritten.
    async with pg_sessionmaker() as reader:
        assert int(await reader.scalar(text("SELECT COUNT(*) FROM resume_skills"))) == 1
        assert (
            await reader.scalar(text("SELECT status FROM resume_skills LIMIT 1"))
        ) == "banana"
        assert float(await reader.scalar(text("SELECT rating FROM courses LIMIT 1"))) == 99.0


@pytest.mark.asyncio
async def test_the_upgrade_refuses_to_create_a_constraint_over_bad_rows(
    schema, pg_engine, pg_sessionmaker
):
    """Loudly, rather than quietly repairing the data to fit."""
    async with pg_engine.begin() as conn:
        await conn.execute(
            text("ALTER TABLE courses DROP CONSTRAINT IF EXISTS ck_courses_rating_five_star")
        )

    async with pg_sessionmaker() as session:
        await _course(session, rating=99.0)
        await session.commit()

    with pytest.raises(Exception) as raised:
        async with pg_engine.begin() as conn:
            await conn.execute(
                text(
                    "ALTER TABLE courses ADD CONSTRAINT ck_courses_rating_five_star "
                    "CHECK (rating IS NULL OR (rating >= 0 AND rating <= 5))"
                )
            )
    assert "ck_courses_rating_five_star" in str(raised.value) or "check constraint" in str(
        raised.value
    ).lower()


@pytest.mark.asyncio
async def test_the_migration_is_reentrant(schema, pg_engine):
    """Running it over a database that already has the constraints is a no-op."""
    migration = _migration()
    async with pg_engine.connect() as conn:
        present = await conn.run_sync(
            lambda c: {
                name
                for table in {table for table, _n, _p in migration.CHECKS}
                for name in migration._constraints(c, table)
            }
        )
    for _table, name, _predicate in migration.CHECKS:
        assert name in present, f"{name} is missing from the created schema"
