from __future__ import annotations

import base64
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, literal, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.messageModel import ConversationModel, ConversationParticipantModel, MessageModel
from app.models.userModel import User
from app.schemas.friendshipSchema import FriendUserSummary
from app.schemas.messageSchema import (
    ConversationSummaryRead,
    MessagePageRead,
    MessageRead,
)
from app.services.community.friendshipService import are_friends
from app.services.community.userDisplay import build_display_name_from_user, build_user_summary


class InvalidMessageCursor(ValueError):
    """The cursor did not come from :meth:`MessageService.encode_message_cursor`."""

    def __init__(self, cursor: str):
        super().__init__("The pagination cursor is not valid.")
        self.cursor = cursor


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

    #: Messages returned when the caller does not say. One screenful of history.
    DEFAULT_MESSAGE_PAGE_SIZE = 50
    #: The most any single request may return, whatever it asks for. This is the
    #: bound that makes the payload finite: the endpoint used to serialise every
    #: message a conversation had ever contained.
    MAX_MESSAGE_PAGE_SIZE = 200

    @staticmethod
    def encode_message_cursor(message: MessageModel) -> str:
        """An opaque cursor addressing one message by ``(created_at, id)``.

        Not an offset: rows inserted while a client pages would shift every
        offset after them, so a conversation being actively written to would
        skip and repeat messages. And not ``created_at`` alone — two messages
        sent in the same millisecond would make the boundary ambiguous, which
        is exactly the case the 10 000-message test exercises.
        """
        raw = f"{message.created_at.isoformat()}|{message.id}"
        return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")

    @staticmethod
    def decode_message_cursor(cursor: str) -> tuple[datetime, UUID]:
        """Parse a cursor, or refuse it.

        A cursor is client-supplied input; a malformed one is a 400, never a
        500 and never a silently ignored filter that would quietly return the
        wrong page.
        """
        try:
            raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
            timestamp, _, identifier = raw.partition("|")
            return datetime.fromisoformat(timestamp), UUID(identifier)
        except Exception as exc:  # noqa: BLE001 — every malformed shape is one answer
            raise InvalidMessageCursor(cursor) from exc

    async def list_message_page(
        self,
        *,
        conversation_id: UUID,
        user_id: UUID,
        before: str | None = None,
        limit: int | None = None,
    ) -> MessagePageRead:
        """One bounded page of a conversation, oldest first, walking backwards.

        The query orders newest-first so the newest page is the cheap one — that
        is what a chat opens on — and the page is reversed before it is
        returned, so the payload reads in conversation order either way.
        """
        page_size = self.DEFAULT_MESSAGE_PAGE_SIZE if limit is None else limit
        page_size = max(1, min(page_size, self.MAX_MESSAGE_PAGE_SIZE))

        conditions = [MessageModel.conversation_id == conversation_id]
        if before:
            cursor_created_at, cursor_id = self.decode_message_cursor(before)
            # Row-value comparison, so the tie-break on identical timestamps is
            # part of the index scan rather than a filter applied afterwards.
            conditions.append(
                tuple_(MessageModel.created_at, MessageModel.id)
                < tuple_(literal(cursor_created_at), literal(cursor_id))
            )

        result = await self.session.execute(
            select(MessageModel)
            .where(*conditions)
            .order_by(MessageModel.created_at.desc(), MessageModel.id.desc())
            # One extra row: whether a further page exists is a fact about the
            # data, not something to infer from a full page.
            .limit(page_size + 1)
        )
        rows = list(result.scalars().all())
        has_more = len(rows) > page_size
        rows = rows[:page_size]
        rows.reverse()

        senders = await self._get_users_by_ids({message.sender_id for message in rows})
        items = [self._build_message_read(message, senders, user_id) for message in rows]

        return MessagePageRead(
            items=items,
            next_cursor=self.encode_message_cursor(rows[0]) if rows and has_more else None,
            has_more=has_more,
            limit=page_size,
        )

    def _build_message_read(
        self, message: MessageModel, senders: dict, user_id: UUID
    ) -> MessageRead:
        sender = senders.get(message.sender_id)
        return MessageRead(
            id=message.id,
            conversation_id=message.conversation_id,
            sender_id=message.sender_id,
            sender_display_name=build_display_name_from_user(sender) if sender else "Student",
            content=message.content,
            created_at=message.created_at,
            is_mine=message.sender_id == user_id,
        )

    async def list_messages(self, *, conversation_id: UUID, user_id: UUID) -> list[MessageRead]:
        """The legacy shape: a bare list, oldest first.

        Kept while the callers are migrated — the React inbox is TASK-051 — but
        no longer unbounded. It answers with the **most recent** page rather
        than the oldest, because a client that renders whatever it is given and
        scrolls to the bottom shows the right thing that way; the oldest page
        would have silently truncated the conversation at its beginning.
        """
        page = await self.list_message_page(conversation_id=conversation_id, user_id=user_id)
        return page.items

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
