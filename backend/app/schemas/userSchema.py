from pydantic import BaseModel
import uuid
from fastapi_users import schemas
from typing import Optional

class UserCreate(schemas.BaseUserCreate):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nickname: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    sex: Optional[str] = None
    age: Optional[int] = None

class UserRead(schemas.BaseUser):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nickname: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    sex: Optional[str] = None
    age: Optional[int] = None
    
class UserUpdate(schemas.BaseUserUpdate):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nickname: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    sex: Optional[str] = None
    age: Optional[int] = None
