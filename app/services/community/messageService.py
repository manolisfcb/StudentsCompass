from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.messageModel import ConversationModel, ConversationParticipantModel, MessageModel
from app.models.userModel import User
from app.schemas.friendshipSchema import FriendUserSummary
from app.schemas.messageSchema import ConversationSummaryRead, MessageRead
from app.services.community.friendshipService import are_friends
from app.services.community.userDisplay import build_display_name_from_user, build_user_summary


def _build_direct_key(first_user_id: UUID, second_user_id: UUID) -> str:
    ordered_ids = sorted([str(first_user_id), str(second_user_id)])
    return ":".join(ordered_ids)


class MessageService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user(self, user_id: UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def are_friends(self, user_id: UUID, friend_id: UUID) -> bool:
        return await are_friends(self.session, user_id, friend_id)

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
        if not rows:
            return []

        # Batch the per-conversation lookups (other participant, latest message,
        # unread count) instead of issuing them once per conversation.
        conversation_ids = [conversation.id for _, conversation in rows]
        other_users = await self._get_other_users_by_conversation(conversation_ids, user_id)
        latest_messages = await self._get_latest_messages_by_conversation(conversation_ids)
        unread_counts = await self._count_unread_by_conversation(
            conversation_ids=conversation_ids,
            user_id=user_id,
        )

        payload: list[ConversationSummaryRead] = []
        for _participant, conversation in rows:
            other_user = other_users.get(conversation.id)
            if not other_user:
                continue
            latest_message = latest_messages.get(conversation.id)
            payload.append(
                ConversationSummaryRead(
                    id=conversation.id,
                    kind="direct",
                    other_user=self._build_user_summary(other_user),
                    created_at=conversation.created_at,
                    updated_at=conversation.updated_at,
                    last_message_at=conversation.last_message_at,
                    last_message_preview=(
                        self._build_message_preview(latest_message.content) if latest_message else None
                    ),
                    unread_count=unread_counts.get(conversation.id, 0),
                )
            )
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

        senders = await self._get_users_by_ids({message.sender_id for message in messages})

        payload: list[MessageRead] = []
        for message in messages:
            sender = senders.get(message.sender_id)
            payload.append(
                MessageRead(
                    id=message.id,
                    conversation_id=message.conversation_id,
                    sender_id=message.sender_id,
                    sender_display_name=build_display_name_from_user(sender) if sender else "Student",
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
            sender_display_name=build_display_name_from_user(sender) if sender else "Student",
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
            select(ConversationParticipantModel.user_id)
            .where(
                ConversationParticipantModel.conversation_id == conversation_id,
                ConversationParticipantModel.user_id != current_user_id,
            )
            .limit(1)
        )
        other_user_id = result.scalar_one_or_none()
        if other_user_id is None:
            return None
        return await self.get_user(other_user_id)

    async def _get_users_by_ids(self, user_ids: set[UUID]) -> dict[UUID, User]:
        ids = list(user_ids)
        if not ids:
            return {}
        result = await self.session.execute(select(User).where(User.id.in_(ids)))
        return {user.id: user for user in result.scalars().all()}

    async def _get_other_users_by_conversation(
        self,
        conversation_ids: list[UUID],
        current_user_id: UUID,
    ) -> dict[UUID, User]:
        if not conversation_ids:
            return {}
        # Resolve user ids first, then batch-load the users with an IN filter.
        # A direct column-to-column join to ``users`` is avoided on purpose: the
        # SQLite test backend stores users.id with dashes and the foreign-key
        # columns without, so such a join never matches there.
        result = await self.session.execute(
            select(
                ConversationParticipantModel.conversation_id,
                ConversationParticipantModel.user_id,
            ).where(
                ConversationParticipantModel.conversation_id.in_(conversation_ids),
                ConversationParticipantModel.user_id != current_user_id,
            )
        )
        pairs = result.all()
        users = await self._get_users_by_ids({user_id for _, user_id in pairs})
        # Direct conversations have exactly one other participant per conversation.
        return {
            conversation_id: users[user_id]
            for conversation_id, user_id in pairs
            if user_id in users
        }

    async def _get_latest_messages_by_conversation(
        self,
        conversation_ids: list[UUID],
    ) -> dict[UUID, MessageModel]:
        if not conversation_ids:
            return {}
        latest_subq = (
            select(
                MessageModel.conversation_id.label("conversation_id"),
                func.max(MessageModel.created_at).label("max_created_at"),
            )
            .where(MessageModel.conversation_id.in_(conversation_ids))
            .group_by(MessageModel.conversation_id)
            .subquery()
        )
        result = await self.session.execute(
            select(MessageModel).join(
                latest_subq,
                and_(
                    MessageModel.conversation_id == latest_subq.c.conversation_id,
                    MessageModel.created_at == latest_subq.c.max_created_at,
                ),
            )
        )
        latest: dict[UUID, MessageModel] = {}
        for message in result.scalars().all():
            # setdefault guards against two messages sharing the exact timestamp.
            latest.setdefault(message.conversation_id, message)
        return latest

    async def _count_unread_by_conversation(
        self,
        *,
        conversation_ids: list[UUID],
        user_id: UUID,
    ) -> dict[UUID, int]:
        if not conversation_ids:
            return {}
        result = await self.session.execute(
            select(MessageModel.conversation_id, func.count(MessageModel.id))
            .join(
                ConversationParticipantModel,
                and_(
                    ConversationParticipantModel.conversation_id == MessageModel.conversation_id,
                    ConversationParticipantModel.user_id == user_id,
                ),
            )
            .where(
                MessageModel.conversation_id.in_(conversation_ids),
                MessageModel.sender_id != user_id,
                or_(
                    ConversationParticipantModel.last_read_at.is_(None),
                    MessageModel.created_at > ConversationParticipantModel.last_read_at,
                ),
            )
            .group_by(MessageModel.conversation_id)
        )
        return {conversation_id: int(count or 0) for conversation_id, count in result.all()}

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
        return build_user_summary(user)

    def _build_message_preview(self, content: str) -> str:
        compact = " ".join((content or "").split())
        if len(compact) <= 120:
            return compact
        return f"{compact[:117]}..."
