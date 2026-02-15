from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CommunityCreate(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    activity_status: Optional[str] = None
    tags: Optional[list[str]] = None
    member_count: Optional[int] = None


class CommunityRead(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    activity_status: Optional[str] = None
    tags: Optional[list[str]] = None
    member_count: int
    created_at: datetime
    created_by: UUID

    model_config = ConfigDict(from_attributes=True)


class CommunityMemberRead(BaseModel):
    id: UUID
    community_id: UUID
    user_id: UUID
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommunityPostCreate(BaseModel):
    title: Optional[str] = None
    content: str


class CommunityPostRead(BaseModel):
    id: UUID
    community_id: UUID
    user_id: UUID
    title: Optional[str] = None
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommunityPostEnriched(BaseModel):
    """Post with author info, like count, comment count, and user like status."""
    id: UUID
    community_id: UUID
    user_id: UUID
    title: Optional[str] = None
    content: str
    created_at: datetime
    author_name: str
    like_count: int = 0
    comment_count: int = 0
    liked_by_me: bool = False


class CommunityPostCommentCreate(BaseModel):
    content: str


class CommunityPostCommentRead(BaseModel):
    id: UUID
    post_id: UUID
    user_id: UUID
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommunityPostCommentEnriched(BaseModel):
    """Comment with author info."""
    id: UUID
    post_id: UUID
    user_id: UUID
    content: str
    created_at: datetime
    author_name: str
