from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from app.db_types import UUID
from sqlalchemy.orm import relationship

from app.db import Base


class ConversationModel(Base):
    __tablename__ = "conversations"
    # Declared here because the index exists in every deployed database:
    # an autogenerate run against metadata that omits it proposes dropping
    # it, which is how a previous revision silently removed a batch of them.
    __table_args__ = (
        Index("ix_conversations_updated_at", "updated_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind = Column(String(32), nullable=False, default="direct")
    direct_key = Column(String(80), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_message_at = Column(DateTime, nullable=True)

    participants = relationship(
        "ConversationParticipantModel",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    messages = relationship(
        "MessageModel",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class ConversationParticipantModel(Base):
    __tablename__ = "conversation_participants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_read_at = Column(DateTime, nullable=True)

    conversation = relationship("ConversationModel", back_populates="participants")
    user = relationship("User", back_populates="conversation_participants")

    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", name="uq_conversation_participant"),
        Index("ix_conversation_participants_user_id", "user_id"),
        Index("ix_conversation_participants_conversation_id", "conversation_id"),
    )


class MessageModel(Base):
    __tablename__ = "messages"
    __table_args__ = (
        # The keyset index: the paged read orders by (created_at, id) inside one
        # conversation, and without the composite the planner scans the
        # conversation's whole history to answer for the newest page.
        Index("ix_messages_conversation_created_id", "conversation_id", "created_at", "id"),
        Index("ix_messages_conversation_id", "conversation_id"),
        Index("ix_messages_created_at", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    conversation = relationship("ConversationModel", back_populates="messages")
    sender = relationship("User", back_populates="sent_messages")
