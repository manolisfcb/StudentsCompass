from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.observability import install_sql_counter
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from fastapi import Depends
# Parsed in app/config.py, which also loads the .env file — so importing this
# module cannot read the environment before that file has been applied. These
# names are re-exported because callers and tests already import them from here.
from app.config import (  # noqa: F401  (re-exported for existing importers)
    AUTO_CREATE_TABLES,
    DATABASE_URL,
    DB_DISABLE_POOL,
    ENV,
    SQLALCHEMY_ECHO,
    env_int,
)
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
        pool_size=env_int("DB_POOL_SIZE", 5, minimum=1),
        max_overflow=env_int("DB_MAX_OVERFLOW", 10, minimum=0),
        pool_pre_ping=True,
        pool_recycle=env_int("DB_POOL_RECYCLE_SECONDS", 300, minimum=30),
        **common,
    )


engine = _build_engine()

# Counts every statement into whatever request is in flight, so a request's log
# line can say how many round trips it made. Attached once, here, at the driver
# level: installing it twice would count each statement twice.
install_sql_counter(engine)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def create_db_and_tables():
    if not AUTO_CREATE_TABLES:
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
