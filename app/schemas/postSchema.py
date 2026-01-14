from pydantic import BaseModel

class PostCreate(BaseModel):
    caption: str
    url: str
    file_type: str
    file_name: str
    
class PostRead(PostCreate):
    id: str
    url: str
    file_name: str

    class Config:
        orm_mode = True