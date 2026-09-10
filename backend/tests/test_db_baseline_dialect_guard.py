"""TASK-069 — un bootstrap no puede sellar lo que no ha creado.

Todo el bloque DDL generado de `create_schema()` estaba indentado dentro del
``if connection.dialect.name == "postgresql":`` que precede al ``CREATE EXTENSION``. Fuera
de PostgreSQL la función no creaba ni una tabla y devolvía como si hubiera funcionado, y
`bootstrap()` seguía hasta ``stamp(script_directory, "head")``: una base **vacía** quedaba
marcada como si tuviera el esquema completo, y a partir de ahí `alembic upgrade` no tenía
nada que aplicar mientras cada consulta fallaba con «relation does not exist».

Estos tests corren en la lane rápida, sin PostgreSQL, porque el camino que fijan es
precisamente el de *no*-PostgreSQL.
"""

import sqlalchemy as sa
import pytest

from app.db_baseline import (
    UnsupportedDialectError,
    bootstrap,
    create_schema,
    database_is_empty,
    require_supported_dialect,
)


@pytest.fixture
def sqlite_connection():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        yield connection


def test_create_schema_refuses_an_unsupported_dialect(sqlite_connection):
    with pytest.raises(UnsupportedDialectError):
        create_schema(sqlite_connection)


def test_refusal_leaves_the_database_untouched(sqlite_connection):
    """Rechazar antes de empezar, no a mitad del DDL.

    Sin la guarda, el bloque generado llegaba a crear 28 tablas antes de morir en
    ``no such function: btrim`` — un esquema a medias, que es peor que ninguno.
    """
    with pytest.raises(UnsupportedDialectError):
        create_schema(sqlite_connection)
    assert sa.inspect(sqlite_connection).get_table_names() == []


def test_bootstrap_does_not_stamp_an_unsupported_dialect(sqlite_connection):
    assert database_is_empty(sqlite_connection)

    with pytest.raises(UnsupportedDialectError):
        bootstrap(sqlite_connection, script_directory=None, metadata=sa.MetaData())

    tables = sa.inspect(sqlite_connection).get_table_names()
    assert "alembic_version" not in tables
    assert tables == []
    assert database_is_empty(sqlite_connection)


def test_generated_ddl_is_not_nested_under_the_extension_guard():
    """La causa raíz era de indentación, así que se fija como tal.

    Un test de comportamiento en SQLite ya no puede distinguir «el bloque está fuera del
    `if`» de «la guarda lo rechazó antes», porque las dos cosas producen la misma
    excepción. Esto sí distingue, y es lo que impide que la regresión vuelva a entrar
    silenciosamente al regenerar la baseline.
    """
    import inspect

    import app.db_baseline as module

    source = inspect.getsource(module.create_schema).splitlines()
    start = next(i for i, line in enumerate(source) if "### generated from Base.metadata" in line)
    end = next(i for i, line in enumerate(source) if "### end generated block ###" in line)

    body = [line for line in source[start + 1 : end] if line.strip()]
    assert body, "el bloque generado está vacío"
    # Cuerpo de la función = 4 espacios. 8 significaría estar dentro de un `if`.
    assert all(line.startswith("    ") and not line.startswith("        ") for line in body)


def test_require_supported_dialect_accepts_postgresql():
    class _Dialect:
        name = "postgresql"

    class _Connection:
        dialect = _Dialect()

    require_supported_dialect(_Connection())  # no levanta
