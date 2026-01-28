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
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    
    post = relationship("PostModel", back_populates="user")
    questionnaires = relationship("UserQuestionnaire", back_populates="user")
    resumes = relationship("ResumeModel", back_populates="user")
    job_analyses = relationship("JobAnalysisModel", back_populates="user", lazy="dynamic")
    

        
async def get_user_db(session: AsyncSession = Depends(get_session)):
    yield SQLAlchemyUserDatabase(session, User)