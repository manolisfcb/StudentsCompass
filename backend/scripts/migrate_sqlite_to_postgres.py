import os
import sys
from pathlib import Path
import json
import uuid
from typing import Any, Dict, List, Type

from sqlalchemy import create_engine, select, insert, text
from sqlalchemy.orm import Session

# Ensure project root is on sys.path for "app" imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import ORM models and Base metadata
from app.db import Base
from app.models.userModel import User
from app.models.postModel import PostModel
from app.models.questionnaireModel import UserQuestionnaire

# Source (SQLite) and Target (PostgreSQL) URLs.
# No default target: a hardcoded URL both leaks a credential and risks writing
# to the wrong database. The operator names the destination explicitly.
SQLITE_URL = os.environ.get("SQLITE_URL", "sqlite:///./test.db")


def _resolve_postgres_url() -> str:
    url = os.environ.get("POSTGRES_URL", "").strip()
    if not url:
        raise SystemExit(
            "POSTGRES_URL is not set. Export the target database URL before "
            "running this migration, e.g.\n"
            "  POSTGRES_URL='postgresql+psycopg://USER:PASSWORD@HOST/DB' \\\n"
            "    python scripts/migrate_sqlite_to_postgres.py\n"
            "This script writes to that database; it has no default on purpose."
        )
    return url


# Ordered by FK dependencies
MODELS = [User, PostModel, UserQuestionnaire]


def _coerce_values(model: Type, row_obj: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    for col in model.__table__.columns:
        val = getattr(row_obj, col.name)
        if val is None:
            data[col.name] = None
            continue
        # Handle UUID stored as string in SQLite
        if getattr(col.type, "as_uuid", False):
            if isinstance(val, str):
                try:
                    val = uuid.UUID(val)
                except ValueError:
                    pass
        # Handle JSON stored as TEXT in SQLite
        if col.type.__class__.__name__ == "JSON" and isinstance(val, str):
            try:
                val = json.loads(val)
            except json.JSONDecodeError:
                pass
        data[col.name] = val
    return data


def main() -> None:
    # Create engines
    src_engine = create_engine(SQLITE_URL, future=True)
    tgt_engine = create_engine(_resolve_postgres_url(), future=True)

    # Ensure target schema exists
    Base.metadata.create_all(tgt_engine)

    inserted_total = 0

    with Session(src_engine) as s_src, Session(tgt_engine) as s_tgt:
        for model in MODELS:
            # Skip if target already has rows
            tgt_count = s_tgt.execute(select(text("count(*)")).select_from(model.__table__)).scalar_one()
            if tgt_count and int(tgt_count) > 0:
                print(f"Skipping {model.__tablename__}: target already has {tgt_count} rows")
                continue

            rows = s_src.execute(select(model)).scalars().all()
            if not rows:
                print(f"No rows to migrate for {model.__tablename__}")
                continue

            payload: List[Dict[str, Any]] = [_coerce_values(model, r) for r in rows]
            s_tgt.execute(insert(model).values(payload))
            s_tgt.commit()
            print(f"Inserted {len(payload)} rows into {model.__tablename__}")
            inserted_total += len(payload)

    print(f"Done. Inserted total rows: {inserted_total}")
    print("Tip: If you plan to use Alembic, you can stamp head now:\n  uv run alembic stamp head")


if __name__ == "__main__":
    main()
