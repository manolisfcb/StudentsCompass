"""TASK-062 — the student's applications, walked with a stable cursor.

TASK-025 took the whole-history materialisation out of the *dashboard*. This is
the applications screen, which still read every application a user had ever
filed and eagerly loaded the company and every interview slot for each one — so
the cost per row was several rows' worth, and the user who paid it most was the
one who uses the product most.

Timestamps are seeded in groups on purpose: the cursor's tie-break on ``id`` is
what keeps the page boundary unambiguous, and it is only exercised by ties.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import MAX_COLLECTION_ROWS
from app.models.applicationModel import ApplicationModel, ApplicationStatus
from app.models.companyModel import Company
from app.models.userModel import User
from app.services.applications.applicationService import (
    ApplicationService,
    InvalidApplicationCursor,
)

TIMESTAMP_GROUP = 7


async def seed_applications(
    session: AsyncSession, *, user: User, company: Company, count: int
) -> None:
    base = datetime(2026, 1, 1, 9, 0, 0)
    session.add_all(
        ApplicationModel(
            id=uuid.uuid4(),
            user_id=user.id,
            company_id=company.id,
            job_title=f"Role {index}",
            status=ApplicationStatus.APPLIED,
            application_date=base,
            created_at=base + timedelta(seconds=index // TIMESTAMP_GROUP),
        )
        for index in range(count)
    )
    await session.commit()


async def canonical_order(session: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    result = await session.execute(
        select(ApplicationModel.id)
        .where(ApplicationModel.user_id == user_id)
        .order_by(ApplicationModel.created_at.desc(), ApplicationModel.id.desc())
    )
    return list(result.scalars().all())


class TestApplicationPage:
    @pytest.mark.parametrize("count", [0, 100, 10_000])
    @pytest.mark.asyncio
    async def test_the_history_is_walked_exactly_once(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_company: Company,
        count: int,
    ):
        """Nothing skipped, nothing repeated, at every size the ficha names."""
        await seed_applications(
            db_session, user=test_user, company=test_company, count=count
        )
        service = ApplicationService(db_session)

        seen: list[uuid.UUID] = []
        cursor = None
        while True:
            rows, cursor, has_more, _ = await service.list_user_application_page(
                user_id=test_user.id, before=cursor, limit=100
            )
            seen.extend(row.id for row in rows)
            if cursor is None:
                assert has_more is False
                break

        assert len(seen) == count
        assert len(set(seen)) == count
        assert seen == await canonical_order(db_session, test_user.id)

    @pytest.mark.asyncio
    async def test_another_students_applications_are_not_reachable(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_company: Company,
    ):
        """Ownership is in the query, so paging cannot walk out of it.

        A cursor is an opaque row address, and a stranger's cursor is a valid
        one — so the guarantee cannot come from the cursor. It comes from the
        ``WHERE user_id``, which no cursor can widen.
        """
        stranger = User(
            id=uuid.uuid4(),
            email="stranger@example.com",
            hashed_password="x",
            is_active=True,
            is_verified=True,
        )
        db_session.add(stranger)
        await db_session.commit()

        await seed_applications(
            db_session, user=stranger, company=test_company, count=30
        )
        await seed_applications(
            db_session, user=test_user, company=test_company, count=5
        )
        service = ApplicationService(db_session)

        stranger_rows, stranger_cursor, _, _ = await service.list_user_application_page(
            user_id=stranger.id, limit=2
        )
        assert stranger_cursor is not None

        # The stranger's own cursor, replayed by the other user.
        mine, _, _, _ = await service.list_user_application_page(
            user_id=test_user.id, before=stranger_cursor, limit=100
        )

        stranger_ids = {row.id for row in stranger_rows}
        assert stranger_ids.isdisjoint({row.id for row in mine})
        assert all(row.user_id == test_user.id for row in mine)

    @pytest.mark.parametrize("requested,expected", [(500, 100), (10_000, 100), (0, 1)])
    @pytest.mark.asyncio
    async def test_the_server_caps_the_page(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_company: Company,
        requested: int,
        expected: int,
    ):
        await seed_applications(
            db_session, user=test_user, company=test_company, count=300
        )
        service = ApplicationService(db_session)

        rows, _, _, page_size = await service.list_user_application_page(
            user_id=test_user.id, limit=requested
        )

        assert len(rows) == expected
        assert page_size == expected

    @pytest.mark.asyncio
    async def test_a_malformed_cursor_is_refused(self, db_session: AsyncSession, test_user: User):
        with pytest.raises(InvalidApplicationCursor):
            await ApplicationService(db_session).list_user_application_page(
                user_id=test_user.id, before="nonsense!"
            )

    @pytest.mark.asyncio
    async def test_the_page_still_carries_company_and_interview_slots(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_company: Company,
    ):
        """The bound must not cost the screen the data it renders.

        The eager loads are what made the unpaged read expensive; the fix was to
        run them per page, not to drop them.
        """
        await seed_applications(
            db_session, user=test_user, company=test_company, count=3
        )

        rows, _, _, _ = await ApplicationService(db_session).list_user_application_page(
            user_id=test_user.id, limit=10
        )

        assert rows
        for row in rows:
            assert row.company is not None
            assert row.interview_availabilities == []


class TestApplicationPageQueryBudget:
    @pytest.mark.asyncio
    async def test_a_page_costs_a_fixed_number_of_queries_at_any_history_size(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_company: Company,
        query_counter,
    ):
        """Fixed per page — the point of the bound.

        Three statements: the page itself plus one ``selectinload`` batch for
        each of the two relations. Constant in the size of the history, which
        is what the unpaged version was not.
        """
        await seed_applications(
            db_session, user=test_user, company=test_company, count=50
        )
        service = ApplicationService(db_session)

        with query_counter() as small:
            await service.list_user_application_page(user_id=test_user.id, limit=20)

        await seed_applications(
            db_session, user=test_user, company=test_company, count=5_000
        )

        with query_counter() as large:
            await service.list_user_application_page(user_id=test_user.id, limit=20)

        assert small.selects == large.selects == 3


class TestApplicationEndpoints:
    @pytest.mark.asyncio
    async def test_the_page_endpoint_returns_the_declared_envelope(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        test_company: Company,
    ):
        await seed_applications(
            db_session, user=test_user, company=test_company, count=50
        )

        response = await client.get("/api/v1/applications/page?limit=20", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"items", "next_cursor", "has_more", "limit"}
        assert len(body["items"]) == 20
        assert body["has_more"] is True
        assert body["next_cursor"]

    @pytest.mark.asyncio
    async def test_the_page_endpoint_refuses_a_malformed_cursor(
        self, client: AsyncClient, auth_headers: dict
    ):
        response = await client.get(
            "/api/v1/applications/page?before=nonsense!", headers=auth_headers
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_the_page_endpoint_needs_a_session(self, client: AsyncClient):
        response = await client.get("/api/v1/applications/page")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_the_legacy_list_is_bounded_and_keeps_its_shape(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        test_company: Company,
    ):
        await seed_applications(
            db_session,
            user=test_user,
            company=test_company,
            count=MAX_COLLECTION_ROWS + 40,
        )

        response = await client.get("/api/v1/applications", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == MAX_COLLECTION_ROWS

    @pytest.mark.asyncio
    async def test_the_legacy_list_keeps_the_newest_applications(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        test_company: Company,
    ):
        """Truncating at the oldest end: the current applications are the ones acted on."""
        await seed_applications(
            db_session,
            user=test_user,
            company=test_company,
            count=MAX_COLLECTION_ROWS + 40,
        )
        newest = (await canonical_order(db_session, test_user.id))[:MAX_COLLECTION_ROWS]

        response = await client.get("/api/v1/applications", headers=auth_headers)

        assert [uuid.UUID(item["id"]) for item in response.json()] == newest
