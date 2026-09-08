"""One answer to "is this CV approved?" and one to "how much is done?".

Both used to be computed in several places. The resources hub completed a
``resume_upload`` lesson on ``pass_status`` alone, the dashboard counted
progress rows in raw SQL keyed on the course title, and application eligibility
checked the score as well. So the same user could see a lesson finished on the
course page, missing on the dashboard, and be refused when attaching the CV.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select

from app.models.resourceModel import (
    ResourceLessonModel,
    ResourceLessonProgressModel,
    ResourceModel,
    ResourceModuleModel,
)
from app.models.resumeCourseEvaluationModel import (
    ResumeCourseEvaluationModel,
    ResumeCourseEvaluationStatus,
)
from app.models.resumeModel import ResumeModel
from app.models.userStatsModel import UserStatsModel
from app.services.applications.dashboardService import DashboardService
from app.services.learning.courseProgress import (
    CORE_COURSES,
    CourseProgressProjector,
    core_course_code_inventory,
)
from app.services.learning.resumeApproval import (
    RESUME_APPROVAL_MIN_SCORE,
    has_approved_resume,
    is_passing_score,
)
from app.services.resources.resourceService import ResourceService
from tests.harness import count_queries


async def _seed_course(session, *, core_code, title, lesson_types):
    resource = ResourceModel(
        id=uuid.uuid4(),
        core_code=core_code,
        title=title,
        description="Course.",
        category="Career",
        is_published=True,
    )
    session.add(resource)
    await session.flush()
    module = ResourceModuleModel(
        id=uuid.uuid4(), resource_id=resource.id, title="Module", position=1
    )
    session.add(module)
    await session.flush()
    lessons = []
    for position, content_type in enumerate(lesson_types, start=1):
        lesson = ResourceLessonModel(
            id=uuid.uuid4(),
            module_id=module.id,
            title=f"Lesson {position}",
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


async def _evaluate(session, user_id, *, score, pass_status=None, status=None):
    resume = ResumeModel(
        id=uuid.uuid4(),
        user_id=user_id,
        view_url=f"https://example.invalid/{uuid.uuid4().hex}",
        storage_file_id=uuid.uuid4().hex,
        original_filename="cv.pdf",
        folder_id="resumes",
    )
    session.add(resume)
    await session.flush()
    evaluation = ResumeCourseEvaluationModel(
        id=uuid.uuid4(),
        user_id=user_id,
        resume_id=resume.id,
        status=status or ResumeCourseEvaluationStatus.COMPLETED,
        overall_score=score,
        pass_status=is_passing_score(score) if pass_status is None else pass_status,
        completed_at=datetime.utcnow(),
    )
    session.add(evaluation)
    await session.commit()
    return resume, evaluation


# ---------------------------------------------------------------------------
# The approval rule
# ---------------------------------------------------------------------------


def test_the_threshold_is_stated_once_and_is_still_eight():
    from app.services.applications.applicationService import ApplicationService

    assert RESUME_APPROVAL_MIN_SCORE == 8.0
    assert ApplicationService.MIN_APPROVED_RESUME_SCORE == RESUME_APPROVAL_MIN_SCORE


@pytest.mark.parametrize(
    ("score", "expected"),
    [(None, False), (0, False), (7.99, False), (8, True), (8.0, True), (10, True)],
)
def test_scores_either_clear_the_bar_or_do_not(score, expected):
    assert is_passing_score(score) is expected


@pytest.mark.asyncio
async def test_a_stored_pass_flag_cannot_outvote_a_failing_score(db_session, test_user):
    """A historical row flagged as passing at 7.5 is not an approval."""
    await _evaluate(db_session, test_user.id, score=7.5, pass_status=True)

    assert await has_approved_resume(db_session, test_user.id) is False


@pytest.mark.asyncio
async def test_an_unfinished_evaluation_is_not_an_approval(db_session, test_user):
    await _evaluate(
        db_session,
        test_user.id,
        score=9.0,
        status=ResumeCourseEvaluationStatus.PENDING,
    )

    assert await has_approved_resume(db_session, test_user.id) is False


# ---------------------------------------------------------------------------
# One projection for both screens
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_course_page_and_dashboard_report_the_same_percentage(db_session, test_user):
    resume_course, lessons = await _seed_course(
        db_session,
        core_code="resume_templates",
        title="Resume Templates",
        lesson_types=["text", "text", "resume_upload", "text"],
    )
    await _complete(db_session, test_user.id, lessons[0])
    await _evaluate(db_session, test_user.id, score=9.0)

    service = ResourceService(db_session)
    page = await service.get_resource_progress(resource_id=resume_course.id, user_id=test_user.id)
    dashboard = await DashboardService._get_core_resource_progress(test_user.id, db_session)

    # One text lesson done plus the upload lesson the audit completed: 2 of 4.
    assert page["completed_lessons"] == 2
    assert page["progress_percent"] == 50
    assert dashboard["resume"] == 50


@pytest.mark.asyncio
async def test_an_approved_audit_completes_the_upload_lesson_on_both_screens(db_session, test_user):
    resume_course, lessons = await _seed_course(
        db_session,
        core_code="resume_templates",
        title="Resume Templates",
        lesson_types=["resume_upload", "text"],
    )
    await _complete(db_session, test_user.id, lessons[1])

    service = ResourceService(db_session)
    before = await service.get_resource_progress(resource_id=resume_course.id, user_id=test_user.id)
    assert before["progress_percent"] == 50
    assert (await DashboardService._get_core_resource_progress(test_user.id, db_session))["resume"] == 50

    await _evaluate(db_session, test_user.id, score=8.0)

    after = await service.get_resource_progress(resource_id=resume_course.id, user_id=test_user.id)
    assert after["progress_percent"] == 100
    assert (await DashboardService._get_core_resource_progress(test_user.id, db_session))["resume"] == 100


@pytest.mark.asyncio
async def test_a_score_just_under_the_bar_completes_nothing(db_session, test_user):
    resume_course, _lessons = await _seed_course(
        db_session,
        core_code="resume_templates",
        title="Resume Templates",
        lesson_types=["resume_upload"],
    )
    await _evaluate(db_session, test_user.id, score=7.99)

    service = ResourceService(db_session)
    progress = await service.get_resource_progress(resource_id=resume_course.id, user_id=test_user.id)

    assert progress["progress_percent"] == 0
    assert (await DashboardService._get_core_resource_progress(test_user.id, db_session))["resume"] == 0


@pytest.mark.asyncio
async def test_the_best_of_several_evaluations_decides(db_session, test_user):
    """A failed attempt followed by a passing one is an approval."""
    resume_course, _lessons = await _seed_course(
        db_session,
        core_code="resume_templates",
        title="Resume Templates",
        lesson_types=["resume_upload"],
    )
    await _evaluate(db_session, test_user.id, score=4.0)
    await _evaluate(db_session, test_user.id, score=8.5)
    await _evaluate(db_session, test_user.id, score=6.0)

    service = ResourceService(db_session)
    progress = await service.get_resource_progress(resource_id=resume_course.id, user_id=test_user.id)
    assert progress["progress_percent"] == 100


@pytest.mark.asyncio
async def test_deleting_the_approved_cv_uncompletes_the_lesson(db_session, test_user):
    """Evaluations cascade with the resume, so the fact stops being true."""
    resume_course, _lessons = await _seed_course(
        db_session,
        core_code="resume_templates",
        title="Resume Templates",
        lesson_types=["resume_upload"],
    )
    resume, _evaluation = await _evaluate(db_session, test_user.id, score=9.0)

    service = ResourceService(db_session)
    assert (await service.get_resource_progress(resource_id=resume_course.id, user_id=test_user.id))[
        "progress_percent"
    ] == 100

    await db_session.delete(resume)
    await db_session.commit()

    assert (await service.get_resource_progress(resource_id=resume_course.id, user_id=test_user.id))[
        "progress_percent"
    ] == 0
    assert (await DashboardService._get_core_resource_progress(test_user.id, db_session))["resume"] == 0


@pytest.mark.asyncio
async def test_a_stale_progress_row_does_not_keep_an_upload_lesson_finished(db_session, test_user):
    """The audit decides upload lessons; a leftover row must not override it."""
    resume_course, lessons = await _seed_course(
        db_session,
        core_code="resume_templates",
        title="Resume Templates",
        lesson_types=["resume_upload"],
    )
    await _complete(db_session, test_user.id, lessons[0])

    service = ResourceService(db_session)
    progress = await service.get_resource_progress(resource_id=resume_course.id, user_id=test_user.id)
    assert progress["progress_percent"] == 0


# ---------------------------------------------------------------------------
# Identity by code, not by title
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_renaming_a_course_does_not_zero_its_progress(db_session, test_user):
    resume_course, lessons = await _seed_course(
        db_session,
        core_code="resume_templates",
        title="Resume Templates",
        lesson_types=["text", "text"],
    )
    await _complete(db_session, test_user.id, lessons[0])
    assert (await DashboardService._get_core_resource_progress(test_user.id, db_session))["resume"] == 50

    resume_course.title = "Resume Templates (2026 edition)"
    await db_session.commit()

    assert (await DashboardService._get_core_resource_progress(test_user.id, db_session))["resume"] == 50


@pytest.mark.asyncio
async def test_a_course_without_a_code_is_still_found_by_its_seeded_title(db_session, test_user):
    """Deployments whose rows predate the backfill keep working."""
    _course, lessons = await _seed_course(
        db_session,
        core_code=None,
        title="Resume Templates",
        lesson_types=["text", "text"],
    )
    await _complete(db_session, test_user.id, lessons[0])

    projector = CourseProgressProjector(db_session)
    assert "resume" in await projector.resolve_core_courses()
    assert (await projector.core_course_progress(test_user.id))["resume"] == 50

    inventory = await core_course_code_inventory(db_session)
    resume_entry = next(item for item in inventory if item["key"] == "resume")
    assert resume_entry["matched_by"] == "title"


@pytest.mark.asyncio
async def test_two_courses_sharing_a_title_resolve_to_neither(db_session, test_user):
    """An ambiguous title cannot say which row is the core course."""
    await _seed_course(
        db_session, core_code=None, title="Resume Templates", lesson_types=["text"]
    )
    await _seed_course(
        db_session, core_code=None, title="Resume Templates", lesson_types=["text"]
    )

    projector = CourseProgressProjector(db_session)
    assert "resume" not in await projector.resolve_core_courses()

    inventory = await core_course_code_inventory(db_session)
    resume_entry = next(item for item in inventory if item["key"] == "resume")
    assert resume_entry["matched_by"] == "nothing"


@pytest.mark.asyncio
async def test_the_code_wins_over_a_row_that_merely_shares_the_title(db_session, test_user):
    coded, coded_lessons = await _seed_course(
        db_session,
        core_code="resume_templates",
        title="Resume Fundamentals",
        lesson_types=["text", "text"],
    )
    await _seed_course(
        db_session, core_code=None, title="Resume Templates", lesson_types=["text"]
    )
    await _complete(db_session, test_user.id, coded_lessons[0])

    projector = CourseProgressProjector(db_session)
    assert (await projector.resolve_core_courses())["resume"] == coded.id
    assert (await projector.core_course_progress(test_user.id))["resume"] == 50


# ---------------------------------------------------------------------------
# Parity with the replaced implementation, and no writes on a read
# ---------------------------------------------------------------------------


async def _legacy_core_progress(session, user_id):
    """The replaced computation: progress rows only, keyed on the title.

    Kept here as the parity reference for the switch — not as production code.
    """
    from sqlalchemy import func

    percentages = {}
    for course in CORE_COURSES:
        total = await session.scalar(
            select(func.count(ResourceLessonModel.id))
            .join(ResourceModuleModel, ResourceModuleModel.id == ResourceLessonModel.module_id)
            .join(ResourceModel, ResourceModel.id == ResourceModuleModel.resource_id)
            .where(ResourceModel.title == course.seed_title, ResourceModel.is_published.is_(True))
        )
        done = await session.scalar(
            select(func.count(ResourceLessonProgressModel.id))
            .join(ResourceLessonModel, ResourceLessonModel.id == ResourceLessonProgressModel.lesson_id)
            .join(ResourceModuleModel, ResourceModuleModel.id == ResourceLessonModel.module_id)
            .join(ResourceModel, ResourceModel.id == ResourceModuleModel.resource_id)
            .where(
                ResourceLessonProgressModel.user_id == user_id,
                ResourceModel.title == course.seed_title,
                ResourceModel.is_published.is_(True),
            )
        )
        percentages[course.key] = 0 if not total else round((done / total) * 100)
    return percentages


@pytest.mark.asyncio
async def test_parity_with_the_legacy_computation_when_no_audit_is_involved(db_session, test_user):
    """Without a resume_upload lesson the two agree exactly — the switch is safe."""
    for course in CORE_COURSES:
        _resource, lessons = await _seed_course(
            db_session,
            core_code=course.code,
            title=course.seed_title,
            lesson_types=["text", "text", "text", "text"],
        )
        await _complete(db_session, test_user.id, lessons[0])
        if course.key == "linkedin":
            await _complete(db_session, test_user.id, lessons[1])

    legacy = await _legacy_core_progress(db_session, test_user.id)
    projected = await DashboardService._get_core_resource_progress(test_user.id, db_session)

    assert projected == legacy
    assert legacy == {"resume": 25, "linkedin": 50, "interview_prep": 25}


@pytest.mark.asyncio
async def test_the_legacy_computation_is_the_one_that_was_wrong(db_session, test_user):
    """Where they differ, the audit is the reason — and the new answer is right."""
    _resource, lessons = await _seed_course(
        db_session,
        core_code="resume_templates",
        title="Resume Templates",
        lesson_types=["text", "resume_upload"],
    )
    await _complete(db_session, test_user.id, lessons[0])
    await _evaluate(db_session, test_user.id, score=9.0)

    legacy = await _legacy_core_progress(db_session, test_user.id)
    projected = await DashboardService._get_core_resource_progress(test_user.id, db_session)

    assert legacy["resume"] == 50  # blind to the approved audit
    assert projected["resume"] == 100


@pytest.mark.asyncio
async def test_reading_the_dashboard_writes_nothing(db_session, test_user):
    from tests.conftest import test_engine

    await _seed_course(
        db_session,
        core_code="resume_templates",
        title="Resume Templates",
        lesson_types=["text"],
    )

    with count_queries(test_engine) as counter:
        await DashboardService._project_student_progress(test_user.id, db_session)

    assert counter.writes == 0
    assert await db_session.scalar(
        select(UserStatsModel).where(UserStatsModel.user_id == test_user.id)
    ) is None


@pytest.mark.asyncio
async def test_without_any_core_course_the_legacy_numbers_are_read_not_written(db_session, test_user):
    from tests.conftest import test_engine

    db_session.add(
        UserStatsModel(
            id=uuid.uuid4(),
            user_id=test_user.id,
            resume_progress=65,
            linkedin_progress=40,
            interview_progress=25,
        )
    )
    await db_session.commit()

    with count_queries(test_engine) as counter:
        progress = await DashboardService._project_student_progress(test_user.id, db_session)

    assert progress["resume"] == 65
    assert progress["linkedin"] == 40
    assert progress["interview_prep"] == 25
    assert progress["overall"] == round((65 + 40 + 25) / 3, 1)
    assert counter.writes == 0


@pytest.mark.asyncio
async def test_projecting_many_courses_stays_a_constant_number_of_queries(db_session, test_user):
    from tests.conftest import test_engine

    for course in CORE_COURSES:
        await _seed_course(
            db_session,
            core_code=course.code,
            title=course.seed_title,
            lesson_types=["text", "text", "resume_upload"],
        )

    with count_queries(test_engine) as counter:
        await DashboardService._get_core_resource_progress(test_user.id, db_session)

    # resolve courses, lessons, progress rows, lessons again for the totals,
    # progress rows again, and one approval check: constant in the number of
    # courses, which is what the N+1 budget is about.
    assert counter.selects <= 6


# ---------------------------------------------------------------------------
# The roadmap stage cache stays separate — and stays out of GETs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reading_a_roadmap_does_not_write_its_stage_cache(db_session, test_user):
    """``user_stage_progress`` is a projection written on mutation, never on a read.

    Verified rather than assumed: this task moves course progress off a
    write-on-read cache, and the roadmap cache is deliberately *not* merged into
    it, so the property it already had has to be pinned somewhere.
    """
    from tests.conftest import test_engine

    from app.models.roadmapModel import (
        RoadmapModel,
        RoadmapStageModel,
        StageTaskModel,
        TaskType,
    )
    from app.services.roadmaps.roadmapService import RoadmapService

    roadmap = RoadmapModel(
        id=uuid.uuid4(),
        slug=f"backend-{uuid.uuid4().hex[:6]}",
        title="Backend",
        description="A roadmap.",
        role_target="Backend Engineer",
        difficulty="beginner",
        duration_weeks_min=4,
        duration_weeks_max=8,
    )
    db_session.add(roadmap)
    await db_session.flush()
    stage = RoadmapStageModel(
        id=uuid.uuid4(),
        roadmap_id=roadmap.id,
        order_index=1,
        title="Foundations",
        objective="Learn the basics.",
        duration_weeks=2,
    )
    db_session.add(stage)
    await db_session.flush()
    db_session.add(
        StageTaskModel(
            id=uuid.uuid4(),
            stage_id=stage.id,
            order_index=1,
            title="Learn HTTP",
            description="Read the spec.",
            estimated_hours=4,
            task_type=TaskType.READ,
        )
    )
    await db_session.commit()

    service = RoadmapService(db_session)
    with count_queries(test_engine) as counter:
        await service.get_roadmap_detail(user_id=test_user.id, slug=roadmap.slug)

    assert counter.writes == 0, counter.statements
