from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from fastapi_users.db import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from fastapi import Depends
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
ENV = os.getenv("ENV", "development").lower()


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


# Default to quiet + migration-driven schema management.
# Opt in locally by setting SQLALCHEMY_ECHO=1 and/or AUTO_CREATE_TABLES=1.
SQLALCHEMY_ECHO = _env_flag("SQLALCHEMY_ECHO", "0")
AUTO_CREATE_TABLES = _env_flag("AUTO_CREATE_TABLES", "0")
class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=SQLALCHEMY_ECHO)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def create_db_and_tables():
    if not AUTO_CREATE_TABLES:
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session

