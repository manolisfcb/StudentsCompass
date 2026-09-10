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


class FriendRequestStatusUpdate(BaseModel):
    """Body of `PATCH /friend-requests/{id}` (TASK-051, plan 08 §5.2).

    Only `"accepted"` is accepted: the plan renames *accepting* a request to
    this verb, not the full lifecycle. Reject and cancel keep their existing
    `POST .../reject` and `.../cancel` actions — the plan does not name them,
    and turning every transition into a `status` value on one endpoint is a
    bigger contract decision than a rename should make on its own.
    """

    status: Literal["accepted"]

