"""Tipos de columna compartidos que se comportan igual en PostgreSQL y en la lane de tests.

`sqlalchemy.dialects.postgresql.UUID` emite el literal DDL ``UUID``. SQLite no reconoce
ese nombre en ninguna de sus reglas de afinidad ("INT", "CHAR"/"CLOB"/"TEXT", "BLOB",
"REAL"/"FLOA"/"DOUB"), así que le aplica la regla de descarte: **afinidad NUMERIC**. Cuando
los 32 dígitos hexadecimales de un UUID parsean como número, SQLite los guarda como `int` o
`real` y los devuelve así; `uuid.UUID(hex=<número>)` revienta entonces con
``AttributeError: 'int'/'float' object has no attribute 'replace'``, y en el caso `real` el
valor ya venía corrompido por la pérdida de precisión del flotante.

`UUID` de este módulo enlaza a `String(36)` fuera de PostgreSQL, que compila a
``VARCHAR(36)``: contiene "CHAR", luego tiene afinidad TEXT y ningún valor se reinterpreta.
La forma almacenada es la canónica con guiones, la misma que usa el `GUID` de
fastapi-users para ``users.id``, de modo que un FK y su destino comparan iguales en la lane.

En PostgreSQL no cambia nada: se delega en el tipo `uuid` nativo y ni el bind ni el result
processor de este decorador tocan el valor.
"""

import uuid as _uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.types import TypeDecorator

__all__ = ["UUID"]


class UUID(TypeDecorator):
    """UUID nativo en PostgreSQL, `VARCHAR(36)` con guiones en el resto de dialectos."""

    impl = PGUUID
    cache_ok = True

    def __init__(self, as_uuid: bool = True, **kwargs) -> None:
        self.as_uuid = as_uuid
        super().__init__(**kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGUUID(as_uuid=self.as_uuid))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        # En PostgreSQL el trabajo lo hace el tipo nativo; aquí solo se pasa el valor.
        if value is None or dialect.name == "postgresql":
            return value
        if not isinstance(value, _uuid.UUID):
            value = _uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None or dialect.name == "postgresql":
            return value
        if not self.as_uuid:
            return str(value)
        if not isinstance(value, _uuid.UUID):
            value = _uuid.UUID(str(value))
        return value
