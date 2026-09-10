"""A durable record that an object *should* no longer exist.

Deleting a file used to happen before the database decided anything: the object
was removed, then the row, then the transaction committed — or didn't. A
rollback after that point left a row pointing at a file that was already gone,
and a provider error before it left a row deleted and the object paying for
storage forever, with nothing left in the system that knew the object existed.

Writing the intent in the *same transaction* as the delete makes the decision
survive both failures. Either the transaction commits — the row is gone and the
intent is on record, so the object is deleted now or on any later retry — or it
rolls back, and neither the row nor the intent exists, so nothing was destroyed.
The provider call happens strictly after the commit and can fail as often as it
likes; ``delete_object`` on an absent key succeeds, so the retry is idempotent.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, UniqueConstraint
from app.db_types import UUID

from app.db import Base


class StorageDeletionIntentModel(Base):
    __tablename__ = "storage_deletion_intents"
    __table_args__ = (
        # One live intent per object: recording the same deletion twice must
        # not create a second row for the sweeper to work through.
        UniqueConstraint(
            "storage_location_id", "object_key", name="uq_storage_deletion_intents_object"
        ),
        # The sweeper's only query is "what is still pending, oldest first".
        Index("ix_storage_deletion_intents_pending", "completed_at", "requested_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    storage_location_id = Column(String(255), nullable=False)
    object_key = Column(String(1024), nullable=False)

    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_attempt_at = Column(DateTime, nullable=True)
    # Kept for operators reading a stuck queue; never surfaced to end users.
    last_error = Column(Text, nullable=True)
