"""TASK-063 — the catalogue filtered by the database, not by Python.

``list_published_resources`` used to run ``SELECT * FROM resources WHERE
is_published`` and then filter, search and sort in three Python passes: eleven
results cost loading the whole catalogue.

Every test here is a **parity** test. The reference implementation below is the
in-memory code as it was, kept verbatim, and the SQL version is required to
agree with it — because the risk in this change is not that the query fails, it
is that it quietly answers something slightly different.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resourceModel import ResourceModel
from app.services.resources.resourceService import ResourceService


def reference_list_published(
    resources: list[ResourceModel],
    category: str | None = None,
    search: str | None = None,
    sort: str = "recent",
) -> list[ResourceModel]:
    """The previous in-memory implementation, unchanged, as the oracle."""
    if category and category.lower() != "all":
        cat = category.strip().lower()
        resources = [r for r in resources if (r.category or "").strip().lower() == cat]

    if search:
        q = search.strip().lower()
        if q:
            def _matches(resource: ResourceModel) -> bool:
                haystack = [resource.title or "", resource.description or ""]
                tags = resource.tags or []
                haystack.extend(tags)
                return any(q in str(v).lower() for v in haystack)

            resources = [r for r in resources if _matches(r)]

    if sort == "name":
        resources.sort(key=lambda r: (r.title or "").lower())
    elif sort == "duration":
        resources.sort(key=lambda r: (r.estimated_duration_minutes or 10**9, (r.title or "").lower()))
    else:
        resources.sort(key=lambda r: r.created_at, reverse=True)

    return ResourceService.prioritize_mandatory_resources(resources)


CATALOGUE = [
    # (title, description, category, tags, duration, published)
    ("LinkedIn Optimization", "Polish your profile", "career", ["linkedin", "profile"], 30, True),
    ("Interview Preparation", "Practice answers", "career", ["interview"], 45, True),
    ("Resume Templates", "Ready to use", "career", ["resume", "cv"], None, True),
    ("Python Basics", "Learn Python from scratch", "tech", ["python", "beginner"], 120, True),
    ("Advanced Python", "Decorators and more", "tech", ["python", "advanced"], 90, True),
    ("Data Structures", "Lists, trees, graphs", "tech", ["algorithms"], 200, True),
    ("Public Speaking", "Talk to a room", "soft-skills", ["speaking", "confidence"], 60, True),
    ("Networking", "Meet people", "Soft-Skills", ["networking"], 25, True),
    ("Negotiation", "Ask for more", " soft-skills ", ["salary", "negotiation"], None, True),
    ("Unpublished Draft", "Not ready", "tech", ["python"], 10, False),
    ("Excel Fundamentals", "Spreadsheets", "tech", ["excel", "data"], 75, True),
]


async def seed_catalogue(session: AsyncSession) -> list[ResourceModel]:
    base = datetime(2026, 1, 1, 8, 0, 0)
    rows = []
    for index, (title, description, category, tags, duration, published) in enumerate(CATALOGUE):
        rows.append(
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
        )
    session.add_all(rows)
    await session.commit()
    return [row for row in rows if row.is_published]


async def published_rows(session: AsyncSession) -> list[ResourceModel]:
    """Freshly loaded published rows, so the oracle sorts its own list."""
    result = await session.execute(
        select(ResourceModel).where(ResourceModel.is_published.is_(True))
    )
    return list(result.scalars().all())


class TestParity:
    @pytest.mark.parametrize(
        "category,search,sort",
        [
            (None, None, "recent"),
            (None, None, "name"),
            (None, None, "duration"),
            ("all", None, "recent"),
            ("tech", None, "recent"),
            ("tech", None, "name"),
            ("career", None, "duration"),
            ("soft-skills", None, "name"),
            ("Soft-Skills", None, "name"),      # the caller's casing
            ("  tech  ", None, "recent"),        # the caller's whitespace
            ("nonexistent", None, "recent"),
            (None, "python", "recent"),
            (None, "PYTHON", "recent"),          # case-insensitive
            (None, "  python  ", "name"),        # trimmed
            (None, "scratch", "recent"),         # description only
            (None, "algorithms", "recent"),      # tag only
            (None, "cv", "recent"),              # tag only, short
            (None, "e", "name"),                 # matches many
            (None, "zzz", "recent"),             # matches none
            (None, "", "recent"),                # empty search is no search
            ("tech", "python", "name"),
            ("tech", "python", "duration"),
            ("career", "resume", "recent"),
        ],
    )
    @pytest.mark.asyncio
    async def test_the_sql_query_answers_what_python_answered(
        self, db_session: AsyncSession, category, search, sort
    ):
        await seed_catalogue(db_session)
        service = ResourceService(db_session)

        expected = reference_list_published(
            await published_rows(db_session), category=category, search=search, sort=sort
        )
        actual = await service.list_published_resources(
            category=category, search=search, sort=sort
        )

        assert [r.id for r in actual] == [r.id for r in expected]

    @pytest.mark.asyncio
    async def test_unpublished_resources_stay_out(self, db_session: AsyncSession):
        await seed_catalogue(db_session)

        results = await ResourceService(db_session).list_published_resources()

        assert all(resource.is_published for resource in results)
        assert "Unpublished Draft" not in {resource.title for resource in results}

    @pytest.mark.asyncio
    async def test_the_mandatory_courses_still_come_first_in_their_fixed_order(
        self, db_session: AsyncSession
    ):
        """A product rule, and it survived the move to SQL untouched."""
        await seed_catalogue(db_session)

        results = await ResourceService(db_session).list_published_resources(sort="name")

        assert [r.title for r in results[:3]] == list(
            ResourceService.MANDATORY_RESOURCE_TITLES
        )


class TestSearchIsNotAPattern:
    @pytest.mark.asyncio
    async def test_a_percent_sign_searches_for_a_percent_sign(self, db_session: AsyncSession):
        """Unescaped, ``%`` in a LIKE matches everything.

        The in-memory version used ``in``, which has no wildcards, so a caller
        typing ``100%`` was searching for the characters ``100%``. Moving to
        LIKE without escaping would silently turn user input into a pattern.
        """
        db_session.add_all(
            [
                ResourceModel(
                    id=uuid.uuid4(),
                    title="Growth 100% guide",
                    description="d",
                    category="tech",
                    is_published=True,
                    created_at=datetime(2026, 1, 1),
                ),
                ResourceModel(
                    id=uuid.uuid4(),
                    title="Unrelated",
                    description="d",
                    category="tech",
                    is_published=True,
                    created_at=datetime(2026, 1, 2),
                ),
            ]
        )
        await db_session.commit()

        results = await ResourceService(db_session).list_published_resources(search="100%")

        assert [r.title for r in results] == ["Growth 100% guide"]

    @pytest.mark.asyncio
    async def test_an_underscore_is_a_literal_underscore(self, db_session: AsyncSession):
        db_session.add_all(
            [
                ResourceModel(
                    id=uuid.uuid4(),
                    title="snake_case naming",
                    description="d",
                    category="tech",
                    is_published=True,
                    created_at=datetime(2026, 1, 1),
                ),
                ResourceModel(
                    id=uuid.uuid4(),
                    title="snakeXcase naming",
                    description="d",
                    category="tech",
                    is_published=True,
                    created_at=datetime(2026, 1, 2),
                ),
            ]
        )
        await db_session.commit()

        results = await ResourceService(db_session).list_published_resources(search="snake_case")

        assert [r.title for r in results] == ["snake_case naming"]

    @pytest.mark.asyncio
    async def test_a_tag_search_does_not_match_across_two_tags(self, db_session: AsyncSession):
        """Why the tags predicate expands the array instead of matching its text.

        ``CAST(tags AS TEXT) LIKE '%a","b%'`` would match ``["a", "b"]`` — a hit
        on the JSON punctuation between two elements, which no tag contains.
        """
        db_session.add(
            ResourceModel(
                id=uuid.uuid4(),
                title="Two tags",
                description="d",
                category="tech",
                tags=["alpha", "beta"],
                is_published=True,
                created_at=datetime(2026, 1, 1),
            )
        )
        await db_session.commit()
        service = ResourceService(db_session)

        assert len(await service.list_published_resources(search="alpha")) == 1
        assert await service.list_published_resources(search='alpha", "beta') == []
        assert await service.list_published_resources(search='a", "b') == []


class TestRowsLoaded:
    @pytest.mark.asyncio
    async def test_rows_loaded_equals_rows_returned(self, db_session: AsyncSession):
        """The whole point of the change.

        Before, a filtered read loaded the entire published catalogue and threw
        most of it away in Python. The assertion is on the ORM identity map:
        after a filtered query only the matching rows have been materialised.
        """
        await seed_catalogue(db_session)
        db_session.expunge_all()

        results = await ResourceService(db_session).list_published_resources(
            category="tech", search="python"
        )

        loaded = [
            obj for obj in db_session.identity_map.all_states()
            if obj.class_ is ResourceModel
        ]
        assert len(results) == 2
        assert len(loaded) == len(results)

    @pytest.mark.asyncio
    async def test_the_catalogue_read_is_bounded(self, db_session: AsyncSession):
        from app.core.pagination import MAX_COLLECTION_ROWS

        db_session.add_all(
            ResourceModel(
                id=uuid.uuid4(),
                title=f"Course {index}",
                description="d",
                category="tech",
                is_published=True,
                created_at=datetime(2026, 1, 1) + timedelta(minutes=index),
            )
            for index in range(MAX_COLLECTION_ROWS + 50)
        )
        await db_session.commit()

        results = await ResourceService(db_session).list_published_resources()

        assert len(results) == MAX_COLLECTION_ROWS
