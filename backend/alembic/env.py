import os
from logging.config import fileConfig
from urllib.parse import urlsplit

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from alembic.script import ScriptDirectory

from app.db_baseline import bootstrap, database_is_empty

# The model manifest is the single import list; importing it registers every
# mapped table on ``Base.metadata``. Listing modules here again is what let
# roadmaps and resume_course_evaluations fall out of autogenerate's view.
from app.models.registry import Base  # noqa: F401


# --- Migration target -------------------------------------------------------
# The URL lives in the environment, never in alembic.ini, for two reasons:
# no credential is committed, and the migrator resolves the *same* variable the
# application uses (app/db.py reads DATABASE_URL), so a migration cannot be
# applied to a different database than the one the app talks to.

_ASYNC_TO_SYNC_DRIVER = {
    # Alembic runs synchronously; the app uses the async driver against the
    # same server. Only the driver differs, so it is translated rather than
    # requiring a second URL that could drift.
    "postgresql+asyncpg": "postgresql+psycopg",
    "postgresql+psycopg_async": "postgresql+psycopg",
    "sqlite+aiosqlite": "sqlite",
}


def _to_sync_url(url: str) -> str:
    scheme, separator, rest = url.partition("://")
    if not separator:
        return url
    return f"{_ASYNC_TO_SYNC_DRIVER.get(scheme, scheme)}://{rest}"


def _redacted(url: str) -> str:
    """Host/database only. Never log or raise with the credential itself."""
    parts = urlsplit(url)
    host = parts.hostname or "?"
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{host}{port}{parts.path}"


def resolve_migration_url() -> str:
    """Resolve the migration target, failing loudly when it is not configured.

    ALEMBIC_DATABASE_URL wins so an operator can aim the migrator at the
    direct (non-pooled) endpoint when the app runs through a pooler; otherwise
    the app's own DATABASE_URL is used, which keeps both in sync by default.
    """
    for variable in ("ALEMBIC_DATABASE_URL", "DATABASE_URL"):
        url = os.environ.get(variable, "").strip()
        if url:
            return _to_sync_url(url)

    raise RuntimeError(
        "No migration target configured. Set DATABASE_URL (the same variable "
        "the application uses), or ALEMBIC_DATABASE_URL to override it for the "
        "migrator only. alembic.ini deliberately carries no credential."
    )


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = resolve_migration_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    url = resolve_migration_url()
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = url
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Redacted on purpose: confirms the destination without printing the
    # credential into CI logs or a developer's terminal.
    print(f"alembic: migrating {_redacted(url)}")

    with connectable.connect() as connection:
        # An empty database cannot replay the historical chain (see
        # app/db_baseline.py): it is built from the checked-in baseline,
        # verified against the metadata and stamped. Anything that already has
        # tables is an existing installation and takes the normal
        # forward-only path from wherever it is stamped.
        if database_is_empty(connection):
            bootstrap(connection, ScriptDirectory.from_config(config), target_metadata)
            connection.commit()
            return

        # Inspecting opened an implicit transaction. Alembic expects to start
        # its own, and leaving this one open swallows the commit: the chain
        # runs and then silently rolls back.
        connection.rollback()

        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
