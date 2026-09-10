from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.paginationSchema import CursorPage


class PostCreate(BaseModel):
    caption: str
    url: str
    file_type: str
    file_name: str
    model_config = ConfigDict(from_attributes=True)

    
class PostRead(BaseModel):
    id: UUID
    caption: str
    url: str
    file_type: str
    file_name: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PostPageRead(CursorPage[PostRead]):
    """One bounded page of the global feed, newest first.

    ``next_cursor`` addresses the post the following page starts from, so
    walking it moves backwards in time. ``None`` means the end of the feed has
    been reached — the only reliable signal, since a full page does not by
    itself mean another exists.
    """
