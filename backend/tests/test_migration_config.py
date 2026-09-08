"""Migration configuration must carry no credential and no implicit target.

F-01 put a live database URL — user and password — into ``alembic.ini`` and
into the SQLite→PostgreSQL script, both versioned. These tests keep it out and
pin the resolution rules that replaced it.
"""
from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# A URL with embedded credentials: scheme://user:password@host
CREDENTIAL_URL = re.compile(r"[a-z0-9+]+://[^/\s:]+:[^/\s@]+@[^/\s]+", re.I)

VERSIONED_CONFIG = [
    ROOT / "alembic.ini",
    ROOT / "alembic" / "env.py",
    ROOT / "scripts" / "migrate_sqlite_to_postgres.py",
]


def _redact(match: re.Match) -> str:
    return re.sub(r"://[^:]+:[^@]+@", "://<user>:<redacted>@", match.group(0))


@pytest.mark.parametrize("path", VERSIONED_CONFIG, ids=lambda p: p.name)
def test_no_credentials_in_versioned_migration_config(path: Path):
    findings = [
        _redact(match)
        for match in CREDENTIAL_URL.finditer(path.read_text())
        # The placeholder in the operator-facing error message is not a secret.
        if "USER:PASSWORD" not in match.group(0)
    ]

    assert not findings, f"credential-shaped URL in {path.name}: {findings}"


def test_alembic_ini_does_not_pin_a_database():
    """An active sqlalchemy.url would let the migrator diverge from the app."""
    active = [
        line
        for line in (ROOT / "alembic.ini").read_text().splitlines()
        if line.strip().startswith("sqlalchemy.url")
    ]

    assert active == [], f"alembic.ini pins a database: {active}"


# --- URL resolution ---------------------------------------------------------

def _load_env_module():
    """Import alembic/env.py for its helpers without running the migrations."""
    spec = importlib.util.spec_from_file_location(
        "alembic_env_under_test", ROOT / "alembic" / "env.py"
    )
    module = importlib.util.module_from_spec(spec)
    # env.py runs migrations on import; stop after the helpers are defined.
    source = (ROOT / "alembic" / "env.py").read_text()
    helpers = source[: source.index("# this is the Alembic Config object")]
    exec(compile(helpers, str(ROOT / "alembic" / "env.py"), "exec"), module.__dict__)
    return module


def test_missing_configuration_fails_loudly(monkeypatch):
    env = _load_env_module()
    monkeypatch.delenv("ALEMBIC_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError) as excinfo:
        env.resolve_migration_url()

    assert "DATABASE_URL" in str(excinfo.value)


def test_migrator_defaults_to_the_application_database(monkeypatch):
    """Same variable as app/db.py, so the two cannot target different servers."""
    env = _load_env_module()
    monkeypatch.delenv("ALEMBIC_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@127.0.0.1:5432/db")

    # The async driver is translated, nothing else: same user, host and database.
    assert env.resolve_migration_url() == "postgresql+psycopg://u:p@127.0.0.1:5432/db"


def test_explicit_override_wins_for_the_migrator_only(monkeypatch):
    env = _load_env_module()
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@127.0.0.1:5432/pooled")
    monkeypatch.setenv(
        "ALEMBIC_DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:5432/direct"
    )

    assert env.resolve_migration_url().endswith("/direct")


def test_redaction_never_exposes_the_credential():
    env = _load_env_module()

    redacted = env._redacted("postgresql+psycopg://neondb_owner:sup3rsecret@host.example/db")

    assert "sup3rsecret" not in redacted
    assert "neondb_owner" not in redacted
    assert "host.example" in redacted


# --- Data migration script --------------------------------------------------

def test_migration_script_has_no_default_target(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "migrate_script_under_test", ROOT / "scripts" / "migrate_sqlite_to_postgres.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.delenv("POSTGRES_URL", raising=False)
    with pytest.raises(SystemExit) as excinfo:
        module._resolve_postgres_url()
    assert "POSTGRES_URL" in str(excinfo.value)

    monkeypatch.setenv("POSTGRES_URL", "postgresql+psycopg://u:p@127.0.0.1:5432/db")
    assert module._resolve_postgres_url().endswith("/db")
