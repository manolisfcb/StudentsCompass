from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.friendshipSchema import FriendUserSummary
from app.schemas.paginationSchema import CursorPage


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


class MessagePageRead(CursorPage[MessageRead]):
    """One bounded page of a conversation, oldest first.

    ``next_cursor`` addresses the message *before* the first item on this page,
    so following it walks backwards through history. It is ``None`` when the
    beginning of the conversation has been reached — the only reliable "no more"
    signal, since a full page does not by itself mean there is another.

    The fields come from :class:`CursorPage`, which TASK-041 generalised out of
    this schema: this was the first cursor-paged collection, and the rest of the
    API now uses the same envelope rather than a second one that looks like it.
    """


class ConversationReadReceipt(BaseModel):
    conversation_id: UUID
    marked_read_at: datetime
