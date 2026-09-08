from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.friendshipSchema import FriendUserSummary


ConversationKind = Literal["direct"]


class DirectConversationCreate(BaseModel):
    friend_id: UUID


class MessageCreate(BaseModel):
    content: str


class ConversationSummaryRead(BaseModel):
    id: UUID
    kind: ConversationKind = "direct"
    other_user: FriendUserSummary
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None
    last_message_preview: str | None = None
    unread_count: int = 0


class MessageRead(BaseModel):
    id: UUID
    conversation_id: UUID
    sender_id: UUID
    sender_display_name: str
    content: str
    created_at: datetime
    is_mine: bool = False

    model_config = ConfigDict(from_attributes=True)


class MessagePageRead(BaseModel):
    """One bounded page of a conversation, oldest first.

    ``next_cursor`` addresses the message *before* the first item on this page,
    so following it walks backwards through history. It is ``None`` when the
    beginning of the conversation has been reached — the only reliable "no more"
    signal, since a full page does not by itself mean there is another.
    """

    items: list[MessageRead]
    next_cursor: str | None = None
    has_more: bool = False
    limit: int


class ConversationReadReceipt(BaseModel):
    conversation_id: UUID
    marked_read_at: datetime
