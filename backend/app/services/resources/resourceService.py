from __future__ import annotations

from datetime import datetime
import mimetypes
from typing import Iterable

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.core.pagination import MAX_COLLECTION_ROWS
from app.models.resourceModel import (
    ResourceLessonModel,
    ResourceLessonProgressModel,
    ResourceModel,
    ResourceModuleModel,
)
from app.services.learning.courseProgress import CourseProgressProjector
from app.services.resources.resourceLessonContentCodec import ResourceLessonContentCodec
from app.services.storage.storageService import (
    StorageService,
    get_resource_storage_location_id,
    get_storage_service,
)

RESOURCE_KEY_PREFIX = "resources/"


class ResourceFileNotFound(LookupError):
    """The key does not belong to any resource the catalogue lets a user open.

    Deliberately the same answer for "no such file", "file exists but belongs to
    a locked or unpublished resource" and "file exists in the bucket but no
    resource references it": telling those apart would turn the endpoint back
    into an oracle for the bucket's contents.
    """


class ResourceService:
    MANDATORY_RESOURCE_TITLES: tuple[str, ...] = (
        "LinkedIn Optimization",
        "Interview Preparation",
        "Resume Templates",
    )

    def __init__(self, session: AsyncSession, storage_service: StorageService | None = None):
        self.session = session
        self.lesson_content_codec = ResourceLessonContentCodec()
        self.progress_projector = CourseProgressProjector(session)
        self.resources_bucket = get_resource_storage_location_id()
        try:
            if storage_service:
                self.storage_service = storage_service
            elif self.resources_bucket:
                self.storage_service = get_storage_service(bucket_name=self.resources_bucket)
            else:
                self.storage_service = None
        except Exception:
            self.storage_service = None

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

    @classmethod
    def is_mandatory_title(cls, title: str | None) -> bool:
        return (title or "").strip() in cls.MANDATORY_RESOURCE_TITLES

    @classmethod
    def prioritize_mandatory_resources(cls, resources: list[ResourceModel]) -> list[ResourceModel]:
        mandatory_by_title = {resource.title: resource for resource in resources if cls.is_mandatory_title(resource.title)}
        mandatory_ordered = [
            mandatory_by_title[title]
            for title in cls.MANDATORY_RESOURCE_TITLES
            if title in mandatory_by_title
        ]
        mandatory_ids = {resource.id for resource in mandatory_ordered}
        remaining = [resource for resource in resources if resource.id not in mandatory_ids]
        return mandatory_ordered + remaining

    #: What the catalogue may return in one read. The filtering is in SQL now,
    #: so this is a bound on the answer rather than on what is scanned.
    MAX_CATALOGUE_ROWS = MAX_COLLECTION_ROWS

    def _tag_matches(self, pattern: str):
        """``EXISTS`` over the tag array, element by element.

        ``tags`` is a JSON array, and matching it as *text* — ``CAST(tags AS
        TEXT) LIKE '%q%'`` — would be portable but wrong: it would also match
        the array's own punctuation and match across the boundary between two
        elements, so ``'a","b'`` would find ``["a", "b"]``. The in-memory
        version tested each tag on its own, and so does this.

        Both dialects can expand a JSON array into rows; only the function name
        differs, so the semantics are the same on the test lane and in
        production rather than merely similar.
        """
        dialect = self.session.bind.dialect.name if self.session.bind else "postgresql"
        if dialect == "postgresql":
            # A set-returning function aliased as a scalar: `tag_value` is both
            # the derived table and its single column.
            source = (
                "jsonb_array_elements_text(resources.tags::jsonb) AS tag_value"
            )
            element = "tag_value"
        else:
            # SQLite's json_each exposes the element under `value`, and it does
            # not accept a column list in the alias.
            source = "json_each(resources.tags) AS tag_element"
            element = "tag_element.value"
        return text(
            "resources.tags IS NOT NULL AND EXISTS ("
            f"SELECT 1 FROM {source} "
            f"WHERE lower({element}) LIKE :tag_pattern ESCAPE '\\')"
        ).bindparams(tag_pattern=pattern)

    async def list_published_resources(
        self,
        category: str | None = None,
        search: str | None = None,
        sort: str = "recent",
    ) -> list[ResourceModel]:
        """The published catalogue, filtered, searched and ordered by the database.

        This used to be ``SELECT * FROM resources WHERE is_published`` followed
        by three passes in Python: returning eleven resources cost loading
        every one of them. The category, the search and the order are now
        predicates and an ``ORDER BY``, so rows loaded equals rows returned.

        ``prioritize_mandatory_resources`` deliberately stays in Python. It is a
        product rule — three named courses come first, in a fixed order — not a
        database ordering, and expressing it as a ``CASE`` would bury it in the
        query where nobody looks for it.
        """
        conditions = [ResourceModel.is_published.is_(True)]

        if category and category.lower() != "all":
            # ``btrim`` + ``lower`` mirrors the in-memory comparison exactly,
            # which trimmed and lowered both sides.
            conditions.append(
                func.lower(func.trim(ResourceModel.category)) == category.strip().lower()
            )

        query = (search or "").strip().lower()
        if query:
            pattern = f"%{self._escape_like(query)}%"
            conditions.append(
                or_(
                    func.lower(ResourceModel.title).like(pattern, escape="\\"),
                    func.lower(ResourceModel.description).like(pattern, escape="\\"),
                    self._tag_matches(pattern),
                )
            )

        statement = select(ResourceModel).where(*conditions)

        if sort == "name":
            statement = statement.order_by(func.lower(ResourceModel.title))
        elif sort == "duration":
            # NULL sorted last, which is what ``or 10**9`` did in Python, then
            # title as the tie-break — the same two keys, in the same order.
            statement = statement.order_by(
                ResourceModel.estimated_duration_minutes.is_(None),
                ResourceModel.estimated_duration_minutes,
                func.lower(ResourceModel.title),
            )
        else:
            statement = statement.order_by(ResourceModel.created_at.desc())

        result = await self.session.execute(statement.limit(self.MAX_CATALOGUE_ROWS))
        return self.prioritize_mandatory_resources(list(result.scalars().all()))

    @staticmethod
    def _escape_like(value: str) -> str:
        """Neutralise LIKE wildcards in user input.

        Without this a search for ``100%`` matches everything, and ``_`` matches
        any character: the caller would be writing patterns without knowing it.
        The in-memory version used ``in``, which has no wildcards at all, so
        escaping is what preserves that meaning.
        """
        for special in ("\\", "%", "_"):
            value = value.replace(special, f"\\{special}")
        return value

    async def get_resource_with_outline(self, resource_id: UUID) -> ResourceModel | None:
        return await self.get_published_resource(resource_id, include_locked=False)

    async def get_published_resource(
        self,
        resource_id: UUID,
        *,
        include_locked: bool = False,
    ) -> ResourceModel | None:
        conditions = [
            ResourceModel.id == resource_id,
            ResourceModel.is_published.is_(True),
        ]
        if not include_locked:
            conditions.append(ResourceModel.is_locked.is_(False))

        result = await self.session.execute(
            select(ResourceModel)
            .where(*conditions)
            .options(
                selectinload(ResourceModel.modules).selectinload(ResourceModuleModel.lessons),
            )
        )
        resource = result.scalar_one_or_none()
        if not resource:
            return None

        resource.modules.sort(key=lambda m: m.position)
        for module in resource.modules:
            module.lessons.sort(key=lambda lesson: lesson.position)

        return resource

    async def get_completed_lesson_ids_for_resource(self, resource_id: UUID, user_id: UUID) -> set[UUID]:
        """What this user has finished in this course.

        Delegated to the shared projector so that the course page and the
        dashboard answer from the same facts. It used to be computed here and
        again, differently, in the dashboard's SQL.
        """
        completed = await self.progress_projector.completed_lesson_ids(
            user_id=user_id, resource_ids=[resource_id]
        )
        return completed.get(resource_id, set())

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
                ResourceModel.is_locked.is_(False),
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

    # Unreserved URL characters survive percent-encoding unchanged, so a run of
    # them is the same in the key and in any URL that embeds it.
    _URL_SAFE_CHARS = frozenset(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.~"
    )

    @classmethod
    def _prefilter_fragment(cls, filename: str) -> str:
        """Longest leading run of the file name that a stored URL cannot have
        re-encoded. Current keys are ``<uuid4 hex><ext>`` and older ones a
        timestamped name, so in practice this is the whole name and is highly
        selective; when it comes out empty the caller scans instead."""
        fragment: list[str] = []
        for char in filename:
            if char not in cls._URL_SAFE_CHARS:
                break
            fragment.append(char)
        return "".join(fragment)

    @staticmethod
    def _normalize_file_key(key: str) -> str | None:
        safe_key = (key or "").strip().lstrip("/")
        if not safe_key or not safe_key.startswith(RESOURCE_KEY_PREFIX):
            return None
        # A key is a stored object name, never a path to walk.
        if ".." in safe_key.split("/"):
            return None
        return safe_key

    async def resolve_authorized_file_key(self, key: str) -> str | None:
        """Return the key only if a visible resource actually references it.

        Belonging to the ``resources/`` prefix grants nothing: the catalogue
        decides what a user may open, so the file has to be reachable from a
        published, unlocked resource — the same conditions
        :meth:`get_published_resource` applies to the resource itself.
        """
        safe_key = self._normalize_file_key(key)
        if not safe_key:
            return None

        # Narrow the scan in SQL by the leading part of the file name, which the
        # upload path makes unique per object, then confirm the full key by
        # decoding the content. The LIKE is only a prefilter and never
        # authorizes on its own: a stored URL may carry a provider prefix the
        # key does not have, and may percent-encode the rest of the name.
        # autoescape keeps "_" in generated names literal.
        filename = safe_key.rsplit("/", 1)[-1]
        fragment = self._prefilter_fragment(filename)

        lesson_query = (
            select(ResourceLessonModel.content_type, ResourceLessonModel.content)
            .join(ResourceModuleModel, ResourceModuleModel.id == ResourceLessonModel.module_id)
            .join(ResourceModel, ResourceModel.id == ResourceModuleModel.resource_id)
            .where(
                ResourceModel.is_published.is_(True),
                ResourceModel.is_locked.is_(False),
            )
        )
        if fragment:
            lesson_query = lesson_query.where(
                ResourceLessonModel.content.contains(fragment, autoescape=True)
            )
        lesson_rows = await self.session.execute(lesson_query)
        for content_type, content in lesson_rows.all():
            referenced = self.lesson_content_codec.referenced_storage_keys(
                content_type=content_type,
                raw_content=content,
                prefix=RESOURCE_KEY_PREFIX,
            )
            if safe_key in referenced:
                return safe_key

        # A resource can also point straight at a stored file.
        resource_query = select(ResourceModel.external_url).where(
            ResourceModel.is_published.is_(True),
            ResourceModel.is_locked.is_(False),
            ResourceModel.external_url.is_not(None),
        )
        if fragment:
            resource_query = resource_query.where(
                ResourceModel.external_url.contains(fragment, autoescape=True)
            )
        resource_rows = await self.session.execute(resource_query)
        for (external_url,) in resource_rows.all():
            if self.lesson_content_codec.extract_storage_key(
                external_url, prefix=RESOURCE_KEY_PREFIX
            ) == safe_key:
                return safe_key

        return None

    async def download_resource_file(self, key: str) -> tuple[bytes, str, str]:
        # Authorize before touching the provider: a rejected key must not cost
        # a download.
        safe_key = await self.resolve_authorized_file_key(key)
        if not safe_key:
            raise ResourceFileNotFound("Resource file not found.")
        if not self.storage_service:
            raise ValueError("Resource storage is not configured.")

        file_bytes = await self.storage_service.download_file(safe_key)
        media_type = mimetypes.guess_type(safe_key)[0] or "application/octet-stream"
        filename = safe_key.rsplit("/", 1)[-1] or "resource_file"
        return file_bytes, media_type, filename

    async def list_user_enrollment_progress(self, user_id: UUID) -> list[dict]:
        """Progress for every course, at a cost that does not grow with the catalogue.

        The projector answers for a list of courses in a fixed number of
        queries, so it is asked once for all of them instead of once per
        resource: the loop used to spend two statements per course plus one
        approval check for every course carrying a ``resume_upload`` lesson.
        Order, DTO and completion semantics are the projector's, unchanged.
        """
        resource_result = await self.session.execute(
            select(ResourceModel)
            .options(selectinload(ResourceModel.modules).selectinload(ResourceModuleModel.lessons))
            .order_by(ResourceModel.created_at.desc())
        )
        resources = list(resource_result.scalars().all())
        if not resources:
            return []

        completed_by_resource = await self.progress_projector.completed_lesson_ids(
            user_id=user_id, resource_ids=[resource.id for resource in resources]
        )
        return [
            self.to_progress_payload(resource, completed_by_resource.get(resource.id, set()))
            for resource in resources
        ]

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
                content_fields = self.lesson_content_codec.to_api_fields(
                    content_type=lesson.content_type,
                    raw_content=lesson.content,
                )
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
                        "content_type": content_fields["content_type"],
                        "content": content_fields["content"],
                        "content_payload": content_fields["content_payload"],
                        "video_url": content_fields["video_url"],
                        "resource_url": content_fields["resource_url"],
                        "notes": content_fields["notes"],
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
            "is_locked": resource.is_locked,
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
