from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
