from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.skillModel import CourseModel, CourseSkillModel


async def load_active_course_links(
    session: AsyncSession,
    skill_ids: list[str],
) -> list[tuple[CourseModel, list[CourseSkillModel]]]:
    """Load active courses that cover any of ``skill_ids``.

    Returns ``(course, links)`` pairs grouped by course, where ``links`` are the
    ``CourseSkillModel`` rows tying that course to the requested skills. Callers
    build their own payload shape on top of this so the shared query and the
    ``is_active`` filter live in one place.
    """
    if not skill_ids:
        return []

    result = await session.execute(
        select(CourseSkillModel)
        .options(
            selectinload(CourseSkillModel.course),
            selectinload(CourseSkillModel.skill),
        )
        .where(CourseSkillModel.skill_id.in_([UUID(skill_id) for skill_id in skill_ids]))
    )
    course_skill_links = result.scalars().all()

    grouped: dict[UUID, tuple[CourseModel, list[CourseSkillModel]]] = {}
    for link in course_skill_links:
        course = link.course
        if not course.is_active:
            continue
        _, links = grouped.setdefault(course.id, (course, []))
        links.append(link)

    return list(grouped.values())
