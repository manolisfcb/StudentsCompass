"""Turning a recorded deletion intent into an object that is actually gone.

The intent is written by whoever decided the object should go, inside the same
transaction as that decision (see ``StorageDeletionIntentModel``). This service
is the other half: it performs the provider call, and it is safe to run again
after any kind of failure — a crash between commit and delete, a provider
outage, a half-finished sweep.
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.storageDeletionIntentModel import StorageDeletionIntentModel
from app.services.storage.storageService import StorageService, get_storage_service

LOGGER = logging.getLogger(__name__)


async def record_deletion_intent(
    session: AsyncSession,
    *,
    storage_location_id: str,
    object_key: str,
) -> None:
    """Register the intent without committing.

    Deliberately does not commit: the caller commits it together with the
    change that justified it, which is the whole point — a deletion the
    database rolled back must leave no intent behind, and one it committed must
    leave one even if the process dies immediately afterwards.
    """
    if not storage_location_id or not object_key:
        return

    values = {
        "storage_location_id": storage_location_id,
        "object_key": object_key,
        "requested_at": datetime.utcnow(),
        "attempts": 0,
    }

    if session.bind is not None and session.bind.dialect.name == "postgresql":
        # Re-recording an intent for the same object is not an error; it just
        # means the object is wanted gone again (a completed intent is reopened).
        statement = (
            postgres_insert(StorageDeletionIntentModel)
            .values(**values)
            .on_conflict_do_update(
                constraint="uq_storage_deletion_intents_object",
                set_={"completed_at": None, "requested_at": values["requested_at"]},
            )
        )
        await session.execute(statement)
        return

    existing = (
        await session.execute(
            select(StorageDeletionIntentModel).where(
                StorageDeletionIntentModel.storage_location_id == storage_location_id,
                StorageDeletionIntentModel.object_key == object_key,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        session.add(StorageDeletionIntentModel(**values))
    else:
        existing.completed_at = None
        existing.requested_at = values["requested_at"]


class StorageCleanupService:
    """Executes recorded deletion intents against the storage provider."""

    def __init__(self, session: AsyncSession, storage_service: StorageService | None = None):
        self.session = session
        self._storage_service = storage_service

    def _storage_for(self, storage_location_id: str) -> StorageService:
        if self._storage_service is not None:
            return self._storage_service
        return get_storage_service(bucket_name=storage_location_id)

    async def _run_intent(self, intent: StorageDeletionIntentModel) -> bool:
        intent.attempts = (intent.attempts or 0) + 1
        intent.last_attempt_at = datetime.utcnow()
        try:
            await self._storage_for(intent.storage_location_id).delete_file(intent.object_key)
        except Exception as error:  # provider failures must not lose the intent
            intent.last_error = str(error)[:2000]
            LOGGER.warning(
                "Storage deletion still pending for %s: %s", intent.object_key, error
            )
            return False

        intent.completed_at = datetime.utcnow()
        intent.last_error = None
        return True

    async def execute_intent(self, *, storage_location_id: str, object_key: str) -> bool:
        """Run the single intent just committed, if it is still pending.

        Called right after the commit so the common case needs no sweep at all.
        A failure here is not an error for the caller: the intent stays pending
        and :meth:`process_pending` will pick it up.
        """
        intent = (
            await self.session.execute(
                select(StorageDeletionIntentModel).where(
                    StorageDeletionIntentModel.storage_location_id == storage_location_id,
                    StorageDeletionIntentModel.object_key == object_key,
                    StorageDeletionIntentModel.completed_at.is_(None),
                )
            )
        ).scalar_one_or_none()

        if intent is None:
            return True

        done = await self._run_intent(intent)
        await self.session.commit()
        return done

    async def process_pending(self, *, limit: int = 100) -> dict:
        """Retry every pending intent, oldest first. Converges across runs."""
        pending = (
            (
                await self.session.execute(
                    select(StorageDeletionIntentModel)
                    .where(StorageDeletionIntentModel.completed_at.is_(None))
                    .order_by(StorageDeletionIntentModel.requested_at)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )

        completed = 0
        for intent in pending:
            if await self._run_intent(intent):
                completed += 1

        if pending:
            await self.session.commit()

        return {"processed": len(pending), "completed": completed}
