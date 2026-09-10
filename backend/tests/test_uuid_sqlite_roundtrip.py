"""TASK-064 — la lane SQLite no debe reinterpretar un UUID como número.

`sqlalchemy.dialects.postgresql.UUID` emite el DDL ``UUID``, que SQLite no reconoce en
ninguna de sus reglas de afinidad y por tanto trata como NUMERIC. Un UUID cuyos 32 dígitos
hexadecimales parsean como número vuelve entonces como `int` o `float` y rompe el test que
lo tocó, sea cual sea lo que ese test afirmara. `app.db_types.UUID` lo corrige enlazando a
``VARCHAR(36)`` fuera de PostgreSQL.

Los casos son los de la ficha y **no** se evitan generando UUIDs "seguros" en los fixtures:
eso ocultaría el defecto en vez de corregirlo.
"""

import uuid

import pytest
from sqlalchemy import Column, MetaData, Table, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_types import UUID
from app.models.applicationModel import ApplicationModel
from app.models.userModel import User

# `UUID(int=1)` son 32 dígitos decimales: SQLite lo guardaba como INTEGER.
# El hex con una `e` entre dígitos es notación científica: lo guardaba como REAL, y ahí
# además perdía precisión. Es el caso que se observó dos veces en quince corridas.
NUMERIC_LOOKING_UUIDS = [
    pytest.param(uuid.UUID(int=1), id="all-decimal-digits"),
    pytest.param(uuid.UUID(hex="12345678901234567890123456789e12"), id="scientific-notation"),
    pytest.param(uuid.UUID(int=0), id="zero"),
]

_metadata = MetaData()
_probe = Table(
    "uuid_roundtrip_probe",
    _metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
)


@pytest.fixture
async def probe_table(db_session: AsyncSession):
    conn = await db_session.connection()
    await conn.run_sync(_metadata.create_all)
    yield _probe
    await conn.run_sync(_metadata.drop_all)


@pytest.mark.asyncio
@pytest.mark.parametrize("value", NUMERIC_LOOKING_UUIDS)
async def test_numeric_looking_uuid_survives_roundtrip(db_session, probe_table, value):
    await db_session.execute(insert(probe_table).values(id=value))
    stored = await db_session.execute(select(probe_table.c.id).where(probe_table.c.id == value))
    assert stored.scalar_one() == value


@pytest.mark.asyncio
async def test_uuid_column_declares_a_text_affinity_type(db_session, probe_table):
    """La afinidad es la causa raíz; comprobarla directamente no depende del azar."""
    conn = await db_session.connection()
    declared = await conn.exec_driver_sql(
        "select type from pragma_table_info('uuid_roundtrip_probe') where name = 'id'"
    )
    assert declared.scalar_one().upper().startswith("VARCHAR")

    await db_session.execute(insert(probe_table).values(id=uuid.UUID(int=1)))
    stored_type = await conn.exec_driver_sql("select typeof(id) from uuid_roundtrip_probe")
    assert stored_type.scalar_one() == "text"


@pytest.mark.asyncio
async def test_many_random_uuids_roundtrip(db_session, probe_table):
    values = [uuid.uuid4() for _ in range(1000)]
    await db_session.execute(insert(probe_table), [{"id": value} for value in values])
    rows = await db_session.execute(select(probe_table.c.id))
    assert set(rows.scalars().all()) == set(values)


@pytest.mark.asyncio
async def test_foreign_keys_share_the_representation_of_users_id(
    db_session, test_user, test_company
):
    """`users.id` usa el `GUID` de fastapi-users, que guarda 36 caracteres con guiones.

    Mientras las FK usaban `postgresql.UUID` guardaban 32 sin guiones, así que en la lane
    SQLite un join entre las dos no podía casar nunca, hubiera o no filas. El tipo
    compartido alinea las dos representaciones.
    """
    application = ApplicationModel(
        user_id=test_user.id,
        company_id=test_company.id,
        job_title="Backend Engineer",
    )
    db_session.add(application)
    await db_session.flush()

    joined = await db_session.execute(
        select(ApplicationModel.id)
        .join(User, User.id == ApplicationModel.user_id)
        .where(User.id == test_user.id)
    )
    assert joined.scalars().all() == [application.id]

    conn = await db_session.connection()
    stored_user_id = await conn.exec_driver_sql("select id from users limit 1")
    stored_fk = await conn.exec_driver_sql("select user_id from applications limit 1")
    assert stored_user_id.scalar_one() == stored_fk.scalar_one()
