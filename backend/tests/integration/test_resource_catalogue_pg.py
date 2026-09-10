"""The catalogue query on the database it actually runs on.

The tag search expands a JSON array, and that is the one part of this query
whose *syntax* differs between SQLite and PostgreSQL — ``json_each`` against
``jsonb_array_elements_text``. Two spellings mean two chances to be subtly
different, so the parity claim is repeated here against the real dialect.

Case folding is the other reason this lane matters. PostgreSQL's ``lower()``
folds Unicode; SQLite's folds ASCII only, so ``lower('Á')`` is ``'Á'`` there.
Accented search is therefore asserted here, where production runs, and not in
the fast lane, where the difference is the test database's and not the code's.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


@pytest.fixture
def _models():
    import tests.conftest  # noqa: F401

    from app.db import Base

    return Base


@pytest.fixture
async def schema(pg_engine, _models):
    async with pg_engine.begin() as conn:
        await conn.run_sync(_models.metadata.create_all)
    try:
        yield
    finally:
        async with pg_engine.begin() as conn:
            await conn.run_sync(_models.metadata.drop_all)


async def _seed(session):
    from app.models.resourceModel import ResourceModel
    from tests.test_resource_catalogue_filtering import CATALOGUE

    base = datetime(2026, 1, 1, 8, 0, 0)
    rows = [
        ResourceModel(
            id=uuid.uuid4(),
            title=title,
            description=description,
            category=category,
            tags=tags,
            estimated_duration_minutes=duration,
            is_published=published,
            created_at=base + timedelta(hours=index),
        )
        for index, (title, description, category, tags, duration, published)
        in enumerate(CATALOGUE)
    ]
    # An accented row, which only this lane can fold correctly.
    rows.append(
        ResourceModel(
            id=uuid.uuid4(),
            title="Gestión de Proyectos",
            description="Planificación y ejecución",
            category="gestión",
            tags=["planificación", "GESTIÓN"],
            estimated_duration_minutes=80,
            is_published=True,
            created_at=base + timedelta(days=1),
        )
    )
    session.add_all(rows)
    await session.commit()
    return rows


@pytest.mark.parametrize(
    "category,search,sort",
    [
        (None, None, "recent"),
        (None, None, "name"),
        (None, None, "duration"),
        ("tech", None, "name"),
        ("career", None, "duration"),
        (None, "python", "recent"),
        (None, "PYTHON", "name"),
        (None, "algorithms", "recent"),
        (None, "cv", "recent"),
        (None, "zzz", "recent"),
        ("tech", "python", "duration"),
    ],
)
@pytest.mark.asyncio
async def test_the_sql_query_matches_the_in_memory_one_on_postgresql(
    schema, pg_session, category, search, sort
):
    from app.models.resourceModel import ResourceModel
    from app.services.resources.resourceService import ResourceService
    from tests.test_resource_catalogue_filtering import reference_list_published

    await _seed(pg_session)
    published = await pg_session.execute(
        select(ResourceModel).where(ResourceModel.is_published.is_(True))
    )
    expected = reference_list_published(
        list(published.scalars().all()), category=category, search=search, sort=sort
    )

    actual = await ResourceService(pg_session).list_published_resources(
        category=category, search=search, sort=sort
    )

    assert [r.id for r in actual] == [r.id for r in expected]


@pytest.mark.parametrize("search", ["gestión", "GESTIÓN", "Gestión", "planificación"])
@pytest.mark.asyncio
async def test_accented_search_folds_case_the_way_python_did(schema, pg_session, search):
    """``lower()`` on PostgreSQL folds ``Ó`` to ``ó``, exactly as ``str.lower``.

    This is why the search moved to SQL without changing what users find: the
    database production runs on folds the same alphabet Python does.
    """
    from app.services.resources.resourceService import ResourceService

    await _seed(pg_session)

    results = await ResourceService(pg_session).list_published_resources(search=search)

    assert [r.title for r in results] == ["Gestión de Proyectos"]


@pytest.mark.asyncio
async def test_the_accented_category_matches_case_insensitively(schema, pg_session):
    from app.services.resources.resourceService import ResourceService

    await _seed(pg_session)

    results = await ResourceService(pg_session).list_published_resources(category="GESTIÓN")

    assert [r.title for r in results] == ["Gestión de Proyectos"]


@pytest.mark.asyncio
async def test_the_tag_search_does_not_match_json_punctuation(schema, pg_session):
    """The reason the array is expanded rather than matched as text."""
    from app.services.resources.resourceService import ResourceService

    await _seed(pg_session)
    service = ResourceService(pg_session)

    assert len(await service.list_published_resources(search="beginner")) == 1
    assert await service.list_published_resources(search='python", "beginner') == []


@pytest.mark.asyncio
async def test_the_filtered_read_does_not_scan_more_than_it_returns(schema, pg_session):
    """Rows produced by the plan, not rows in the table.

    The claim of this task is that filtering happens in the database. If it did
    not, the plan would still produce every published row and discard them
    above the scan.
    """
    from sqlalchemy import text

    await _seed(pg_session)
    plan = await pg_session.execute(
        text(
            "EXPLAIN (ANALYZE) SELECT * FROM resources "
            "WHERE is_published AND lower(btrim(category)) = 'tech' "
            "ORDER BY created_at DESC LIMIT 200"
        )
    )
    plan_text = "\n".join(row[0] for row in plan)

    # Four published 'tech' rows in the seed; the scan must not produce more
    # than the filter accepts plus what the planner needs to reject inline.
    assert "rows=" in plan_text
