from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.models.resourceModel import ResourceModel, ResourceModuleModel


class ResourceService:
    def __init__(self, session: AsyncSession):
        self.session = session

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

    def to_detail_payload(self, resource: ResourceModel) -> dict:
        modules = []
        total_lessons = 0
        for module in resource.modules:
            lessons = []
            for lesson in module.lessons:
                total_lessons += 1
                lessons.append(
                    {
                        "id": str(lesson.id),
                        "module_id": str(lesson.module_id),
                        "title": lesson.title,
                        "position": lesson.position,
                        "content_type": lesson.content_type,
                        "content": lesson.content,
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
