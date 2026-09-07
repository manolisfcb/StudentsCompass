"""One projection of course progress, from the facts, for every screen.

The facts are ``resource_lesson_progress`` rows and approved resume
evaluations. Everything else — ``user_stats``, the dashboard's percentages, the
course page's ring — is a projection of those, and used to be computed twice:

* the resources hub completed a ``resume_upload`` lesson whenever an approved
  evaluation existed;
* the dashboard counted progress rows only, in raw SQL keyed on the course
  *title*, so the same user saw the lesson finished on one screen and missing on
  the other.

Courses are identified by ``resources.core_code``, a stable identifier, rather
than by a title an admin can edit.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resourceModel import (
    ResourceLessonModel,
    ResourceLessonProgressModel,
    ResourceModuleModel,
    ResourceModel,
)
from app.services.learning.resumeApproval import has_approved_resume

#: Lessons of this type are not marked done by hand; an approved resume audit
#: completes them. See ``CourseProgressProjector.completed_lesson_ids``.
RESUME_UPLOAD_CONTENT_TYPE = "resume_upload"


@dataclass(frozen=True)
class CoreCourse:
    """A course the product treats as mandatory.

    ``key`` is part of the dashboard payload and must not change. ``code`` is
    what identifies the row in the database. ``seed_title`` is only how the
    course was originally seeded, kept for the backfill and for deployments
    whose rows predate the code.
    """

    key: str
    code: str
    seed_title: str


CORE_COURSES: tuple[CoreCourse, ...] = (
    CoreCourse(key="resume", code="resume_templates", seed_title="Resume Templates"),
    CoreCourse(key="linkedin", code="linkedin_optimization", seed_title="LinkedIn Optimization"),
    CoreCourse(key="interview_prep", code="interview_preparation", seed_title="Interview Preparation"),
)

CORE_COURSE_CODES: tuple[str, ...] = tuple(course.code for course in CORE_COURSES)
CORE_COURSE_BY_CODE: dict[str, CoreCourse] = {course.code: course for course in CORE_COURSES}
#: Titles the seed data used. Only the backfill and the parity report read this.
CORE_COURSE_SEED_TITLES: tuple[str, ...] = tuple(course.seed_title for course in CORE_COURSES)


def percent(completed: int, total: int) -> int:
    """Rounded percentage; an empty course is 0, never a division by zero."""
    if total <= 0:
        return 0
    return round((completed / total) * 100)


@dataclass(frozen=True)
class CourseCompletion:
    """How much of one course a user has finished."""

    resource_id: UUID
    completed_lessons: int
    total_lessons: int

    @property
    def percent(self) -> int:
        return percent(self.completed_lessons, self.total_lessons)


class CourseProgressProjector:
    """Reads facts, answers "what is done?". Never writes.

    A projection that repaired a cache on read would turn every page view into a
    write and hide the drift instead of reporting it, so every method here is
    read-only.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _lessons_of(self, resource_ids: list[UUID]) -> list[tuple[UUID, UUID, str]]:
        """(lesson_id, resource_id, content_type) for the given courses, one query."""
        if not resource_ids:
            return []
        result = await self.session.execute(
            select(
                ResourceLessonModel.id,
                ResourceModuleModel.resource_id,
                ResourceLessonModel.content_type,
            )
            .join(ResourceModuleModel, ResourceModuleModel.id == ResourceLessonModel.module_id)
            .where(ResourceModuleModel.resource_id.in_(resource_ids))
        )
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def _recorded_progress(self, user_id: UUID, lesson_ids: list[UUID]) -> set[UUID]:
        """Lessons this user has an explicit progress row for, one query."""
        if not lesson_ids:
            return set()
        result = await self.session.execute(
            select(ResourceLessonProgressModel.lesson_id).where(
                ResourceLessonProgressModel.user_id == user_id,
                ResourceLessonProgressModel.lesson_id.in_(lesson_ids),
            )
        )
        return {row[0] for row in result.all()}

    async def completed_lesson_ids(
        self, *, user_id: UUID, resource_ids: list[UUID]
    ) -> dict[UUID, set[UUID]]:
        """Completed lessons per course, including the ones completed by audit.

        Constant in the number of queries regardless of how many courses are
        asked for: lessons, progress rows, and — only when a ``resume_upload``
        lesson is actually among them — one existence check on the evaluations.
        """
        lessons = await self._lessons_of(resource_ids)
        if not lessons:
            return {resource_id: set() for resource_id in resource_ids}

        recorded = await self._recorded_progress(user_id, [lesson_id for lesson_id, _, _ in lessons])

        resume_upload_lessons = [
            (lesson_id, resource_id)
            for lesson_id, resource_id, content_type in lessons
            if content_type == RESUME_UPLOAD_CONTENT_TYPE
        ]
        approved = False
        if resume_upload_lessons:
            try:
                approved = await has_approved_resume(self.session, user_id)
            except ProgrammingError as exc:
                # A deployment mid-rollout may not have the evaluations table
                # yet. Nothing is approved there, which is the safe answer.
                if "resume_course_evaluations" not in str(exc):
                    raise

        completed: dict[UUID, set[UUID]] = {resource_id: set() for resource_id in resource_ids}
        for lesson_id, resource_id, content_type in lessons:
            if content_type == RESUME_UPLOAD_CONTENT_TYPE:
                # An explicit row does not complete an upload lesson: the audit
                # does. Otherwise a stale row would keep the lesson finished
                # after the approved CV was deleted.
                if approved:
                    completed.setdefault(resource_id, set()).add(lesson_id)
            elif lesson_id in recorded:
                completed.setdefault(resource_id, set()).add(lesson_id)
        return completed

    async def completion_of(self, *, user_id: UUID, resource_ids: list[UUID]) -> dict[UUID, CourseCompletion]:
        """Completed/total per course, from the same facts as the lesson view."""
        lessons = await self._lessons_of(resource_ids)
        totals: dict[UUID, int] = {resource_id: 0 for resource_id in resource_ids}
        for _, resource_id, _ in lessons:
            totals[resource_id] = totals.get(resource_id, 0) + 1

        completed = await self.completed_lesson_ids(user_id=user_id, resource_ids=resource_ids)
        return {
            resource_id: CourseCompletion(
                resource_id=resource_id,
                completed_lessons=len(completed.get(resource_id, set())),
                total_lessons=totals.get(resource_id, 0),
            )
            for resource_id in resource_ids
        }

    async def resolve_core_courses(self) -> dict[str, UUID]:
        """Map each core course key to its published resource id, by code.

        Rows seeded before ``core_code`` existed are matched on their seed title
        as a documented fallback; the backfill fills the column in, and
        :func:`core_course_code_inventory` reports what is still unmatched. A
        course with no row at all is simply absent from the result.
        """
        result = await self.session.execute(
            select(ResourceModel.id, ResourceModel.core_code, ResourceModel.title).where(
                ResourceModel.is_published.is_(True)
            )
        )
        rows = result.all()
        by_code = {row[1]: row[0] for row in rows if row[1]}

        titles: dict[str, list[UUID]] = {}
        for resource_id, _code, title in rows:
            titles.setdefault((title or "").strip(), []).append(resource_id)

        resolved: dict[str, UUID] = {}
        for course in CORE_COURSES:
            if course.code in by_code:
                resolved[course.key] = by_code[course.code]
                continue
            # Fallback only when the title match is unambiguous: two courses
            # sharing a title cannot tell us which one is the core one.
            candidates = titles.get(course.seed_title, [])
            if len(candidates) == 1:
                resolved[course.key] = candidates[0]
        return resolved

    async def core_course_progress(self, user_id: UUID) -> dict[str, int]:
        """Percentage per core course key, or ``{}`` when no core course has content.

        The empty result is what tells the dashboard to fall back to its legacy
        numbers instead of reporting a confident 0% for courses that were never
        seeded.
        """
        resolved = await self.resolve_core_courses()
        if not resolved:
            return {}

        completion = await self.completion_of(user_id=user_id, resource_ids=list(resolved.values()))
        if not any(item.total_lessons > 0 for item in completion.values()):
            return {}
        return {key: completion[resource_id].percent for key, resource_id in resolved.items()}


async def core_course_code_inventory(session: AsyncSession) -> list[dict]:
    """What each core course currently resolves to, and how.

    Evidence for the switch from title to code: it names the rows that carry the
    code, the ones still matched by title, and the ones that match nothing.
    """
    result = await session.execute(
        select(ResourceModel.id, ResourceModel.core_code, ResourceModel.title, ResourceModel.is_published)
    )
    rows = result.all()
    inventory = []
    for course in CORE_COURSES:
        coded = [row[0] for row in rows if row[1] == course.code]
        titled = [row[0] for row in rows if (row[2] or "").strip() == course.seed_title]
        inventory.append(
            {
                "key": course.key,
                "code": course.code,
                "seed_title": course.seed_title,
                "resources_with_code": coded,
                "resources_with_seed_title": titled,
                "matched_by": "code" if coded else ("title" if len(titled) == 1 else "nothing"),
            }
        )
    return inventory
