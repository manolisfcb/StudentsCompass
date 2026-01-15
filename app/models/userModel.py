from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from fastapi_users.db import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from app.db import Base
from app.db import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"
    nickname: str = Column(String, unique=False, nullable=True)
    post = relationship("PostModel", back_populates="user")
    

        
async def get_user_db(session: AsyncSession = Depends(get_session)):
    yield SQLAlchemyUserDatabase(session, User)