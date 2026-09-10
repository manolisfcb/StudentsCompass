"""Baseline schema for an empty database.

The historical revision chain cannot be replayed from nothing. Its root adds
columns to ``users`` without ever creating the table; ``4897b7743b34`` drops
``job_analysis`` and no later revision recreates it, yet ``1720e86014a0`` and
``e1f7c2b9a4d3`` go on to alter it; and ``73a6e7c411b9`` drops ``applications``
before anything creates it. Those revisions are already applied in the deployed
database, so they are not edited here — fixing them would rewrite history that
production has already passed through.

That leaves two paths, which is what this module implements:

* An **existing** database keeps the forward-only chain. ``alembic upgrade
  head`` walks from whatever revision it is stamped at, exactly as before.
* An **empty** database is created from the explicit DDL below, verified
  structurally against the mapped metadata, and only then stamped at head.

The DDL is generated from ``Base.metadata`` and checked in, so a schema change
that never reached a migration shows up as a diff in review rather than being
conjured at deploy time by ``create_all``. :func:`verify_against_metadata` is
what makes the stamp legitimate: it re-introspects the database Alembic just
built and refuses to stamp if it does not match the models.

Regenerate after a schema change, against a disposable database. Seed
``alembic_version`` with SQL rather than ``alembic stamp``: an empty database
routes through this module, so ``stamp`` would try to bootstrap instead::

    CREATE TABLE alembic_version (version_num varchar(32) NOT NULL,
        CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num));
    INSERT INTO alembic_version VALUES ('<current head>');

then ``alembic revision --autogenerate -m "snapshot"`` and move the generated
``upgrade()`` body into :func:`create_schema`.

Databases bootstrapped this way are forward-only: ``alembic downgrade`` would
run historical revisions whose starting shape they never had.
"""
from __future__ import annotations

import logging

import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.dialects import postgresql  # noqa: F401  (used by the generated DDL)

# Referenced by the generated DDL below, which renders column types with their
# fully qualified names. ``fastapi_users.db`` comes first on purpose: it and
# ``fastapi_users_db_sqlalchemy`` import each other, and reaching the latter
# first leaves the pair half-initialised.
import fastapi_users.db  # noqa: F401
import fastapi_users_db_sqlalchemy.generics  # noqa: F401
import pgvector.sqlalchemy.vector  # noqa: F401

LOGGER = logging.getLogger("alembic.baseline")


class BaselineVerificationError(RuntimeError):
    """The freshly created schema does not match the mapped metadata."""


class UnsupportedDialectError(RuntimeError):
    """The baseline cannot build this database, so it must not stamp it either."""


#: The baseline DDL below is PostgreSQL-only, and not merely by preference: it uses
#: ``btrim``/``char_length`` inside CHECK constraints, ``JSONB``, partial indexes and a
#: pgvector HNSW index. Measured on SQLite, ``create_schema`` gets 28 tables in before
#: ``no such function: btrim`` — a *partial* schema, which is worse than none.
SUPPORTED_DIALECT = "postgresql"


def require_supported_dialect(connection) -> None:
    """Refuse a dialect the baseline cannot build, before anything is created.

    Guarding here rather than letting the DDL fail halfway is the point: a half-built
    database is harder to reason about than one that was never touched.
    """
    dialect = connection.dialect.name
    if dialect != SUPPORTED_DIALECT:
        raise UnsupportedDialectError(
            f"The baseline schema is {SUPPORTED_DIALECT}-only and cannot be created on "
            f"{dialect!r}; the database was neither created nor stamped. Point "
            "DATABASE_URL at PostgreSQL, or create the schema by another route."
        )


def database_is_empty(connection) -> bool:
    """True only when the connection points at a database with no tables yet.

    A database that carries ``alembic_version`` is an existing installation
    even if it is otherwise bare, and any application table means the same.
    Being conservative here matters: mistaking a real database for an empty one
    would run the baseline over live data.
    """
    return not sa.inspect(connection).get_table_names()


def create_schema(connection) -> None:
    """Create the current schema. Generated from ``Base.metadata`` — see above.

    The generated block is in the function body, not inside the extension guard. It used
    to be indented one level deeper, so on any dialect other than PostgreSQL this
    function created nothing at all and returned as if it had succeeded — and
    :func:`bootstrap` went on to stamp an empty database at head.
    """
    require_supported_dialect(connection)

    op = Operations(MigrationContext.configure(connection))

    # pgvector must exist before ``resume_embeddings`` and its HNSW index.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ### generated from Base.metadata — regenerate, do not hand-edit ###
    op.create_table('companies',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('company_name', sa.String(), nullable=False),
    sa.Column('industry', sa.String(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('website', sa.String(), nullable=True),
    sa.Column('location', sa.String(), nullable=True),
    sa.Column('contact_person', sa.String(), nullable=True),
    sa.Column('phone', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_companies_company_name', 'companies', ['company_name'], unique=False)
    op.create_table('conversations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('direct_key', sa.String(length=80), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('last_message_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('direct_key')
    )
    op.create_index('ix_conversations_updated_at', 'conversations', ['updated_at'], unique=False)
    op.create_table('idempotency_records',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('actor_key', sa.String(length=128), nullable=False),
    sa.Column('endpoint', sa.String(length=200), nullable=False),
    sa.Column('idempotency_key', sa.String(length=255), nullable=False),
    sa.Column('request_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('status', sa.Enum('IN_PROGRESS', 'COMPLETED', name='idempotencystatus'), nullable=False),
    sa.Column('response_status_code', sa.Integer(), nullable=True),
    sa.Column('response_body', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('actor_key', 'endpoint', 'idempotency_key', name='uq_idempotency_actor_endpoint_key')
    )
    op.create_index('ix_idempotency_records_expires_at', 'idempotency_records', ['expires_at'], unique=False)
    op.create_table('resources',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=180), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('icon', sa.String(length=120), nullable=True),
    sa.Column('category', sa.String(length=64), nullable=False),
    sa.Column('tags', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('level', sa.String(length=32), nullable=True),
    sa.Column('estimated_duration_minutes', sa.Integer(), nullable=True),
    sa.Column('external_url', sa.String(length=512), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('is_published', sa.Boolean(), nullable=False),
    sa.Column('is_locked', sa.Boolean(), nullable=False),
    sa.Column('core_code', sa.String(length=64), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_resources_core_code', 'resources', ['core_code'], unique=True)
    op.create_index('ix_resources_is_locked', 'resources', ['is_locked'], unique=False)
    op.create_table('roadmaps',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('slug', sa.String(length=140), nullable=False),
    sa.Column('title', sa.String(length=180), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('role_target', sa.String(length=140), nullable=False),
    sa.Column('difficulty', sa.String(length=32), nullable=False),
    sa.Column('duration_weeks_min', sa.Integer(), nullable=False),
    sa.Column('duration_weeks_max', sa.Integer(), nullable=False),
    sa.Column('is_public', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_roadmaps_slug'), 'roadmaps', ['slug'], unique=True)
    op.create_table('skills',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('normalized_name', sa.String(length=120), nullable=False),
    sa.Column('display_name', sa.String(length=160), nullable=False),
    sa.Column('category', sa.String(length=64), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('normalized_name', name='uq_skills_normalized_name')
    )
    op.create_index('ix_skills_category', 'skills', ['category'], unique=False)
    op.create_table('storage_deletion_intents',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('storage_location_id', sa.String(length=255), nullable=False),
    sa.Column('object_key', sa.String(length=1024), nullable=False),
    sa.Column('requested_at', sa.DateTime(), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('last_attempt_at', sa.DateTime(), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('storage_location_id', 'object_key', name='uq_storage_deletion_intents_object')
    )
    op.create_index('ix_storage_deletion_intents_pending', 'storage_deletion_intents', ['completed_at', 'requested_at'], unique=False)
    op.create_table('users',
    sa.Column('nickname', sa.String(), nullable=True),
    sa.Column('first_name', sa.String(), nullable=True),
    sa.Column('last_name', sa.String(), nullable=True),
    sa.Column('address', sa.String(), nullable=True),
    sa.Column('phone', sa.String(), nullable=True),
    sa.Column('sex', sa.String(), nullable=True),
    sa.Column('age', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('hashed_password', sa.String(length=1024), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_superuser', sa.Boolean(), nullable=False),
    sa.Column('is_verified', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('ai_quota_grants',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('feature', sa.String(length=64), nullable=True),
    sa.Column('daily_extra_units', sa.Integer(), nullable=False),
    sa.Column('starts_at', sa.DateTime(), nullable=False),
    sa.Column('ends_at', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('reason', sa.String(length=120), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_quota_grants_feature'), 'ai_quota_grants', ['feature'], unique=False)
    op.create_index('ix_ai_quota_grants_user_feature_active', 'ai_quota_grants', ['user_id', 'feature', 'is_active'], unique=False)
    op.create_index(op.f('ix_ai_quota_grants_user_id'), 'ai_quota_grants', ['user_id'], unique=False)
    op.create_table('ai_usage_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('feature', sa.String(length=64), nullable=False),
    sa.Column('units', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(length=64), nullable=False),
    sa.Column('reference_type', sa.String(length=64), nullable=True),
    sa.Column('reference_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.String(length=16), server_default='committed', nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_usage_events_created_at'), 'ai_usage_events', ['created_at'], unique=False)
    op.create_index(op.f('ix_ai_usage_events_feature'), 'ai_usage_events', ['feature'], unique=False)
    op.create_index('ix_ai_usage_events_reserved_expiry', 'ai_usage_events', ['user_id', 'feature', 'expires_at'], unique=False, postgresql_where=sa.text("status = 'reserved'"))
    op.create_index('ix_ai_usage_events_user_feature_created', 'ai_usage_events', ['user_id', 'feature', 'created_at'], unique=False)
    op.create_index(op.f('ix_ai_usage_events_user_id'), 'ai_usage_events', ['user_id'], unique=False)
    op.create_index('uq_ai_usage_events_reference', 'ai_usage_events', ['reference_type', 'reference_id'], unique=True, postgresql_where=sa.text("reference_id IS NOT NULL AND status = 'committed'"))
    op.create_table('application_daily_aggregates',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('company_id', sa.UUID(), nullable=False),
    sa.Column('metric_date', sa.Date(), nullable=False),
    sa.Column('applications_created_count', sa.Integer(), nullable=False),
    sa.Column('applications_deleted_count', sa.Integer(), nullable=False),
    sa.Column('status_change_events_count', sa.Integer(), nullable=False),
    sa.Column('entered_applied_count', sa.Integer(), nullable=False),
    sa.Column('entered_in_review_count', sa.Integer(), nullable=False),
    sa.Column('entered_interview_count', sa.Integer(), nullable=False),
    sa.Column('entered_offer_count', sa.Integer(), nullable=False),
    sa.Column('entered_rejected_count', sa.Integer(), nullable=False),
    sa.Column('entered_withdrawn_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('company_id', 'metric_date', name='uq_application_daily_aggregate_company_date')
    )
    op.create_index('ix_application_daily_aggregates_company_metric_date', 'application_daily_aggregates', ['company_id', 'metric_date'], unique=False)
    op.create_table('communities',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('icon', sa.String(length=20), nullable=True),
    sa.Column('activity_status', sa.String(length=32), nullable=True),
    sa.Column('tags', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('member_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('company_recruiters',
    sa.Column('company_id', sa.UUID(), nullable=False),
    sa.Column('first_name', sa.String(), nullable=True),
    sa.Column('last_name', sa.String(), nullable=True),
    sa.Column('role', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('hashed_password', sa.String(length=1024), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_superuser', sa.Boolean(), nullable=False),
    sa.Column('is_verified', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_company_recruiters_company_id', 'company_recruiters', ['company_id'], unique=False)
    op.create_index('ix_company_recruiters_company_id_is_active', 'company_recruiters', ['company_id', 'is_active'], unique=False)
    op.create_index(op.f('ix_company_recruiters_email'), 'company_recruiters', ['email'], unique=True)
    op.create_table('conversation_participants',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('conversation_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('joined_at', sa.DateTime(), nullable=False),
    sa.Column('last_read_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('conversation_id', 'user_id', name='uq_conversation_participant')
    )
    op.create_index('ix_conversation_participants_conversation_id', 'conversation_participants', ['conversation_id'], unique=False)
    op.create_index('ix_conversation_participants_user_id', 'conversation_participants', ['user_id'], unique=False)
    op.create_table('courses',
    sa.CheckConstraint('cost IS NULL OR cost >= 0', name='ck_courses_cost_non_negative'),
    sa.CheckConstraint('duration_hours IS NULL OR duration_hours >= 0', name='ck_courses_duration_hours_non_negative'),
    sa.CheckConstraint('rating IS NULL OR (rating >= 0 AND rating <= 5)', name='ck_courses_rating_five_star'),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('resource_id', sa.UUID(), nullable=True),
    sa.Column('title', sa.String(length=220), nullable=False),
    sa.Column('provider', sa.String(length=120), nullable=False),
    sa.Column('url', sa.String(length=512), nullable=True),
    sa.Column('cost', sa.Float(), nullable=True),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('duration_hours', sa.Float(), nullable=True),
    sa.Column('difficulty', sa.String(length=32), nullable=True),
    sa.Column('rating', sa.Float(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider', 'title', name='uq_courses_provider_title')
    )
    op.create_index('ix_courses_difficulty', 'courses', ['difficulty'], unique=False)
    op.create_index('ix_courses_is_active', 'courses', ['is_active'], unique=False)
    op.create_index('ix_courses_provider', 'courses', ['provider'], unique=False)
    op.create_table('friend_requests',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('sender_id', sa.UUID(), nullable=False),
    sa.Column('receiver_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('responded_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['receiver_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_friend_requests_receiver_id', 'friend_requests', ['receiver_id'], unique=False)
    op.create_index('ix_friend_requests_sender_id', 'friend_requests', ['sender_id'], unique=False)
    op.create_index('ix_friend_requests_status', 'friend_requests', ['status'], unique=False)
    op.create_table('friendships',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('friend_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['friend_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'friend_id', name='uq_friendships_user_friend')
    )
    op.create_index('ix_friendships_friend_id', 'friendships', ['friend_id'], unique=False)
    op.create_index('ix_friendships_user_id', 'friendships', ['user_id'], unique=False)
    op.create_table('job_postings',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('company_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('requirements', sa.Text(), nullable=True),
    sa.Column('responsibilities', sa.Text(), nullable=True),
    sa.Column('location', sa.String(), nullable=True),
    sa.Column('job_type', sa.String(), nullable=True),
    sa.Column('workplace_type', sa.String(), nullable=True),
    sa.Column('seniority_level', sa.String(), nullable=True),
    sa.Column('salary_range', sa.String(), nullable=True),
    sa.Column('benefits', sa.Text(), nullable=True),
    sa.Column('listed_context', sa.String(), nullable=True),
    sa.Column('source_context', sa.String(), nullable=True),
    sa.Column('application_url', sa.String(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.CheckConstraint('expires_at IS NULL OR expires_at >= created_at', name='ck_job_postings_expires_after_created'),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'company_id', name='uq_job_postings_id_company_id')
    )
    op.create_index('ix_job_postings_company_active_expires_created', 'job_postings', ['company_id', 'is_active', 'expires_at', 'created_at'], unique=False)
    op.create_index('ix_job_postings_company_created_at', 'job_postings', ['company_id', 'created_at'], unique=False)
    op.create_table('messages',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('conversation_id', sa.UUID(), nullable=False),
    sa.Column('sender_id', sa.UUID(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_messages_conversation_created_id', 'messages', ['conversation_id', 'created_at', 'id'], unique=False)
    op.create_index('ix_messages_conversation_id', 'messages', ['conversation_id'], unique=False)
    op.create_index('ix_messages_created_at', 'messages', ['created_at'], unique=False)
    op.create_table('posts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('caption', sa.String(length=255), nullable=False),
    sa.Column('url', sa.String(length=255), nullable=False),
    sa.Column('file_type', sa.String(length=50), nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_posts_created_at_id', 'posts', ['created_at', 'id'], unique=False)
    op.create_table('task_outbox',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('task_type', sa.String(length=64), nullable=False),
    sa.Column('payload', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('dedupe_key', sa.String(length=200), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'DISPATCHED', 'FAILED', name='outboxstatus'), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('available_at', sa.DateTime(), nullable=False),
    sa.Column('dispatched_at', sa.DateTime(), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dedupe_key', name='uq_task_outbox_dedupe_key')
    )
    op.create_index('ix_task_outbox_status_available_at', 'task_outbox', ['status', 'available_at'], unique=False)
    op.create_table('resource_modules',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('resource_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=180), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('resumes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('view_url', sa.String(length=255), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('storage_file_id', sa.String(length=255), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('folder_id', sa.String(length=255), nullable=False),
    sa.Column('ai_summary', sa.Text(), nullable=True),
    sa.Column('contact_phone', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('roadmap_stages',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('roadmap_id', sa.UUID(), nullable=False),
    sa.Column('order_index', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=180), nullable=False),
    sa.Column('objective', sa.Text(), nullable=False),
    sa.Column('duration_weeks', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['roadmap_id'], ['roadmaps.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('roadmap_id', 'order_index', name='uq_roadmap_stage_order')
    )
    op.create_index(op.f('ix_roadmap_stages_roadmap_id'), 'roadmap_stages', ['roadmap_id'], unique=False)
    op.create_table('skill_aliases',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('skill_id', sa.UUID(), nullable=False),
    sa.Column('alias', sa.String(length=160), nullable=False),
    sa.Column('source', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('alias', name='uq_skill_aliases_alias')
    )
    op.create_index('ix_skill_aliases_skill_id', 'skill_aliases', ['skill_id'], unique=False)
    op.create_table('user_questionnaires',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('version', sa.String(), nullable=False),
    sa.Column('answers', sa.JSON(), nullable=False),
    sa.Column('results', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('user_roadmaps',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('roadmap_id', sa.UUID(), nullable=False),
    sa.Column('saved_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['roadmap_id'], ['roadmaps.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'roadmap_id', name='uq_user_roadmap')
    )
    op.create_index(op.f('ix_user_roadmaps_roadmap_id'), 'user_roadmaps', ['roadmap_id'], unique=False)
    op.create_index(op.f('ix_user_roadmaps_user_id'), 'user_roadmaps', ['user_id'], unique=False)
    op.create_table('user_stats',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('resume_progress', sa.Integer(), nullable=False),
    sa.Column('linkedin_progress', sa.Integer(), nullable=False),
    sa.Column('interview_progress', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('applications',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('company_id', sa.UUID(), nullable=False),
    sa.Column('assigned_recruiter_id', sa.UUID(), nullable=True),
    sa.Column('job_posting_id', sa.UUID(), nullable=True),
    sa.Column('resume_id', sa.UUID(), nullable=True),
    sa.Column('job_title', sa.String(), nullable=False),
    sa.Column('status', sa.Enum('APPLIED', 'IN_REVIEW', 'INTERVIEW', 'OFFER', 'REJECTED', 'WITHDRAWN', name='applicationstatus'), nullable=False),
    sa.Column('match_strength', sa.Enum('strong_match', 'match', 'weak_match', name='applicationmatchstrength'), nullable=False),
    sa.Column('application_date', sa.DateTime(), nullable=False),
    sa.Column('application_url', sa.String(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint('char_length(btrim(job_title)) > 0', name='ck_applications_job_title_not_blank'),
    sa.ForeignKeyConstraint(['assigned_recruiter_id'], ['company_recruiters.id'], ),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.ForeignKeyConstraint(['job_posting_id', 'company_id'], ['job_postings.id', 'job_postings.company_id'], name='fk_applications_job_posting_id_company_id_job_postings'),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_applications_company_assigned_recruiter_created_at', 'applications', ['company_id', 'assigned_recruiter_id', 'created_at'], unique=False)
    op.create_index('ix_applications_company_status_created_at', 'applications', ['company_id', 'status', 'created_at'], unique=False)
    op.create_index('ix_applications_job_posting_created_at', 'applications', ['job_posting_id', 'created_at'], unique=False)
    op.create_index('ix_applications_resume_id', 'applications', ['resume_id'], unique=False)
    op.create_index('ix_applications_user_created_at', 'applications', ['user_id', 'created_at'], unique=False)
    op.create_index('ux_applications_user_job_posting_not_null', 'applications', ['user_id', 'job_posting_id'], unique=True, postgresql_where=sa.text('job_posting_id IS NOT NULL'))
    op.create_table('community_members',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('community_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('joined_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('community_id', 'user_id', name='uq_community_member')
    )
    op.create_table('community_posts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('community_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('post_type', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('course_skills',
    sa.CheckConstraint('coverage_score IS NULL OR (coverage_score >= 0 AND coverage_score <= 1)', name='ck_course_skills_coverage_score_fraction'),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('course_id', sa.UUID(), nullable=False),
    sa.Column('skill_id', sa.UUID(), nullable=False),
    sa.Column('coverage_score', sa.Float(), nullable=True),
    sa.Column('is_prerequisite', sa.Boolean(), nullable=False),
    sa.Column('evidence_text', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('course_id', 'skill_id', name='uq_course_skills_course_skill')
    )
    op.create_index('ix_course_skills_course_id', 'course_skills', ['course_id'], unique=False)
    op.create_index('ix_course_skills_skill_id', 'course_skills', ['skill_id'], unique=False)
    op.create_table('job_analysis',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('resume_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', name='jobstatus'), nullable=False),
    sa.Column('keywords', sa.Text(), nullable=True),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('lease_expires_at', sa.DateTime(), nullable=True),
    sa.Column('provider_attempted_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_job_analysis_active_lease', 'job_analysis', ['lease_expires_at'], unique=False, postgresql_where=sa.text("status IN ('PENDING', 'PROCESSING')"))
    op.create_index('uq_job_analysis_active_per_resume', 'job_analysis', ['user_id', 'resume_id'], unique=True, postgresql_where=sa.text("status IN ('PENDING', 'PROCESSING')"))
    op.create_table('job_skills',
    sa.CheckConstraint('importance_score IS NULL OR (importance_score >= 0 AND importance_score <= 1)', name='ck_job_skills_importance_score_fraction'),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('job_posting_id', sa.UUID(), nullable=True),
    sa.Column('skill_id', sa.UUID(), nullable=False),
    sa.Column('target_role', sa.String(length=120), nullable=True),
    sa.Column('importance_score', sa.Float(), nullable=True),
    sa.Column('extraction_method', sa.String(length=64), nullable=False),
    sa.Column('evidence_text', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_job_skills_job_posting_id', 'job_skills', ['job_posting_id'], unique=False)
    op.create_index('ix_job_skills_skill_id', 'job_skills', ['skill_id'], unique=False)
    op.create_index('ix_job_skills_target_role', 'job_skills', ['target_role'], unique=False)
    op.create_index('uq_job_skills_posting_skill_method', 'job_skills', ['job_posting_id', 'skill_id', 'extraction_method'], unique=True, postgresql_where=sa.text('job_posting_id IS NOT NULL'))
    op.create_table('optimization_runs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('resume_id', sa.UUID(), nullable=True),
    sa.Column('target_role', sa.String(length=120), nullable=False),
    sa.Column('budget', sa.Float(), nullable=True),
    sa.Column('available_hours', sa.Float(), nullable=True),
    sa.Column('max_courses', sa.Integer(), nullable=True),
    sa.Column('objective_version', sa.String(length=40), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('total_score', sa.Float(), nullable=True),
    sa.Column('total_cost', sa.Float(), nullable=True),
    sa.Column('total_hours', sa.Float(), nullable=True),
    sa.Column('skill_coverage', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('constraints', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_optimization_runs_resume_id', 'optimization_runs', ['resume_id'], unique=False)
    op.create_index('ix_optimization_runs_status', 'optimization_runs', ['status'], unique=False)
    op.create_index('ix_optimization_runs_target_role', 'optimization_runs', ['target_role'], unique=False)
    op.create_index('ix_optimization_runs_user_id', 'optimization_runs', ['user_id'], unique=False)
    op.create_table('resource_lessons',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('module_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=220), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('content_type', sa.String(length=32), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('reading_time_minutes', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['module_id'], ['resource_modules.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('resume_course_evaluations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('resume_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.Enum('pending', 'completed', 'failed', name='resumecourseevaluationstatus'), nullable=False),
    sa.Column('overall_score', sa.Float(), nullable=True),
    sa.Column('llm_confidence', sa.Float(), nullable=True),
    sa.Column('pass_status', sa.Boolean(), nullable=True),
    sa.Column('report_text', sa.Text(), nullable=True),
    sa.Column('structured_payload', sa.Text(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('prompt_version', sa.String(length=40), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_resume_course_evaluations_created_at', 'resume_course_evaluations', ['created_at'], unique=False)
    op.create_index(op.f('ix_resume_course_evaluations_resume_id'), 'resume_course_evaluations', ['resume_id'], unique=False)
    op.create_index(op.f('ix_resume_course_evaluations_user_id'), 'resume_course_evaluations', ['user_id'], unique=False)
    op.create_table('resume_embeddings',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('resume_id', sa.UUID(), nullable=False),
    sa.Column('model_name', sa.String(length=120), nullable=False),
    sa.Column('dims', sa.Integer(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=True),
    sa.Column('text_fingerprint', sa.String(length=64), nullable=True),
    sa.Column('fingerprint_version', sa.String(length=16), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_resume_embeddings_embedding_hnsw', 'resume_embeddings', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_with={'m': '16', 'ef_construction': '64'}, postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index(op.f('ix_resume_embeddings_resume_id'), 'resume_embeddings', ['resume_id'], unique=False)
    op.create_index('ix_resume_embeddings_resume_model', 'resume_embeddings', ['resume_id', 'model_name'], unique=True)
    op.create_table('resume_skills',
    sa.CheckConstraint("status IN ('detected', 'confirmed', 'rejected', 'manual')", name='ck_resume_skills_status'),
    sa.CheckConstraint('confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)', name='ck_resume_skills_confidence_score_fraction'),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('resume_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('skill_id', sa.UUID(), nullable=False),
    sa.Column('confidence_score', sa.Float(), nullable=True),
    sa.Column('extraction_method', sa.String(length=64), nullable=False),
    sa.Column('evidence_text', sa.Text(), nullable=True),
    sa.Column('source_section', sa.String(length=80), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('reviewed_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('resume_id', 'skill_id', 'extraction_method', name='uq_resume_skills_resume_skill_method')
    )
    op.create_index('ix_resume_skills_resume_id', 'resume_skills', ['resume_id'], unique=False)
    op.create_index('ix_resume_skills_skill_id', 'resume_skills', ['skill_id'], unique=False)
    op.create_index('ix_resume_skills_status', 'resume_skills', ['status'], unique=False)
    op.create_index('ix_resume_skills_user_id', 'resume_skills', ['user_id'], unique=False)
    op.create_table('stage_projects',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('stage_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=220), nullable=False),
    sa.Column('brief', sa.Text(), nullable=False),
    sa.Column('acceptance_criteria', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('rubric', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('estimated_hours', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['stage_id'], ['roadmap_stages.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stage_projects_stage_id'), 'stage_projects', ['stage_id'], unique=False)
    op.create_table('stage_tasks',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('stage_id', sa.UUID(), nullable=False),
    sa.Column('order_index', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=220), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('estimated_hours', sa.Integer(), nullable=False),
    sa.Column('task_type', sa.Enum('learn', 'practice', 'build', 'read', 'watch', name='task_type_enum'), nullable=False),
    sa.Column('resource_url', sa.String(length=600), nullable=True),
    sa.Column('resource_title', sa.String(length=220), nullable=True),
    sa.ForeignKeyConstraint(['stage_id'], ['roadmap_stages.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('stage_id', 'order_index', name='uq_stage_task_order')
    )
    op.create_index(op.f('ix_stage_tasks_stage_id'), 'stage_tasks', ['stage_id'], unique=False)
    op.create_table('user_stage_progress',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('stage_id', sa.UUID(), nullable=False),
    sa.Column('progress_percent', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['stage_id'], ['roadmap_stages.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'stage_id', name='uq_user_stage_progress')
    )
    op.create_index(op.f('ix_user_stage_progress_stage_id'), 'user_stage_progress', ['stage_id'], unique=False)
    op.create_index(op.f('ix_user_stage_progress_user_id'), 'user_stage_progress', ['user_id'], unique=False)
    op.create_table('application_status_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('application_id', sa.UUID(), nullable=True),
    sa.Column('company_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('job_posting_id', sa.UUID(), nullable=True),
    sa.Column('triggered_by_user_id', sa.UUID(), nullable=True),
    sa.Column('triggered_by_company_recruiter_id', sa.UUID(), nullable=True),
    sa.Column('event_type', sa.Enum('CREATED', 'STATUS_CHANGED', 'DELETED', name='applicationeventtype'), nullable=False),
    sa.Column('from_status', sa.Enum('APPLIED', 'IN_REVIEW', 'INTERVIEW', 'OFFER', 'REJECTED', 'WITHDRAWN', name='applicationstatus'), nullable=True),
    sa.Column('to_status', sa.Enum('APPLIED', 'IN_REVIEW', 'INTERVIEW', 'OFFER', 'REJECTED', 'WITHDRAWN', name='applicationstatus'), nullable=True),
    sa.Column('occurred_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['triggered_by_company_recruiter_id'], ['company_recruiters.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['triggered_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_application_status_events_application_occurred_at', 'application_status_events', ['application_id', 'occurred_at'], unique=False)
    op.create_index('ix_application_status_events_company_occurred_at', 'application_status_events', ['company_id', 'occurred_at'], unique=False)
    op.create_index('ix_application_status_events_event_type_occurred_at', 'application_status_events', ['event_type', 'occurred_at'], unique=False)
    op.create_table('community_post_comments',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('post_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['community_posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('community_post_likes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('post_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['community_posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('post_id', 'user_id', name='uq_community_post_like')
    )
    op.create_table('email_notification_logs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('application_id', sa.UUID(), nullable=True),
    sa.Column('company_id', sa.UUID(), nullable=True),
    sa.Column('recruiter_id', sa.UUID(), nullable=True),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('recipient_email', sa.String(length=320), nullable=False),
    sa.Column('recipient_name', sa.String(length=255), nullable=True),
    sa.Column('template_key', sa.String(length=128), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('body_preview', sa.Text(), nullable=False),
    sa.Column('payload_json', sa.Text(), nullable=True),
    sa.Column('delivery_status', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('sent_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['recruiter_id'], ['company_recruiters.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_email_notification_logs_application_created_at', 'email_notification_logs', ['application_id', 'created_at'], unique=False)
    op.create_index('ix_email_notification_logs_recipient_created_at', 'email_notification_logs', ['recipient_email', 'created_at'], unique=False)
    op.create_table('interview_availabilities',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('application_id', sa.UUID(), nullable=False),
    sa.Column('company_id', sa.UUID(), nullable=False),
    sa.Column('recruiter_id', sa.UUID(), nullable=True),
    sa.Column('candidate_id', sa.UUID(), nullable=False),
    sa.Column('starts_at', sa.DateTime(), nullable=False),
    sa.Column('ends_at', sa.DateTime(), nullable=False),
    sa.Column('timezone', sa.String(length=64), nullable=False),
    sa.Column('status', sa.Enum('available', 'booked', 'cancelled', name='interviewavailabilitystatus'), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('booked_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['candidate_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recruiter_id'], ['company_recruiters.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_interview_availabilities_application_status', 'interview_availabilities', ['application_id', 'status'], unique=False)
    op.create_index('ix_interview_availabilities_company_start', 'interview_availabilities', ['company_id', 'starts_at'], unique=False)
    op.create_index('uq_interview_availabilities_booked_per_application', 'interview_availabilities', ['application_id'], unique=True, postgresql_where=sa.text("status = 'booked'"))
    op.create_table('resource_enrollments',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('resource_id', sa.UUID(), nullable=False),
    sa.Column('last_opened_lesson_id', sa.UUID(), nullable=True),
    sa.Column('enrolled_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['last_opened_lesson_id'], ['resource_lessons.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'resource_id', name='uq_resource_enrollments_user_resource')
    )
    op.create_index(op.f('ix_resource_enrollments_resource_id'), 'resource_enrollments', ['resource_id'], unique=False)
    op.create_index(op.f('ix_resource_enrollments_user_id'), 'resource_enrollments', ['user_id'], unique=False)
    op.create_table('resource_lesson_progress',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('resource_id', sa.UUID(), nullable=True),
    sa.Column('lesson_id', sa.UUID(), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('last_opened_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['lesson_id'], ['resource_lessons.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'lesson_id', name='uq_resource_lesson_progress_user_lesson')
    )
    op.create_index(op.f('ix_resource_lesson_progress_lesson_id'), 'resource_lesson_progress', ['lesson_id'], unique=False)
    op.create_index(op.f('ix_resource_lesson_progress_resource_id'), 'resource_lesson_progress', ['resource_id'], unique=False)
    op.create_index(op.f('ix_resource_lesson_progress_user_id'), 'resource_lesson_progress', ['user_id'], unique=False)
    op.create_table('user_project_submissions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('repo_url', sa.String(length=600), nullable=True),
    sa.Column('live_url', sa.String(length=600), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('status', sa.Enum('draft', 'submitted', 'reviewed', name='project_submission_status_enum'), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['stage_projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'project_id', name='uq_user_project_submission')
    )
    op.create_index(op.f('ix_user_project_submissions_project_id'), 'user_project_submissions', ['project_id'], unique=False)
    op.create_index(op.f('ix_user_project_submissions_user_id'), 'user_project_submissions', ['user_id'], unique=False)
    op.create_table('user_task_progress',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('task_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.Enum('not_started', 'in_progress', 'completed', name='task_progress_status_enum'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['task_id'], ['stage_tasks.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'task_id', name='uq_user_task_progress')
    )
    op.create_index(op.f('ix_user_task_progress_task_id'), 'user_task_progress', ['task_id'], unique=False)
    op.create_index(op.f('ix_user_task_progress_user_id'), 'user_task_progress', ['user_id'], unique=False)
    # ### end generated block ###


def verify_against_metadata(connection, metadata) -> list:
    """Return the structural differences between the database and the models.

    An empty list is the precondition for stamping: it says the database
    Alembic just built is the one the application expects, rather than
    something that merely looks close enough.
    """
    return compare_metadata(MigrationContext.configure(connection), metadata)


def bootstrap(connection, script_directory, metadata) -> None:
    """Create, verify and stamp an empty database.

    Raises :class:`BaselineVerificationError` without stamping when the result
    does not match the metadata, so a partial or stale baseline surfaces at
    deploy time instead of becoming a database nobody can migrate, and
    :class:`UnsupportedDialectError` before touching a database it cannot build.
    """
    require_supported_dialect(connection)

    LOGGER.info("empty database detected: applying the baseline schema")
    create_schema(connection)

    differences = verify_against_metadata(connection, metadata)
    if differences:
        rendered = "\n".join(f"  - {difference}" for difference in differences)
        raise BaselineVerificationError(
            "The baseline schema does not match the mapped metadata; the "
            "database was NOT stamped. Regenerate alembic/baseline.py.\n"
            + rendered
        )

    MigrationContext.configure(connection).stamp(script_directory, "head")
    LOGGER.info("baseline applied and stamped at head")
