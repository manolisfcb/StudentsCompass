"""The deletion-intent queue on the database that actually runs it.

``record_deletion_intent`` takes the PostgreSQL ``ON CONFLICT`` path, which the
SQLite lane never executes, and the uniqueness it relies on is a real constraint
rather than an application check.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


@pytest.fixture
async def intents_table(pg_engine):
    from app.models.storageDeletionIntentModel import StorageDeletionIntentModel

    async with pg_engine.begin() as conn:
        await conn.run_sync(StorageDeletionIntentModel.__table__.create, checkfirst=True)
    try:
        yield StorageDeletionIntentModel
    finally:
        async with pg_engine.begin() as conn:
            await conn.run_sync(StorageDeletionIntentModel.__table__.drop, checkfirst=True)


@pytest.mark.asyncio
async def test_recording_the_same_object_twice_keeps_one_row(pg_sessionmaker, intents_table):
    from app.services.storage.storageCleanupService import record_deletion_intent

    key = f"resumes/{uuid.uuid4().hex}.pdf"

    for _ in range(3):
        async with pg_sessionmaker() as session:
            await record_deletion_intent(
                session, storage_location_id="bucket", object_key=key
            )
            await session.commit()

    async with pg_sessionmaker() as session:
        rows = (
            (
                await session.execute(
                    select(intents_table).where(intents_table.object_key == key)
                )
            )
            .scalars()
            .all()
        )

    assert len(rows) == 1


@pytest.mark.asyncio
async def test_re_recording_reopens_a_completed_intent(pg_sessionmaker, intents_table):
    """The object was deleted, uploaded again, and is unwanted again."""
    from app.services.storage.storageCleanupService import record_deletion_intent

    key = f"resumes/{uuid.uuid4().hex}.pdf"

    async with pg_sessionmaker() as session:
        await record_deletion_intent(session, storage_location_id="bucket", object_key=key)
        await session.commit()
        await session.execute(
            text(
                "UPDATE storage_deletion_intents SET completed_at = now()"
                " WHERE object_key = :key"
            ),
            {"key": key},
        )
        await session.commit()

    async with pg_sessionmaker() as session:
        await record_deletion_intent(session, storage_location_id="bucket", object_key=key)
        await session.commit()

    async with pg_sessionmaker() as session:
        row = (
            await session.execute(select(intents_table).where(intents_table.object_key == key))
        ).scalar_one()

    assert row.completed_at is None


@pytest.mark.asyncio
async def test_the_sweeper_completes_a_pending_intent(pg_sessionmaker, intents_table):
    from app.services.storage.storageCleanupService import (
        StorageCleanupService,
        record_deletion_intent,
    )

    class Storage:
        def __init__(self):
            self.deleted = []

        async def delete_file(self, file_key: str) -> bool:
            self.deleted.append(file_key)
            return True

    key = f"resumes/{uuid.uuid4().hex}.pdf"
    storage = Storage()

    async with pg_sessionmaker() as session:
        await record_deletion_intent(session, storage_location_id="bucket", object_key=key)
        await session.commit()

        result = await StorageCleanupService(session, storage_service=storage).process_pending()

    assert result == {"processed": 1, "completed": 1}
    assert storage.deleted == [key]

    async with pg_sessionmaker() as session:
        row = (
            await session.execute(select(intents_table).where(intents_table.object_key == key))
        ).scalar_one()
    assert row.completed_at is not None
