from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class EmailNotificationLogModel(Base):
    __tablename__ = "email_notification_logs"
    __table_args__ = (
        Index("ix_email_notification_logs_application_created_at", "application_id", "created_at"),
        Index("ix_email_notification_logs_recipient_created_at", "recipient_email", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="SET NULL"), nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    recruiter_id = Column(UUID(as_uuid=True), ForeignKey("company_recruiters.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recipient_email = Column(String(320), nullable=False)
    recipient_name = Column(String(255), nullable=True)
    template_key = Column(String(128), nullable=False)
    subject = Column(String(255), nullable=False)
    body_preview = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=True)
    delivery_status = Column(String(32), nullable=False, default="mocked")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=False, default=datetime.utcnow)
