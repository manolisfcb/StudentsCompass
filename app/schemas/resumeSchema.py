from pydantic import BaseModel
import uuid
from fastapi_users import schemas
from typing import Optional



class CreateResumeSchema(BaseModel):
    view_url: str
    original_filename: str
    storage_file_id: str
    folder_id: str
    user_id: uuid.UUID



class ResumeReadSchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    view_url: str
    original_filename: str
    storage_file_id: str
    folder_id: str
    created_at: Optional[str] = None
