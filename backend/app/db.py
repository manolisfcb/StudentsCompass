from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from fastapi import Depends
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
ENV = os.getenv("ENV", "development").lower()


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        value = int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default


# Default to quiet + migration-driven schema management.
# Opt in locally by setting SQLALCHEMY_ECHO=1 and/or AUTO_CREATE_TABLES=1.
SQLALCHEMY_ECHO = _env_flag("SQLALCHEMY_ECHO", "0")
AUTO_CREATE_TABLES = _env_flag("AUTO_CREATE_TABLES", "0")
# Opt back into a connection-per-request engine for true serverless targets.
DB_DISABLE_POOL = _env_flag("DB_DISABLE_POOL", "0")
class Base(DeclarativeBase):
    pass


def _build_engine():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL must be configured before starting the API. "
            "Set it in the deployment environment; .env is not copied into the Docker image."
        )

    # Reuse warm connections across requests so each call does not pay a fresh
    # TCP + TLS handshake to the remote database. ``statement_cache_size=0`` is
    # required because the Neon "-pooler" endpoint is PgBouncer in transaction
    # mode, which is incompatible with asyncpg's prepared-statement cache.
    common = dict(
        echo=SQLALCHEMY_ECHO,
        connect_args={"statement_cache_size": 0},
    )
    if DB_DISABLE_POOL:
        return create_async_engine(DATABASE_URL, poolclass=NullPool, **common)
    return create_async_engine(
        DATABASE_URL,
        pool_size=_env_int("DB_POOL_SIZE", 5, minimum=1),
        max_overflow=_env_int("DB_MAX_OVERFLOW", 10, minimum=0),
        pool_pre_ping=True,
        pool_recycle=_env_int("DB_POOL_RECYCLE_SECONDS", 300, minimum=30),
        **common,
    )


engine = _build_engine()
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def create_db_and_tables():
    if not AUTO_CREATE_TABLES:
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
