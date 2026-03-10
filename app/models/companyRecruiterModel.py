from datetime import datetime

from fastapi import Depends
from fastapi_users.db import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship

from app.db import Base, get_session


class CompanyRecruiter(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "company_recruiters"
    __table_args__ = (
        Index("ix_company_recruiters_company_id", "company_id"),
        Index("ix_company_recruiters_company_id_is_active", "company_id", "is_active"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    role = Column(String(32), nullable=False, default="owner")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", back_populates="recruiters")


async def get_company_recruiter_db(session: AsyncSession = Depends(get_session)):
    yield SQLAlchemyUserDatabase(session, CompanyRecruiter)
