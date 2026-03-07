from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid import UUID

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


class ResourceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.resources_bucket = os.getenv("RESOURCES_BUCKET_NAME") or os.getenv("BUCKET_NAME")
        try:
            self.s3_service = S3Service(bucket_name=self.resources_bucket) if self.resources_bucket else None
        except Exception:
            self.s3_service = None

    @staticmethod
    def _percent(completed: int, total: int) -> int:
        if total <= 0:
            return 0
        return round((completed / total) * 100)

    @staticmethod
    def _normalize_completed_ids(completed_lesson_ids: Iterable[UUID] | None) -> set[UUID]:
        if not completed_lesson_ids:
            return set()
        return set(completed_lesson_ids)

    async def list_published_resources(
        self,
        category: str | None = None,
        search: str | None = None,
        sort: str = "recent",
    ) -> list[ResourceModel]:
        result = await self.session.execute(
            select(ResourceModel).where(ResourceModel.is_published.is_(True))
        )
        resources = list(result.scalars().all())

        if category and category.lower() != "all":
            cat = category.strip().lower()
            resources = [r for r in resources if (r.category or "").strip().lower() == cat]

        if search:
            q = search.strip().lower()
            if q:
                def _matches(resource: ResourceModel) -> bool:
                    haystack = [resource.title or "", resource.description or ""]
                    tags = resource.tags or []
                    haystack.extend(tags)
                    return any(q in str(v).lower() for v in haystack)

                resources = [r for r in resources if _matches(r)]

        if sort == "name":
            resources.sort(key=lambda r: (r.title or "").lower())
        elif sort == "duration":
            resources.sort(key=lambda r: (r.estimated_duration_minutes or 10**9, (r.title or "").lower()))
        else:
            resources.sort(key=lambda r: r.created_at, reverse=True)

        return resources

    async def get_resource_with_outline(self, resource_id: UUID) -> ResourceModel | None:
        result = await self.session.execute(
            select(ResourceModel)
            .where(ResourceModel.id == resource_id, ResourceModel.is_published.is_(True))
            .options(
                selectinload(ResourceModel.modules).selectinload(ResourceModuleModel.lessons),
            )
        )
        resource = result.scalar_one_or_none()
        if not resource:
            return None

        resource.modules.sort(key=lambda m: m.position)
        for module in resource.modules:
            module.lessons.sort(key=lambda l: l.position)

        return resource

    async def get_completed_lesson_ids_for_resource(self, resource_id: UUID, user_id: UUID) -> set[UUID]:
        result = await self.session.execute(
            select(ResourceLessonProgressModel.lesson_id)
            .join(ResourceLessonModel, ResourceLessonModel.id == ResourceLessonProgressModel.lesson_id)
            .join(ResourceModuleModel, ResourceModuleModel.id == ResourceLessonModel.module_id)
            .where(
                ResourceLessonProgressModel.user_id == user_id,
                ResourceModuleModel.resource_id == resource_id,
                ResourceLessonModel.content_type != "resume_upload",
            )
        )
        completed_ids = {row[0] for row in result.all()}

        resume_upload_lessons = await self.session.execute(
            select(ResourceLessonModel.id)
            .join(ResourceModuleModel, ResourceModuleModel.id == ResourceLessonModel.module_id)
            .where(
                ResourceModuleModel.resource_id == resource_id,
                ResourceLessonModel.content_type == "resume_upload",
            )
        )
        resume_upload_lesson_ids = [row[0] for row in resume_upload_lessons.all()]
        if not resume_upload_lesson_ids:
            return completed_ids

        try:
            passed_eval = await self.session.execute(
                select(ResumeCourseEvaluationModel.id).where(
                    ResumeCourseEvaluationModel.user_id == user_id,
                    ResumeCourseEvaluationModel.status == ResumeCourseEvaluationStatus.COMPLETED,
                    ResumeCourseEvaluationModel.pass_status.is_(True),
                ).limit(1)
            )
        except ProgrammingError as exc:
            # Backward compatibility while DB migration is being rolled out.
            if "resume_course_evaluations" in str(exc):
                return completed_ids
            raise
        if passed_eval.scalar_one_or_none():
            completed_ids.update(resume_upload_lesson_ids)

        return completed_ids

    async def set_lesson_progress(
        self,
        *,
        user_id: UUID,
        lesson_id: UUID,
        completed: bool,
    ) -> dict | None:
        lesson_result = await self.session.execute(
            select(ResourceLessonModel, ResourceModuleModel.resource_id)
            .join(ResourceModuleModel, ResourceModuleModel.id == ResourceLessonModel.module_id)
            .join(ResourceModel, ResourceModel.id == ResourceModuleModel.resource_id)
            .where(
                ResourceLessonModel.id == lesson_id,
                ResourceModel.is_published.is_(True),
            )
        )
        lesson_row = lesson_result.first()
        if not lesson_row:
            return None

        lesson, resource_id = lesson_row

        # This lesson is managed exclusively by the resume-audit backend flow.
        # Ignore manual patch attempts from the generic lesson endpoint.
        if (lesson.content_type or "").strip().lower() == "resume_upload":
            return await self.get_resource_progress(resource_id=resource_id, user_id=user_id)

        progress_result = await self.session.execute(
            select(ResourceLessonProgressModel).where(
                ResourceLessonProgressModel.user_id == user_id,
                ResourceLessonProgressModel.lesson_id == lesson_id,
            )
        )
        progress = progress_result.scalar_one_or_none()
        now = datetime.utcnow()

        if completed:
            if progress:
                progress.last_opened_at = now
            else:
                self.session.add(
                    ResourceLessonProgressModel(
                        user_id=user_id,
                        lesson_id=lesson_id,
                        completed_at=now,
                        last_opened_at=now,
                    )
                )
        elif progress:
            await self.session.delete(progress)

        await self.session.commit()
        return await self.get_resource_progress(resource_id=resource_id, user_id=user_id)

    async def get_resource_progress(self, *, resource_id: UUID, user_id: UUID) -> dict | None:
        resource = await self.get_resource_with_outline(resource_id)
        if not resource:
            return None
        completed_ids = await self.get_completed_lesson_ids_for_resource(resource_id=resource.id, user_id=user_id)
        return self.to_progress_payload(resource, completed_ids)

    def to_detail_payload(
        self,
        resource: ResourceModel,
        completed_lesson_ids: Iterable[UUID] | None = None,
    ) -> dict:
        completed_ids = self._normalize_completed_ids(completed_lesson_ids)
        modules = []
        module_progress = []
        total_lessons = 0
        completed_lessons = 0

        for module in resource.modules:
            lessons = []
            module_completed = 0

            for lesson in module.lessons:
                total_lessons += 1
                is_completed = lesson.id in completed_ids
                if is_completed:
                    completed_lessons += 1
                    module_completed += 1
                lessons.append(
                    {
                        "id": str(lesson.id),
                        "module_id": str(lesson.module_id),
                        "title": lesson.title,
                        "position": lesson.position,
                        "content_type": lesson.content_type,
                        "content": content,
                        "reading_time_minutes": lesson.reading_time_minutes,
                        "created_at": lesson.created_at.isoformat(),
                        "is_completed": is_completed,
                    }
                )

            module_total = len(module.lessons)
            module_progress.append(
                {
                    "module_id": str(module.id),
                    "completed_lessons": module_completed,
                    "total_lessons": module_total,
                    "progress_percent": self._percent(module_completed, module_total),
                }
            )
            modules.append(
                {
                    "id": str(module.id),
                    "resource_id": str(module.resource_id),
                    "title": module.title,
                    "position": module.position,
                    "description": module.description,
                    "completed_lessons": module_completed,
                    "total_lessons": module_total,
                    "progress_percent": self._percent(module_completed, module_total),
                    "lessons": lessons,
                }
            )

        return {
            "id": str(resource.id),
            "title": resource.title,
            "description": resource.description,
            "icon": resource.icon,
            "category": resource.category,
            "tags": resource.tags or [],
            "level": resource.level,
            "estimated_duration_minutes": resource.estimated_duration_minutes,
            "external_url": resource.external_url,
            "created_at": resource.created_at.isoformat(),
            "modules": modules,
            "module_progress": module_progress,
            "module_count": len(modules),
            "lesson_count": total_lessons,
            "completed_lesson_ids": sorted(str(lesson_id) for lesson_id in completed_ids),
            "completed_lessons": completed_lessons,
            "progress_percent": self._percent(completed_lessons, total_lessons),
        }

    def to_progress_payload(
        self,
        resource: ResourceModel,
        completed_lesson_ids: Iterable[UUID] | None = None,
    ) -> dict:
        detail_payload = self.to_detail_payload(resource, completed_lesson_ids=completed_lesson_ids)
        return {
            "resource_id": detail_payload["id"],
            "completed_lesson_ids": detail_payload["completed_lesson_ids"],
            "completed_lessons": detail_payload["completed_lessons"],
            "total_lessons": detail_payload["lesson_count"],
            "progress_percent": detail_payload["progress_percent"],
            "modules": detail_payload["module_progress"],
        }
