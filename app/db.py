from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from fastapi_users.db import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from fastapi import Depends



# PostgreSQL (Neon) async connection URL
# Uses asyncpg driver for SQLAlchemy AsyncEngine
DATABASE_URL = (
    "postgresql+asyncpg://"
    "neondb_owner:npg_ADpQzRkP2T6O"
    "@ep-broad-mud-ah6lygvy-pooler.c-3.us-east-1.aws.neon.tech/neondb"
)

class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=True)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session

