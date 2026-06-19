from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.friendshipModel import FriendshipModel
from app.models.messageModel import ConversationModel, ConversationParticipantModel, MessageModel
from app.models.userModel import User
from app.schemas.friendshipSchema import FriendUserSummary
from app.schemas.messageSchema import ConversationSummaryRead, MessageRead


def _build_direct_key(first_user_id: UUID, second_user_id: UUID) -> str:
    ordered_ids = sorted([str(first_user_id), str(second_user_id)])
    return ":".join(ordered_ids)


def _build_display_name(user: User) -> str:
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
    return full_name or user.nickname or user.email or "Student"


class MessageService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user(self, user_id: UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def are_friends(self, user_id: UUID, friend_id: UUID) -> bool:
        result = await self.session.execute(
            select(FriendshipModel.id).where(
                FriendshipModel.user_id == user_id,
                FriendshipModel.friend_id == friend_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_direct_conversation(self, first_user_id: UUID, second_user_id: UUID) -> ConversationModel | None:
        direct_key = _build_direct_key(first_user_id, second_user_id)
        result = await self.session.execute(
            select(ConversationModel).where(ConversationModel.direct_key == direct_key)
        )
        return result.scalar_one_or_none()

    async def get_conversation_for_user(self, conversation_id: UUID, user_id: UUID) -> ConversationModel | None:
        result = await self.session.execute(
            select(ConversationModel)
            .join(ConversationParticipantModel, ConversationParticipantModel.conversation_id == ConversationModel.id)
            .where(
                ConversationModel.id == conversation_id,
                ConversationParticipantModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_participant(self, conversation_id: UUID, user_id: UUID) -> ConversationParticipantModel | None:
        result = await self.session.execute(
            select(ConversationParticipantModel).where(
                ConversationParticipantModel.conversation_id == conversation_id,
                ConversationParticipantModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_or_get_direct_conversation(self, *, user_id: UUID, friend_id: UUID) -> ConversationModel:
        existing = await self.get_direct_conversation(user_id, friend_id)
        if existing:
            return existing

        created_at = datetime.utcnow()
        conversation = ConversationModel(
            kind="direct",
            direct_key=_build_direct_key(user_id, friend_id),
            created_at=created_at,
            updated_at=created_at,
        )
        self.session.add(conversation)
        await self.session.flush()

        self.session.add_all(
            [
                ConversationParticipantModel(
                    conversation_id=conversation.id,
                    user_id=user_id,
                    joined_at=created_at,
                    last_read_at=created_at,
                ),
                ConversationParticipantModel(
                    conversation_id=conversation.id,
                    user_id=friend_id,
                    joined_at=created_at,
                    last_read_at=created_at,
                ),
            ]
        )
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation

    async def list_conversations(self, user_id: UUID) -> list[ConversationSummaryRead]:
        result = await self.session.execute(
            select(ConversationParticipantModel, ConversationModel)
            .join(ConversationModel, ConversationParticipantModel.conversation_id == ConversationModel.id)
            .where(ConversationParticipantModel.user_id == user_id)
            .order_by(ConversationModel.updated_at.desc())
        )
        rows = result.all()

        payload: list[ConversationSummaryRead] = []
        for participant, conversation in rows:
            summary = await self.build_conversation_summary(
                conversation=conversation,
                current_user_id=user_id,
                participant=participant,
            )
            if summary:
                payload.append(summary)
        return payload

    async def build_conversation_summary(
        self,
        *,
        conversation: ConversationModel,
        current_user_id: UUID,
        participant: ConversationParticipantModel | None = None,
    ) -> ConversationSummaryRead | None:
        participant = participant or await self.get_participant(conversation.id, current_user_id)
        if not participant:
            return None

        other_user = await self._get_other_user(conversation.id, current_user_id)
        if not other_user:
            return None

        latest_message = await self._get_latest_message(conversation.id)
        unread_count = await self._count_unread_messages(
            conversation_id=conversation.id,
            user_id=current_user_id,
            last_read_at=participant.last_read_at,
        )

        return ConversationSummaryRead(
            id=conversation.id,
            kind="direct",
            other_user=self._build_user_summary(other_user),
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            last_message_at=conversation.last_message_at,
            last_message_preview=self._build_message_preview(latest_message.content) if latest_message else None,
            unread_count=unread_count,
        )

    async def list_messages(self, *, conversation_id: UUID, user_id: UUID) -> list[MessageRead]:
        result = await self.session.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.asc())
        )
        messages = result.scalars().all()

        payload: list[MessageRead] = []
        for message in messages:
            sender = await self.get_user(message.sender_id)
            payload.append(
                MessageRead(
                    id=message.id,
                    conversation_id=message.conversation_id,
                    sender_id=message.sender_id,
                    sender_display_name=_build_display_name(sender),
                    content=message.content,
                    created_at=message.created_at,
                    is_mine=message.sender_id == user_id,
                )
            )
        return payload

    async def send_message(self, *, conversation_id: UUID, sender_id: UUID, content: str) -> MessageRead:
        timestamp = datetime.utcnow()
        message = MessageModel(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.session.add(message)

        conversation = await self.get_conversation_for_user(conversation_id, sender_id)
        conversation.updated_at = timestamp
        conversation.last_message_at = timestamp

        participant = await self.get_participant(conversation_id, sender_id)
        participant.last_read_at = timestamp

        await self.session.commit()
        await self.session.refresh(message)

        sender = await self.get_user(sender_id)
        return MessageRead(
            id=message.id,
            conversation_id=message.conversation_id,
            sender_id=message.sender_id,
            sender_display_name=_build_display_name(sender),
            content=message.content,
            created_at=message.created_at,
            is_mine=True,
        )

    async def mark_conversation_read(self, *, conversation_id: UUID, user_id: UUID) -> datetime:
        participant = await self.get_participant(conversation_id, user_id)
        marked_at = datetime.utcnow()
        participant.last_read_at = marked_at
        await self.session.commit()
        return marked_at

    async def _get_other_user(self, conversation_id: UUID, current_user_id: UUID) -> User | None:
        result = await self.session.execute(
            select(ConversationParticipantModel).where(
                ConversationParticipantModel.conversation_id == conversation_id,
            )
        )
        participants = result.scalars().all()
        for participant in participants:
            if participant.user_id != current_user_id:
                return await self.get_user(participant.user_id)
        return None

    async def _get_latest_message(self, conversation_id: UUID) -> MessageModel | None:
        result = await self.session.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _count_unread_messages(self, *, conversation_id: UUID, user_id: UUID, last_read_at: datetime | None) -> int:
        conditions = [
            MessageModel.conversation_id == conversation_id,
            MessageModel.sender_id != user_id,
        ]
        if last_read_at is not None:
            conditions.append(MessageModel.created_at > last_read_at)

        result = await self.session.execute(
            select(func.count(MessageModel.id)).where(and_(*conditions))
        )
        return int(result.scalar_one() or 0)

    def _build_user_summary(self, user: User) -> FriendUserSummary:
        return FriendUserSummary(
            id=user.id,
            display_name=_build_display_name(user),
            nickname=user.nickname,
            first_name=user.first_name,
            last_name=user.last_name,
        )

    def _build_message_preview(self, content: str) -> str:
        compact = " ".join((content or "").split())
        if len(compact) <= 120:
            return compact
        return f"{compact[:117]}..."
