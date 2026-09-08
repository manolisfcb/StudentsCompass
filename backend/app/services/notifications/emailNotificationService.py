from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.emailNotificationLogModel import EmailNotificationLogModel


class EmailNotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def queue_mock_email(
        self,
        *,
        recipient_email: str,
        recipient_name: str | None,
        template_key: str,
        subject: str,
        body_preview: str,
        payload: dict[str, Any] | None = None,
        application_id: UUID | None = None,
        company_id: UUID | None = None,
        recruiter_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> EmailNotificationLogModel:
        log = EmailNotificationLogModel(
            application_id=application_id,
            company_id=company_id,
            recruiter_id=recruiter_id,
            user_id=user_id,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            template_key=template_key,
            subject=subject,
            body_preview=body_preview,
            payload_json=json.dumps(payload or {}, default=str),
            delivery_status="mocked",
            created_at=datetime.utcnow(),
            sent_at=datetime.utcnow(),
        )
        self.session.add(log)
        await self.session.flush()
        return log
