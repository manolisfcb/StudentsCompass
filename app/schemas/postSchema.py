from pydantic import BaseModel, ConfigDict
from pydantic import BaseModel
from uuid import UUID
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
    model_config = ConfigDict(from_attributes=True)
