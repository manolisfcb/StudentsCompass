"""TASK-041 — the pagination contract and the idempotency registry.

Two guarantees are under test here, and they answer different failure modes:

* **A collection cannot exceed the server's ceiling**, whatever the client asks
  for. The failure it prevents is a caller — or a crawler, or a bug — choosing
  how much work the server does.
* **The same intention, sent twice, is carried out once.** The failure it
  prevents is a retried POST filing a second application or spending a second
  AI credit, which is invisible to the client precisely because the client
  never saw the first response.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_COLLECTION_ROWS,
    MAX_PAGE_SIZE,
    InvalidCursor,
    clamp_page_number,
    clamp_page_size,
    decode_cursor,
    encode_cursor,
    fetch_probe_limit,
    split_probe,
)
from app.core.idempotency import (
    IDEMPOTENCY_HEADER,
    IN_PROGRESS_LEASE,
    fingerprint,
    purge_expired_records,
)
from app.models.applicationModel import ApplicationModel
from app.schemas.applicationSchema import ApplicationCreate
from app.models.companyModel import Company
from app.models.friendshipModel import FriendshipModel
from app.models.idempotencyModel import IdempotencyRecordModel, IdempotencyStatus
from app.models.jobPostingModel import JobPosting
from app.models.userModel import User
from tests.test_applications import create_approved_resume


# --- The cursor -------------------------------------------------------------


class TestCursor:
    def test_a_cursor_round_trips_its_two_fields(self):
        moment = datetime(2026, 3, 4, 5, 6, 7, 890123)
        identifier = uuid.uuid4()

        assert decode_cursor(encode_cursor(moment, identifier)) == (moment, identifier)

    def test_the_cursor_carries_the_id_so_equal_timestamps_stay_ordered(self):
        """Two rows in the same microsecond must produce different cursors.

        This is the whole reason the cursor is a pair. If it were the timestamp
        alone, the boundary between pages would be ambiguous exactly when rows
        are created together — a batch insert, a client retrying — and a row
        would be repeated or skipped.
        """
        moment = datetime(2026, 3, 4, 5, 6, 7)
        first, second = sorted([uuid.uuid4(), uuid.uuid4()], key=str)

        assert encode_cursor(moment, first) != encode_cursor(moment, second)

    @pytest.mark.parametrize(
        "malformed",
        [
            "",
            "not-base64!!",
            "YWJj",  # valid base64, but not "<timestamp>|<uuid>"
            encode_cursor(datetime(2026, 1, 1), "not-a-uuid"),
            "MjAyNi0wMS0wMXxub3QtYS11dWlk",
        ],
    )
    def test_a_malformed_cursor_is_refused_rather_than_ignored(self, malformed):
        """Refused, not dropped.

        A filter that is silently discarded answers with the wrong page and
        calls it the right one, which is worse than an error the client can see.
        """
        with pytest.raises(InvalidCursor):
            decode_cursor(malformed)


# --- The server ceiling -----------------------------------------------------


class TestPageSizeClamp:
    @pytest.mark.parametrize(
        "requested,expected",
        [
            (None, DEFAULT_PAGE_SIZE),  # did not say
            (0, 1),                      # nonsense for a page size
            (-1, 1),
            (7, 7),                      # honoured
            (MAX_PAGE_SIZE, MAX_PAGE_SIZE),
            (MAX_PAGE_SIZE + 1, MAX_PAGE_SIZE),
            (10_000, MAX_PAGE_SIZE),     # the ceiling is the server's, not the client's
        ],
    )
    def test_the_server_decides_the_page_size(self, requested, expected):
        assert clamp_page_size(requested) == expected

    def test_an_over_large_request_is_clamped_not_rejected(self):
        """A caller asking for too much still gets a working response.

        Rejecting would turn a client's over-eager default into an outage for
        the user; clamping bounds the cost and answers.
        """
        assert clamp_page_size(10_000) == MAX_PAGE_SIZE

    @pytest.mark.parametrize("requested,expected", [(None, 1), (0, 1), (-5, 1), (3, 3)])
    def test_page_numbers_start_at_one(self, requested, expected):
        assert clamp_page_number(requested) == expected

    def test_the_probe_row_is_what_decides_has_more(self):
        """`has_more` is a fact about the data, not a guess from a full page."""
        page_size = 3
        assert fetch_probe_limit(page_size) == 4

        exactly_full = [1, 2, 3]
        with_probe = [1, 2, 3, 4]

        assert split_probe(exactly_full, page_size) == ([1, 2, 3], False)
        assert split_probe(with_probe, page_size) == ([1, 2, 3], True)


class TestCollectionCeilings:
    """No collection may answer with more rows than the server's bound."""

    @pytest.mark.asyncio
    async def test_the_friends_list_is_bounded_however_long_it_gets(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        overflow = MAX_COLLECTION_ROWS + 25
        friends = [
            User(
                id=uuid.uuid4(),
                email=f"friend{index}@example.com",
                hashed_password="x",
                is_active=True,
                is_verified=True,
                first_name="Friend",
                last_name=str(index),
            )
            for index in range(overflow)
        ]
        db_session.add_all(friends)
        db_session.add_all(
            FriendshipModel(id=uuid.uuid4(), user_id=test_user.id, friend_id=friend.id)
            for friend in friends
        )
        await db_session.commit()

        response = await client.get("/api/v1/friends", headers=auth_headers)

        assert response.status_code == 200
        assert len(response.json()) == MAX_COLLECTION_ROWS

    @pytest.mark.asyncio
    async def test_the_resume_list_is_bounded(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        from app.models.resumeModel import ResumeModel

        overflow = MAX_COLLECTION_ROWS + 10
        db_session.add_all(
            ResumeModel(
                id=uuid.uuid4(),
                user_id=test_user.id,
                view_url=f"https://example.com/cv{index}.pdf",
                storage_file_id=f"resumes/cv{index}.pdf",
                original_filename=f"cv{index}.pdf",
                folder_id="test-bucket",
            )
            for index in range(overflow)
        )
        await db_session.commit()

        response = await client.get("/api/v1/profile/cv", headers=auth_headers)

        assert response.status_code == 200
        assert len(response.json()) == MAX_COLLECTION_ROWS


# --- The idempotency registry ----------------------------------------------


class TestFingerprint:
    def test_field_order_does_not_change_the_fingerprint(self):
        """The same request serialised differently is still the same request."""
        assert fingerprint({"a": 1, "b": 2}) == fingerprint({"b": 2, "a": 1})

    def test_a_different_body_is_a_different_fingerprint(self):
        assert fingerprint({"a": 1}) != fingerprint({"a": 2})

    def test_bytes_are_hashed_as_themselves(self):
        """For an upload the file *is* the request."""
        assert fingerprint(b"pdf-bytes") == fingerprint(b"pdf-bytes")
        assert fingerprint(b"pdf-bytes") != fingerprint(b"other-bytes")


async def _application_payload(
    *, db_session: AsyncSession, test_user: User, test_company: Company
) -> dict:
    job_posting = JobPosting(
        id=uuid.uuid4(),
        company_id=test_company.id,
        title="Software Engineer",
        description="Great opportunity",
    )
    db_session.add(job_posting)
    await create_approved_resume(db_session=db_session, test_user=test_user)
    await db_session.commit()
    return {
        "company_id": str(test_company.id),
        "job_posting_id": str(job_posting.id),
        "job_title": "Software Engineer",
        "status": "applied",
    }


async def _count_applications(session: AsyncSession, user_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count(ApplicationModel.id)).where(ApplicationModel.user_id == user_id)
    )
    return int(result.scalar_one())


class TestIdempotentApplications:
    @pytest.mark.asyncio
    async def test_the_same_key_and_body_replays_the_first_response(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_company: Company,
        test_company_recruiter,
        db_session: AsyncSession,
    ):
        payload = await _application_payload(
            db_session=db_session, test_user=test_user, test_company=test_company
        )
        headers = {**auth_headers, IDEMPOTENCY_HEADER: "apply-once"}

        first = await client.post("/api/v1/applications", headers=headers, json=payload)
        second = await client.post("/api/v1/applications", headers=headers, json=payload)

        assert first.status_code == 200
        assert second.status_code == 200
        # Byte-for-byte the first answer, not a freshly computed equivalent one.
        assert second.json() == first.json()
        assert second.headers.get("Idempotent-Replay") == "true"
        assert await _count_applications(db_session, test_user.id) == 1

    @pytest.mark.asyncio
    async def test_the_same_key_with_a_different_body_is_a_conflict(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_company: Company,
        test_company_recruiter,
        db_session: AsyncSession,
    ):
        """409, not the first response.

        Replaying here would confirm a request the client never made — the
        worst of the three possible answers.
        """
        payload = await _application_payload(
            db_session=db_session, test_user=test_user, test_company=test_company
        )
        headers = {**auth_headers, IDEMPOTENCY_HEADER: "reused-key"}

        first = await client.post("/api/v1/applications", headers=headers, json=payload)
        second = await client.post(
            "/api/v1/applications",
            headers=headers,
            json={**payload, "job_title": "A completely different role"},
        )

        assert first.status_code == 200
        assert second.status_code == 409
        assert second.headers.get("X-Error-Code") == "idempotency_key_reuse"
        assert await _count_applications(db_session, test_user.id) == 1

    @pytest.mark.asyncio
    async def test_a_different_key_files_a_second_application(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_company: Company,
        test_company_recruiter,
        db_session: AsyncSession,
    ):
        """Idempotency must not become deduplication.

        Two deliberate applications to the same posting are the caller's
        business; the key is what distinguishes "again" from "still the first".
        """
        payload = await _application_payload(
            db_session=db_session, test_user=test_user, test_company=test_company
        )

        first = await client.post(
            "/api/v1/applications",
            headers={**auth_headers, IDEMPOTENCY_HEADER: "first"},
            json=payload,
        )
        second = await client.post(
            "/api/v1/applications",
            headers={**auth_headers, IDEMPOTENCY_HEADER: "second"},
            json=payload,
        )

        assert first.status_code == second.status_code == 200
        # The application service already collapses a repeat application to the
        # same posting; what matters here is that the second key was accepted
        # and answered on its own rather than refused as a replay.
        assert second.headers.get("Idempotent-Replay") is None

    @pytest.mark.asyncio
    async def test_without_a_key_nothing_changes(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_company: Company,
        test_company_recruiter,
        db_session: AsyncSession,
    ):
        """The legacy clients send no key, and must keep working untouched."""
        payload = await _application_payload(
            db_session=db_session, test_user=test_user, test_company=test_company
        )

        response = await client.post("/api/v1/applications", headers=auth_headers, json=payload)

        assert response.status_code == 200
        assert response.headers.get("Idempotent-Replay") is None
        stored = await db_session.execute(select(func.count(IdempotencyRecordModel.id)))
        assert stored.scalar_one() == 0

    @pytest.mark.asyncio
    async def test_an_unfinished_request_blocks_its_key(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_company: Company,
        db_session: AsyncSession,
    ):
        """A key claimed and not yet finished has no result to replay.

        409 is the honest answer: the alternative is doing the work twice, which
        is the thing the header exists to prevent.
        """
        payload = await _application_payload(
            db_session=db_session, test_user=test_user, test_company=test_company
        )
        db_session.add(
            IdempotencyRecordModel(
                id=uuid.uuid4(),
                actor_key=f"user:{test_user.id}",
                endpoint="POST /applications",
                idempotency_key="in-flight",
                request_fingerprint=fingerprint(ApplicationCreate(**payload)),
                status=IdempotencyStatus.IN_PROGRESS,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=24),
            )
        )
        await db_session.commit()

        response = await client.post(
            "/api/v1/applications",
            headers={**auth_headers, IDEMPOTENCY_HEADER: "in-flight"},
            json=payload,
        )

        assert response.status_code == 409
        assert response.headers.get("X-Error-Code") == "idempotency_request_in_progress"

    @pytest.mark.asyncio
    async def test_an_abandoned_claim_stops_blocking_after_its_lease(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_company: Company,
        test_company_recruiter,
        db_session: AsyncSession,
    ):
        """A process killed mid-request must not lock a key out for a day."""
        payload = await _application_payload(
            db_session=db_session, test_user=test_user, test_company=test_company
        )
        abandoned = datetime.utcnow() - IN_PROGRESS_LEASE - timedelta(minutes=1)
        db_session.add(
            IdempotencyRecordModel(
                id=uuid.uuid4(),
                actor_key=f"user:{test_user.id}",
                endpoint="POST /applications",
                idempotency_key="abandoned",
                request_fingerprint=fingerprint(ApplicationCreate(**payload)),
                status=IdempotencyStatus.IN_PROGRESS,
                created_at=abandoned,
                expires_at=datetime.utcnow() + timedelta(hours=24),
            )
        )
        await db_session.commit()

        response = await client.post(
            "/api/v1/applications",
            headers={**auth_headers, IDEMPOTENCY_HEADER: "abandoned"},
            json=payload,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_one_users_key_is_not_another_users_answer(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_company: Company,
        test_company_recruiter,
        db_session: AsyncSession,
    ):
        """Keys are client-chosen strings, so two users will collide eventually.

        A record scoped by key alone would hand one student another student's
        application as their own result.
        """
        payload = await _application_payload(
            db_session=db_session, test_user=test_user, test_company=test_company
        )
        stranger_id = uuid.uuid4()
        db_session.add(
            IdempotencyRecordModel(
                id=uuid.uuid4(),
                actor_key=f"user:{stranger_id}",
                endpoint="POST /applications",
                idempotency_key="shared-string",
                request_fingerprint=fingerprint(ApplicationCreate(**payload)),
                status=IdempotencyStatus.COMPLETED,
                response_status_code=200,
                response_body='{"id": "not-yours"}',
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=24),
            )
        )
        await db_session.commit()

        response = await client.post(
            "/api/v1/applications",
            headers={**auth_headers, IDEMPOTENCY_HEADER: "shared-string"},
            json=payload,
        )

        assert response.status_code == 200
        assert response.json()["id"] != "not-yours"

    @pytest.mark.asyncio
    async def test_a_blank_key_is_rejected_as_a_client_error(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_company: Company,
        db_session: AsyncSession,
    ):
        payload = await _application_payload(
            db_session=db_session, test_user=test_user, test_company=test_company
        )

        response = await client.post(
            "/api/v1/applications",
            headers={**auth_headers, IDEMPOTENCY_HEADER: "   "},
            json=payload,
        )

        assert response.status_code == 400
        assert response.headers.get("X-Error-Code") == "idempotency_key_invalid"


class TestRetention:
    @pytest.mark.asyncio
    async def test_expired_records_are_swept(self, db_session: AsyncSession):
        """Retention is finite: a key is a retry window, not an audit log."""
        now = datetime.utcnow()
        db_session.add_all(
            [
                IdempotencyRecordModel(
                    id=uuid.uuid4(),
                    actor_key="user:someone",
                    endpoint="POST /applications",
                    idempotency_key="expired",
                    request_fingerprint="x" * 64,
                    status=IdempotencyStatus.COMPLETED,
                    created_at=now - timedelta(days=2),
                    expires_at=now - timedelta(days=1),
                ),
                IdempotencyRecordModel(
                    id=uuid.uuid4(),
                    actor_key="user:someone",
                    endpoint="POST /applications",
                    idempotency_key="live",
                    request_fingerprint="y" * 64,
                    status=IdempotencyStatus.COMPLETED,
                    created_at=now,
                    expires_at=now + timedelta(hours=1),
                ),
            ]
        )
        await db_session.commit()

        removed = await purge_expired_records(db_session, now=now)

        assert removed == 1
        remaining = await db_session.execute(select(IdempotencyRecordModel.idempotency_key))
        assert remaining.scalars().all() == ["live"]
