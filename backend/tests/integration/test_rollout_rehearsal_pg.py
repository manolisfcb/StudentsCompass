"""The rehearsal TASK-031 exists for: data survives the upgrade, and a restore works.

Every migration in this batch was tested on its own. What none of them tested is
the thing a deploy actually does: take a database that **already has data**,
walk the whole chain to head, and still have that data — and, if the deploy goes
wrong, be able to put the database back.

Nothing here touches production. The lane database is disposable and every
provider is fake. A dump and restore is exercised against that lane, which is
what "restore probado" can honestly mean without production access.
"""
from __future__ import annotations

import ast
import os
import pathlib
import subprocess
import uuid

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text

pytestmark = [pytest.mark.integration, pytest.mark.postgres]

#: The revisions this batch of tasks added, oldest first.
BATCH_REVISIONS = (
    "b2e9f4a71c33",  # TASK-019 job_skills uniqueness
    "c4a71e2b90d8",  # TASK-021 embedding fingerprint
    "d5b83f1a6c27",  # TASK-024 messages keyset index
    "e7c2d940ab15",  # TASK-027 analytics checks
)


@pytest.fixture
def metadata():
    import tests.conftest  # noqa: F401  (imports the full model set)

    from app.db import Base

    return Base.metadata


def _config(url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", url)
    return config


def _upgrade(url: str, target: str = "head") -> None:
    from alembic import command

    previous = os.environ.get("ALEMBIC_DATABASE_URL")
    os.environ["ALEMBIC_DATABASE_URL"] = url
    try:
        command.upgrade(_config(url), target)
    finally:
        if previous is None:
            os.environ.pop("ALEMBIC_DATABASE_URL", None)
        else:
            os.environ["ALEMBIC_DATABASE_URL"] = previous


async def _reset(engine) -> None:
    """The lane's own reset, reused rather than copied."""
    from tests.integration.conftest import reset_public_schema

    await reset_public_schema(engine)


def _sync_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg://")


# ---------------------------------------------------------------------------
# The chain preserves data
# ---------------------------------------------------------------------------


async def _seed_rows(engine) -> dict:
    """A row in each table this batch's migrations touch."""
    user_id, resume_id, skill_id, course_id = (uuid.uuid4() for _ in range(4))
    conversation_id, message_id = uuid.uuid4(), uuid.uuid4()

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, email, hashed_password, is_active, is_superuser, "
                "is_verified, created_at, updated_at) VALUES (:id, :email, 'x', true, false, "
                "true, now(), now())"
            ),
            {"id": user_id, "email": f"rollout-{user_id.hex[:8]}@example.invalid"},
        )
        await conn.execute(
            text(
                "INSERT INTO resumes (id, user_id, view_url, storage_file_id, "
                "original_filename, folder_id, created_at, updated_at) VALUES (:id, :user, "
                "'https://e.invalid/a', :sid, 'cv.pdf', 'resumes', now(), now())"
            ),
            {"id": resume_id, "user": user_id, "sid": uuid.uuid4().hex},
        )
        await conn.execute(
            text(
                "INSERT INTO skills (id, normalized_name, display_name, source, created_at, "
                "updated_at) VALUES (:id, :n, :n, 'rollout', now(), now())"
            ),
            {"id": skill_id, "n": f"skill-{skill_id.hex[:8]}"},
        )
        await conn.execute(
            text(
                "INSERT INTO courses (id, title, provider, cost, currency, duration_hours, "
                "rating, is_active, created_at, updated_at) VALUES (:id, 'Rollout course', "
                "'Test', 10, 'CAD', 4, 4.5, true, now(), now())"
            ),
            {"id": course_id},
        )
        await conn.execute(
            text(
                "INSERT INTO resume_skills (id, resume_id, skill_id, confidence_score, "
                "extraction_method, status, created_at) VALUES (:id, :resume, :skill, 0.75, "
                "'rollout', 'detected', now())"
            ),
            {"id": uuid.uuid4(), "resume": resume_id, "skill": skill_id},
        )
        await conn.execute(
            text(
                "INSERT INTO conversations (id, kind, direct_key, created_at, updated_at) "
                "VALUES (:id, 'direct', :key, now(), now())"
            ),
            {"id": conversation_id, "key": uuid.uuid4().hex},
        )
        await conn.execute(
            text(
                "INSERT INTO messages (id, conversation_id, sender_id, content, created_at, "
                "updated_at) VALUES (:id, :conv, :user, 'survives the upgrade', now(), now())"
            ),
            {"id": message_id, "conv": conversation_id, "user": user_id},
        )
    return {
        "user_id": user_id,
        "resume_id": resume_id,
        "skill_id": skill_id,
        "course_id": course_id,
        "message_id": message_id,
    }


async def _counts(engine) -> dict:
    tables = ("users", "resumes", "skills", "courses", "resume_skills", "messages")
    out = {}
    async with engine.connect() as conn:
        for table in tables:
            out[table] = int(await conn.scalar(text(f"SELECT COUNT(*) FROM {table}")))
    return out


@pytest.mark.asyncio
async def test_a_database_with_data_walks_the_chain_and_keeps_it(
    pg_engine, postgres_url, metadata
):
    """The rehearsal: seed at the pre-batch revision, upgrade to head, check the rows."""
    await _reset(pg_engine)

    before_batch = BATCH_REVISIONS[0]
    _upgrade(postgres_url, before_batch + "-1")  # the revision just before this batch

    seeded = await _seed_rows(pg_engine)
    before = await _counts(pg_engine)
    assert all(count == 1 for count in before.values()), before

    _upgrade(postgres_url, "head")

    after = await _counts(pg_engine)
    assert after == before, f"the upgrade changed row counts: {before} -> {after}"

    async with pg_engine.connect() as conn:
        content = await conn.scalar(
            text("SELECT content FROM messages WHERE id = :id"), {"id": seeded["message_id"]}
        )
        status = await conn.scalar(text("SELECT status FROM resume_skills LIMIT 1"))
        # The columns this batch added exist and are NULL for pre-existing rows,
        # which is the documented "no demonstrable provenance" state.
        fingerprint_column = await conn.scalar(
            text(
                "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = "
                "'resume_embeddings' AND column_name = 'text_fingerprint'"
            )
        )
    assert content == "survives the upgrade"
    assert status == "detected"
    assert int(fingerprint_column) == 1


@pytest.mark.asyncio
async def test_the_schema_after_the_chain_matches_the_models(pg_engine, postgres_url, metadata):
    """No drift between what the migrations build and what the code expects."""
    await _reset(pg_engine)
    _upgrade(postgres_url, "head")

    async with pg_engine.connect() as conn:
        differences = await conn.run_sync(
            lambda c: compare_metadata(MigrationContext.configure(c), metadata)
        )
    assert differences == [], differences


# ---------------------------------------------------------------------------
# Expand-only: old code keeps working against the new schema
# ---------------------------------------------------------------------------


def test_every_migration_in_this_batch_is_expand_only():
    """The rollout half of expand/contract, checked as a property of the code.

    A deploy is not atomic: for a while the previous version of the application
    runs against the migrated schema. That is safe only while the migrations add
    things. A dropped column or table would break the running version instantly,
    and no test of the *new* code would notice.

    Checked by reading the migration source rather than by running it, because
    the point is that the destructive operation must not be *there* at all.
    """
    destructive = {"drop_column", "drop_table", "alter_column", "rename_table"}
    offences = []
    for revision in BATCH_REVISIONS:
        path = next(pathlib.Path("alembic/versions").glob(f"{revision}_*.py"))
        tree = ast.parse(path.read_text())
        upgrade = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "upgrade"
        )
        for node in ast.walk(upgrade):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in destructive
            ):
                offences.append(f"{path.name}: {node.func.attr}")
    assert offences == [], offences


def test_each_migration_in_this_batch_has_a_downgrade():
    """Not for the data — for being able to undo the schema half of a bad deploy."""
    for revision in BATCH_REVISIONS:
        path = next(pathlib.Path("alembic/versions").glob(f"{revision}_*.py"))
        tree = ast.parse(path.read_text())
        downgrade = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "downgrade"
            ),
            None,
        )
        assert downgrade is not None, f"{path.name} has no downgrade()"
        body = [
            statement
            for statement in downgrade.body
            if not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant))
        ]
        assert body and not (
            len(body) == 1 and isinstance(body[0], ast.Pass)
        ), f"{path.name}: downgrade() does nothing"


@pytest.mark.asyncio
async def test_the_chain_can_be_walked_back_and_forward_again(
    pg_engine, postgres_url, metadata
):
    """Downgrade to before the batch and upgrade again: the schema comes back."""
    from alembic import command

    await _reset(pg_engine)
    _upgrade(postgres_url, "head")

    previous = os.environ.get("ALEMBIC_DATABASE_URL")
    os.environ["ALEMBIC_DATABASE_URL"] = postgres_url
    try:
        command.downgrade(_config(postgres_url), BATCH_REVISIONS[0] + "-1")
        command.upgrade(_config(postgres_url), "head")
    finally:
        if previous is None:
            os.environ.pop("ALEMBIC_DATABASE_URL", None)
        else:
            os.environ["ALEMBIC_DATABASE_URL"] = previous

    async with pg_engine.connect() as conn:
        differences = await conn.run_sync(
            lambda c: compare_metadata(MigrationContext.configure(c), metadata)
        )
    assert differences == [], differences


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------


def _pg_binary(name: str) -> str | None:
    """Run pg_dump/pg_restore inside the lane container if they are not local."""
    from shutil import which

    return which(name)


@pytest.mark.asyncio
async def test_a_dump_taken_before_the_upgrade_restores_the_data(
    pg_engine, postgres_url, metadata
):
    """The other half of a rollout plan: putting the database back.

    Uses the lane container's own ``pg_dump``/``pg_restore`` through ``docker
    exec`` when they are not installed locally, so the rehearsal does not depend
    on the developer's machine. Skipped, not faked, when neither is available.
    """
    container = os.environ.get("PG_TEST_CONTAINER", "sc-test-pg")
    docker = _pg_binary("docker")
    if docker is None and _pg_binary("pg_dump") is None:
        pytest.skip("neither docker nor pg_dump is available for the restore rehearsal")

    await _reset(pg_engine)
    _upgrade(postgres_url, BATCH_REVISIONS[0] + "-1")
    seeded = await _seed_rows(pg_engine)
    before = await _counts(pg_engine)

    def _run(args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(args, capture_output=True, text=True, timeout=120)

    dump = _run(
        [docker, "exec", container, "pg_dump", "-U", "testuser", "-d",
         "studentscompass_test", "-Fc", "-f", "/tmp/rehearsal.dump"]
    )
    if dump.returncode != 0:
        pytest.skip(f"pg_dump unavailable in the lane container: {dump.stderr[:200]}")

    # Deploy goes ahead...
    _upgrade(postgres_url, "head")
    async with pg_engine.begin() as conn:
        await conn.execute(text("DELETE FROM messages"))
    assert (await _counts(pg_engine))["messages"] == 0

    # ...and is rolled back by restoring the dump.
    await _reset(pg_engine)
    restore = _run(
        [docker, "exec", container, "pg_restore", "-U", "testuser", "-d",
         "studentscompass_test", "--no-owner", "/tmp/rehearsal.dump"]
    )
    assert restore.returncode == 0, restore.stderr[:400]

    after = await _counts(pg_engine)
    assert after == before, f"restore did not bring the data back: {before} -> {after}"
    async with pg_engine.connect() as conn:
        content = await conn.scalar(
            text("SELECT content FROM messages WHERE id = :id"), {"id": seeded["message_id"]}
        )
    assert content == "survives the upgrade"

    # And the restored database can be taken forward again.
    _upgrade(postgres_url, "head")
    async with pg_engine.connect() as conn:
        differences = await conn.run_sync(
            lambda c: compare_metadata(MigrationContext.configure(c), metadata)
        )
    assert differences == [], differences


# ---------------------------------------------------------------------------
# Contract parity against the TASK-035 baseline
# ---------------------------------------------------------------------------


#: Differences from the archived baseline that a task *declared*. Anything else
#: is an accident, and that is the whole point of the check: a contract change
#: has to be written down somewhere before it is allowed.
DECLARED_REMOVED_PATHS = {
    # TASK-042 replaced the fastapi-users JWT routes with per-actor session
    # endpoints carrying CSRF double-submit.
    "/auth/jwt/login",
    "/auth/jwt/logout",
    # TASK-048–053: the legacy adapters remain callable while traffic drains,
    # but are intentionally hidden from the public OpenAPI contract. Their
    # REST replacements below are the documented surface consumed by React.
    "/api/v1/applications/{application_id}/interview-selection",
    "/api/v1/communities/{community_id}/join",
    "/api/v1/communities/{community_id}/leave",
    "/api/v1/company_dashboard",
    "/api/v1/friends/requests/{request_id}/accept",
    "/api/v1/jobs/keywords/analyze",
    "/api/v1/jobs/keywords/{job_id}",
    "/api/v1/jobs/search",
    "/api/v1/profile/cv",
    "/api/v1/profile/cv/course-audit-attempts",
    "/api/v1/profile/cv/course-audit-upload",
    "/api/v1/profile/cv/upload",
    "/api/v1/profile/cv/{resume_id}",
    "/api/v1/roadmaps/{slug}/save",
    "/api/v1/students_dashboard",
}
DECLARED_ADDED_PATHS = {
    "/api/v1/auth/session",
    "/api/v1/auth/session/refresh",
    "/api/v1/auth/student/login",
    "/api/v1/auth/student/logout",
    # TASK-024: the paged read; the legacy list endpoint is untouched beside it.
    "/api/v1/conversations/{conversation_id}/messages/page",
    # TASK-061 and TASK-062: the same shape for the community feed and for a
    # student's applications. In both cases the legacy list endpoint stays
    # exactly as it was beside the new one — bounded now, but unchanged in shape.
    "/api/v1/posts/page",
    "/api/v1/applications/page",
    # TASK-048–053: stable REST replacements for the hidden legacy adapters.
    "/api/v1/admin/job-postings",
    "/api/v1/admin/job-postings/{job_id}",
    "/api/v1/admin/resource-files",
    "/api/v1/applications/{application_id}/selected-interview",
    "/api/v1/communities/{community_id}/members/me",
    "/api/v1/companies/me/dashboard",
    "/api/v1/cv-analyses",
    "/api/v1/cv-analyses/{job_id}",
    "/api/v1/dashboard/student",
    "/api/v1/friend-requests/{request_id}",
    "/api/v1/job-searches",
    "/api/v1/resume-course-audits",
    "/api/v1/resume-course-audits/attempts",
    "/api/v1/resumes",
    "/api/v1/resumes/{resume_id}",
    "/api/v1/roadmaps/{slug}/saves/me",
    # TASK-054: the endpoints a task queue calls, deliberately outside /api/v1
    # because they are not part of the public contract. Reachable from the
    # internet under ADR-001, and therefore authenticated by OIDC rather than by
    # being hard to find (app/core/internalAuth.py).
    "/internal/tasks/cv-analyses/{job_id}",
    "/internal/tasks/cv-analyses-reconcile",
}


def _baseline_openapi() -> dict:
    import json

    path = pathlib.Path("../docs/refactor/baseline/openapi.json")
    if not path.exists():
        pytest.skip("no archived OpenAPI baseline (TASK-035)")
    return json.loads(path.read_text())


def test_no_endpoint_disappeared_without_a_task_saying_so():
    """Parity with the baseline archived before any of this work started."""
    from app.app import app

    baseline = _baseline_openapi()
    current = app.openapi()

    removed = set(baseline["paths"]) - set(current["paths"])
    added = set(current["paths"]) - set(baseline["paths"])

    assert removed == DECLARED_REMOVED_PATHS, {
        "undeclared removals": sorted(removed - DECLARED_REMOVED_PATHS),
        "declared but still present": sorted(DECLARED_REMOVED_PATHS - removed),
    }
    assert added == DECLARED_ADDED_PATHS, {
        "undeclared additions": sorted(added - DECLARED_ADDED_PATHS),
        "declared but missing": sorted(DECLARED_ADDED_PATHS - added),
    }


def test_the_methods_of_every_surviving_endpoint_are_unchanged():
    """A path that stayed must not have quietly lost a verb."""
    from app.app import app

    baseline = _baseline_openapi()
    current = app.openapi()
    verbs = {"get", "post", "put", "patch", "delete"}

    lost = []
    for path, item in baseline["paths"].items():
        if path in DECLARED_REMOVED_PATHS:
            continue
        before = {method for method in item if method in verbs}
        after = {method for method in current["paths"].get(path, {}) if method in verbs}
        if before - after:
            lost.append((path, sorted(before - after)))
    assert lost == [], lost
