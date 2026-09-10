from pydantic import BaseModel
import uuid
from typing import Optional



class CreateResumeEmbeddingSchema(BaseModel):
    resume_id:uuid.UUID
    model_name: str
    dims: int
    embedding: Optional[list[float]] = None
    created_at: Optional[str] = None
    


class ReadResumeEmbeddingSchema(BaseModel):
    id: uuid.UUID
    resume_id:uuid.UUID
    model_name: str
    dims: int
    embedding: Optional[list[float]] = None
    created_at: Optional[str] = None
    
    class Config:
        orm_mode = True