from __future__ import annotations

import os
import mimetypes
from datetime import datetime
from urllib.parse import urlparse, unquote, quote

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.models.resourceModel import (
    ResourceEnrollmentModel,
    ResourceLessonModel,
    ResourceLessonProgressModel,
    ResourceModel,
    ResourceModuleModel,
)
from app.services.s3Service import S3Service


class ResourceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.resources_bucket = os.getenv("RESOURCES_BUCKET_NAME") or os.getenv("BUCKET_NAME")
        try:
            self.s3_service = S3Service(bucket_name=self.resources_bucket) if self.resources_bucket else None
        except Exception:
            self.s3_service = None

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

    async def _get_or_create_enrollment(self, user_id: UUID, resource_id: UUID) -> ResourceEnrollmentModel:
        result = await self.session.execute(
            select(ResourceEnrollmentModel).where(
                ResourceEnrollmentModel.user_id == user_id,
                ResourceEnrollmentModel.resource_id == resource_id,
            )
        )
        enrollment = result.scalar_one_or_none()
        if enrollment:
            return enrollment

        enrollment = ResourceEnrollmentModel(user_id=user_id, resource_id=resource_id)
        self.session.add(enrollment)
        await self.session.flush()
        return enrollment

    async def _get_or_create_lesson_progress(
        self,
        user_id: UUID,
        resource_id: UUID,
        lesson_id: UUID,
    ) -> ResourceLessonProgressModel:
        result = await self.session.execute(
            select(ResourceLessonProgressModel).where(
                ResourceLessonProgressModel.user_id == user_id,
                ResourceLessonProgressModel.lesson_id == lesson_id,
            )
        )
        progress = result.scalar_one_or_none()
        if progress:
            return progress

        progress = ResourceLessonProgressModel(
            user_id=user_id,
            resource_id=resource_id,
            lesson_id=lesson_id,
        )
        self.session.add(progress)
        await self.session.flush()
        return progress

    async def _validate_resource_and_lesson(
        self,
        resource_id: UUID,
        lesson_id: UUID,
    ) -> tuple[ResourceModel, ResourceLessonModel]:
        resource_result = await self.session.execute(
            select(ResourceModel).where(
                ResourceModel.id == resource_id,
                ResourceModel.is_published.is_(True),
            )
        )
        resource = resource_result.scalar_one_or_none()
        if not resource:
            raise ValueError("Resource not found")

        lesson_result = await self.session.execute(
            select(ResourceLessonModel)
            .join(ResourceModuleModel, ResourceLessonModel.module_id == ResourceModuleModel.id)
            .where(
                ResourceLessonModel.id == lesson_id,
                ResourceModuleModel.resource_id == resource_id,
            )
        )
        lesson = lesson_result.scalar_one_or_none()
        if not lesson:
            raise ValueError("Lesson not found in this resource")

        return resource, lesson

    async def _total_lessons_map(self, resource_ids: list[UUID]) -> dict[UUID, int]:
        if not resource_ids:
            return {}

        result = await self.session.execute(
            select(ResourceModuleModel.resource_id, func.count(ResourceLessonModel.id))
            .join(ResourceLessonModel, ResourceLessonModel.module_id == ResourceModuleModel.id)
            .where(ResourceModuleModel.resource_id.in_(resource_ids))
            .group_by(ResourceModuleModel.resource_id)
        )
        return {resource_id: int(total or 0) for resource_id, total in result.all()}

    async def _completed_lessons_map(self, user_id: UUID, resource_ids: list[UUID]) -> dict[UUID, int]:
        if not resource_ids:
            return {}

        result = await self.session.execute(
            select(ResourceLessonProgressModel.resource_id, func.count(ResourceLessonProgressModel.id))
            .where(
                ResourceLessonProgressModel.user_id == user_id,
                ResourceLessonProgressModel.resource_id.in_(resource_ids),
                or_(
                    ResourceLessonProgressModel.completed_at.is_not(None),
                    ResourceLessonProgressModel.last_opened_at.is_not(None),
                ),
            )
            .group_by(ResourceLessonProgressModel.resource_id)
        )
        return {resource_id: int(total or 0) for resource_id, total in result.all()}

    def _build_enrollment_progress_payload(
        self,
        enrollment: ResourceEnrollmentModel,
        total_lessons: int,
        completed_lessons: int,
    ) -> dict:
        progress_percent = round((completed_lessons / total_lessons) * 100, 2) if total_lessons else 0.0
        resource = enrollment.resource
        return {
            "resource_id": enrollment.resource_id,
            "title": resource.title if resource else "",
            "category": resource.category if resource else "",
            "level": resource.level if resource else None,
            "icon": resource.icon if resource else None,
            "enrolled_at": enrollment.enrolled_at,
            "last_opened_lesson_id": enrollment.last_opened_lesson_id,
            "total_lessons": total_lessons,
            "completed_lessons": completed_lessons,
            "progress_percent": progress_percent,
            "is_completed": total_lessons > 0 and completed_lessons >= total_lessons,
        }

    async def enroll_user_in_resource(self, user_id: UUID, resource_id: UUID) -> dict:
        resource = await self.get_resource_with_outline(resource_id)
        if not resource:
            raise ValueError("Resource not found")

        enrollment = await self._get_or_create_enrollment(user_id=user_id, resource_id=resource_id)
        await self.session.commit()

        enrollment_result = await self.session.execute(
            select(ResourceEnrollmentModel)
            .where(
                ResourceEnrollmentModel.user_id == user_id,
                ResourceEnrollmentModel.resource_id == resource_id,
            )
            .options(selectinload(ResourceEnrollmentModel.resource))
        )
        enrollment = enrollment_result.scalar_one()

        totals = await self._total_lessons_map([resource_id])
        completed = await self._completed_lessons_map(user_id, [resource_id])
        return self._build_enrollment_progress_payload(
            enrollment=enrollment,
            total_lessons=totals.get(resource_id, 0),
            completed_lessons=completed.get(resource_id, 0),
        )

    async def mark_lesson_opened(
        self,
        user_id: UUID,
        resource_id: UUID,
        lesson_id: UUID,
    ) -> dict:
        _, lesson = await self._validate_resource_and_lesson(resource_id=resource_id, lesson_id=lesson_id)

        enrollment = await self._get_or_create_enrollment(user_id=user_id, resource_id=resource_id)
        progress = await self._get_or_create_lesson_progress(
            user_id=user_id,
            resource_id=resource_id,
            lesson_id=lesson.id,
        )
        now = datetime.utcnow()
        progress.last_opened_at = now
        enrollment.last_opened_lesson_id = lesson.id
        await self.session.commit()
        return await self.get_user_resource_progress(user_id=user_id, resource_id=resource_id)

    async def set_lesson_completion(
        self,
        user_id: UUID,
        resource_id: UUID,
        lesson_id: UUID,
        completed: bool = True,
    ) -> dict:
        _, lesson = await self._validate_resource_and_lesson(resource_id=resource_id, lesson_id=lesson_id)

        enrollment = await self._get_or_create_enrollment(user_id=user_id, resource_id=resource_id)
        progress = await self._get_or_create_lesson_progress(
            user_id=user_id,
            resource_id=resource_id,
            lesson_id=lesson.id,
        )
        now = datetime.utcnow()
        progress.last_opened_at = now
        progress.completed_at = now if completed else None
        enrollment.last_opened_lesson_id = lesson.id
        await self.session.commit()
        return await self.get_user_resource_progress(user_id=user_id, resource_id=resource_id)

    async def list_user_enrollment_progress(self, user_id: UUID) -> list[dict]:
        result = await self.session.execute(
            select(ResourceEnrollmentModel)
            .where(ResourceEnrollmentModel.user_id == user_id)
            .options(selectinload(ResourceEnrollmentModel.resource))
            .order_by(ResourceEnrollmentModel.enrolled_at.desc())
        )
        enrollments = list(result.scalars().all())
        if not enrollments:
            return []

        resource_ids = [e.resource_id for e in enrollments]
        totals = await self._total_lessons_map(resource_ids)
        completed = await self._completed_lessons_map(user_id, resource_ids)

        return [
            self._build_enrollment_progress_payload(
                enrollment=e,
                total_lessons=totals.get(e.resource_id, 0),
                completed_lessons=completed.get(e.resource_id, 0),
            )
            for e in enrollments
        ]

    async def get_user_resource_progress(self, user_id: UUID, resource_id: UUID) -> dict:
        result = await self.session.execute(
            select(ResourceEnrollmentModel)
            .where(
                ResourceEnrollmentModel.user_id == user_id,
                ResourceEnrollmentModel.resource_id == resource_id,
            )
            .options(selectinload(ResourceEnrollmentModel.resource))
        )
        enrollment = result.scalar_one_or_none()
        if not enrollment:
            raise ValueError("User is not enrolled in this resource")

        totals = await self._total_lessons_map([resource_id])
        completed = await self._completed_lessons_map(user_id, [resource_id])
        return self._build_enrollment_progress_payload(
            enrollment=enrollment,
            total_lessons=totals.get(resource_id, 0),
            completed_lessons=completed.get(resource_id, 0),
        )

    def _extract_s3_key(self, content_url: str) -> str | None:
        if not content_url or not self.resources_bucket:
            return None
        try:
            parsed = urlparse(content_url)
            if parsed.scheme not in {"http", "https"}:
                return None
            host = parsed.netloc.lower()
            bucket_host_prefix = f"{self.resources_bucket.lower()}.s3."
            if not host.startswith(bucket_host_prefix):
                return None
            key = unquote(parsed.path.lstrip("/"))
            return key or None
        except Exception:
            return None

    async def _resolve_lesson_content_url(self, content_type: str, content: str) -> str:
        signable_types = {"video_url", "external_link", "pdf_url", "ppt_url", "document_url"}
        if content_type not in signable_types:
            return content

        key = self._extract_s3_key(content)
        if not key:
            return content

        return f"/api/v1/resources/file?key={quote(key, safe='')}"

    async def download_resource_file(self, key: str) -> tuple[bytes, str, str]:
        if not self.s3_service:
            raise ValueError("S3 is not configured")
        if not key or not key.startswith("resources/"):
            raise ValueError("Invalid resource key")

        file_bytes = await self.s3_service.download_file(key)
        media_type, _ = mimetypes.guess_type(key)
        media_type = media_type or "application/octet-stream"
        filename = key.rsplit("/", 1)[-1] or "resource_file"
        return file_bytes, media_type, filename

    async def to_detail_payload(self, resource: ResourceModel) -> dict:
        modules = []
        total_lessons = 0
        for module in resource.modules:
            lessons = []
            for lesson in module.lessons:
                total_lessons += 1
                content = await self._resolve_lesson_content_url(lesson.content_type, lesson.content)
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
                    }
                )

            modules.append(
                {
                    "id": str(module.id),
                    "resource_id": str(module.resource_id),
                    "title": module.title,
                    "position": module.position,
                    "description": module.description,
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
            "module_count": len(modules),
            "lesson_count": total_lessons,
            # TODO(progress): when progress table exists, include completed lessons percentage here.
        }
