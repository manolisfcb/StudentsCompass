"""Listing a user's course progress costs the same whether there are 1 or 100 courses.

``list_user_enrollment_progress`` used to ask the projector once per resource,
so the admin panel's per-user progress view issued at least two statements per
course, plus one more for every course carrying a ``resume_upload`` lesson. The
projector was already batch-capable — ``completed_lesson_ids`` takes a list of
resource ids — so the N+1 was in the caller, not in the projection.

These tests pin the *shape* of the cost (constant, not linear) and the fact
that batching did not change a single byte of the payload. They compare against
the per-resource projector rather than against a hard-coded payload, so they
keep testing the invariant TASK-016 established: one projection of progress,
for every screen.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from app.models.resourceModel import (
    ResourceLessonModel,
    ResourceLessonProgressModel,
    ResourceModel,
    ResourceModuleModel,
)
from app.services.resources.resourceService import ResourceService
from tests.harness import count_queries


async def _seed_course(session, *, title, lesson_types, modules=1):
    """A published course with ``modules`` modules of ``lesson_types`` each."""
    resource = ResourceModel(
        id=uuid.uuid4(),
        title=title,
        description="Course.",
        category="Career",
        is_published=True,
    )
    session.add(resource)
    await session.flush()
    lessons = []
    for module_position in range(1, modules + 1):
        module = ResourceModuleModel(
            id=uuid.uuid4(),
            resource_id=resource.id,
            title=f"Module {module_position}",
            position=module_position,
        )
        session.add(module)
        await session.flush()
        for position, content_type in enumerate(lesson_types, start=1):
            lesson = ResourceLessonModel(
                id=uuid.uuid4(),
                module_id=module.id,
                title=f"Lesson {module_position}.{position}",
                position=position,
                content_type=content_type,
                content="body",
            )
            session.add(lesson)
            lessons.append(lesson)
    await session.commit()
    return resource, lessons


async def _complete(session, user_id, lesson):
    session.add(
        ResourceLessonProgressModel(
            id=uuid.uuid4(),
            user_id=user_id,
            lesson_id=lesson.id,
            completed_at=datetime.utcnow(),
        )
    )
    await session.commit()


async def _seed_courses(session, count, *, with_resume_upload=False):
    seeded = []
    for index in range(count):
        lesson_types = ["text", "video"]
        if with_resume_upload:
            lesson_types = ["text", "resume_upload"]
        seeded.append(
            await _seed_course(session, title=f"Course {index}", lesson_types=lesson_types)
        )
    return seeded


async def _count_listing(session, engine, user_id):
    service = ResourceService(session)
    with count_queries(engine) as counter:
        payload = await service.list_user_enrollment_progress(user_id)
    return payload, counter


@pytest.mark.asyncio
async def test_the_number_of_selects_does_not_grow_with_the_number_of_courses(
    db_session, test_user
):
    """1, 10 and 100 courses cost the same number of statements."""
    from tests.conftest import test_engine

    await _seed_courses(db_session, 1)
    _payload, one = await _count_listing(db_session, test_engine, test_user.id)

    await _seed_courses(db_session, 9)
    _payload, ten = await _count_listing(db_session, test_engine, test_user.id)

    await _seed_courses(db_session, 90)
    payload, hundred = await _count_listing(db_session, test_engine, test_user.id)

    assert len(payload) == 100
    assert one.selects == ten.selects == hundred.selects, (
        f"1 course: {one.selects} selects, 10: {ten.selects}, 100: {hundred.selects}"
    )
    # Catalogue+outline, lessons, progress rows. No approval check: no course
    # here carries a resume_upload lesson.
    assert hundred.selects <= 5
    assert hundred.writes == 0


@pytest.mark.asyncio
async def test_the_cv_approval_is_checked_once_for_the_whole_listing(db_session, test_user):
    """A resume_upload lesson in every course still costs one approval check."""
    from tests.conftest import test_engine

    await _seed_courses(db_session, 20, with_resume_upload=True)
    _payload, counter = await _count_listing(db_session, test_engine, test_user.id)

    approval_checks = counter.matching("resume_course_evaluations")
    assert len(approval_checks) == 1, f"{len(approval_checks)} approval checks"
    assert counter.selects <= 6


@pytest.mark.asyncio
async def test_the_batched_listing_says_exactly_what_the_per_resource_projector_says(
    db_session, test_user
):
    """Same payload, course by course, as asking the projector one at a time."""
    seeded = await _seed_courses(db_session, 5)
    # A partially finished course, a finished one and untouched ones.
    await _complete(db_session, test_user.id, seeded[0][1][0])
    await _complete(db_session, test_user.id, seeded[1][1][0])
    await _complete(db_session, test_user.id, seeded[1][1][1])

    service = ResourceService(db_session)
    batched = await service.list_user_enrollment_progress(test_user.id)

    expected = []
    for resource, _lessons in seeded:
        outline = await service.get_published_resource(resource.id, include_locked=True)
        completed = await service.get_completed_lesson_ids_for_resource(
            resource.id, test_user.id
        )
        expected.append(service.to_progress_payload(outline, completed))

    by_id = {item["resource_id"]: item for item in batched}
    assert set(by_id) == {item["resource_id"] for item in expected}
    for item in expected:
        assert by_id[item["resource_id"]] == item


@pytest.mark.asyncio
async def test_the_listing_keeps_its_newest_first_order(db_session, test_user):
    """Order is part of the contract; batching must not reshuffle it."""
    from sqlalchemy import select

    await _seed_courses(db_session, 4)
    service = ResourceService(db_session)
    payload = await service.list_user_enrollment_progress(test_user.id)

    rows = await db_session.execute(
        select(ResourceModel.id).order_by(ResourceModel.created_at.desc())
    )
    assert [item["resource_id"] for item in payload] == [str(row[0]) for row in rows.all()]


@pytest.mark.asyncio
async def test_a_user_with_no_courses_at_all_costs_nothing_extra(db_session, test_user):
    """No resources means no projector round trip."""
    from tests.conftest import test_engine

    payload, counter = await _count_listing(db_session, test_engine, test_user.id)

    assert payload == []
    assert counter.selects <= 2
    assert counter.writes == 0
