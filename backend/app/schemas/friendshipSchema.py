from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


FriendRequestStatus = Literal["pending", "accepted", "rejected", "cancelled"]
FriendshipStatus = Literal["self", "friends", "incoming_request", "outgoing_request", "none"]


class FriendRequestCreate(BaseModel):
    receiver_id: UUID


class FriendUserSummary(BaseModel):
    id: UUID
    display_name: str
    nickname: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class FriendRequestRead(BaseModel):
    id: UUID
    status: FriendRequestStatus
    created_at: datetime
    responded_at: datetime | None = None
    sender: FriendUserSummary
    receiver: FriendUserSummary


class FriendshipRead(BaseModel):
    friend: FriendUserSummary
    created_at: datetime


class FriendshipStatusRead(BaseModel):
    user_id: UUID
    status: FriendshipStatus
    request_id: UUID | None = None

