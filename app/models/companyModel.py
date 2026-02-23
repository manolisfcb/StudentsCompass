from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from fastapi_users.db import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from app.db import Base
from app.db import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends


class Company(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "companies"
    
    company_name = Column(String, nullable=False)
    industry = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    website = Column(String, nullable=True)
    location = Column(String, nullable=True)
    contact_person = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    

async def get_company_db(session: AsyncSession = Depends(get_session)):
    yield SQLAlchemyUserDatabase(session, Company)
