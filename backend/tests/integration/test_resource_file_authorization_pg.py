"""Resource-file authorization against PostgreSQL.

The lookup narrows candidates with a LIKE prefilter over the lesson content.
Escaping and wildcard handling there are dialect behaviour, and the generated
file names contain ``_`` — a LIKE wildcard — so the check is worth running on
the database that actually serves production, not only on SQLite.
"""
from __future__ import annotations

import uuid

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.postgres]

VISIBLE_KEY = "resources/20260101_120000_ab12cd34_guide.pdf"
LOCKED_KEY = "resources/20260101_120000_ffffffff_secret.pdf"


@pytest.fixture
def _models():
    import tests.conftest  # noqa: F401  (imports the full model set)
    from app.db import Base

    return Base


async def _seed(session, *, key: str, is_published: bool, is_locked: bool) -> None:
    from app.models.resourceModel import ResourceLessonModel, ResourceModel, ResourceModuleModel
    from app.services.resources.resourceLessonContentCodec import ResourceLessonContentCodec

    codec = ResourceLessonContentCodec()
    resource = ResourceModel(
        id=uuid.uuid4(),
        title=f"Course {uuid.uuid4().hex[:6]}",
        description="A course with an attached file.",
        category="career",
        is_published=is_published,
        is_locked=is_locked,
    )
    module = ResourceModuleModel(id=uuid.uuid4(), resource_id=resource.id, title="M", position=1)
    lesson = ResourceLessonModel(
        id=uuid.uuid4(),
        module_id=module.id,
        title="L",
        position=1,
        content_type="pdf_url",
        content=codec.encode(
            content_type="pdf_url",
            content=None,
            resource_url=f"https://storage.example/{key}",
        ).storage_content,
    )
    session.add_all([resource, module, lesson])
    await session.commit()


@pytest.mark.asyncio
async def test_only_visible_resources_authorize_their_files(pg_engine, pg_sessionmaker, _models):
    from app.db import Base
    from app.services.resources.resourceService import ResourceService

    async with pg_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with pg_sessionmaker() as session:
            await _seed(session, key=VISIBLE_KEY, is_published=True, is_locked=False)
            await _seed(session, key=LOCKED_KEY, is_published=True, is_locked=True)

            service = ResourceService(session=session, storage_service=None)

            assert await service.resolve_authorized_file_key(VISIBLE_KEY) == VISIBLE_KEY
            assert await service.resolve_authorized_file_key(LOCKED_KEY) is None
            assert await service.resolve_authorized_file_key("resources/unknown.pdf") is None

            # "_" is a LIKE wildcard: a key that differs only where the visible
            # key has an underscore must not match through the prefilter.
            assert (
                await service.resolve_authorized_file_key(
                    "resources/20260101X120000_ab12cd34_guide.pdf"
                )
                is None
            )
    finally:
        async with pg_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
