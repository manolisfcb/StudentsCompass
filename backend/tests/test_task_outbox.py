"""TASK-054 — the dispatch survives the process that created it.

Three things are being fixed at once, and they fail differently:

* a **loop in the web replica** does not run when the replica is scaled to
  zero, and runs N times when there are N replicas;
* an **enqueue outside the transaction** loses work in one direction or invents
  it in the other, depending on which side of the commit it sits;
* an **unauthenticated internal endpoint** lets anyone spend the AI budget.

The job's own state machine — claim, lease, terminal statuses — is TASK-013's
and is deliberately untouched. What is under test here is who pulls the
trigger, and what happens when the trigger is pulled twice.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import internalAuth
from app.core.internalAuth import (
    SHARED_SECRET_HEADER,
    InternalTaskAuthError,
    verify_google_oidc,
)
from app.models.jobAnalysisModel import JobAnalysisModel, JobStatus
from app.models.resumeModel import ResumeModel
from app.models.taskOutboxModel import TASK_CV_ANALYSIS, OutboxStatus, TaskOutboxModel
from app.models.userModel import User
from app.services.tasks import outbox
from app.services.tasks.transports import (
    CloudTasksTransport,
    DisabledTransport,
    HttpTransport,
    TransportNotConfigured,
    task_path,
)


async def make_job(
    session: AsyncSession, *, user: User, status: JobStatus = JobStatus.PENDING
) -> JobAnalysisModel:
    resume = ResumeModel(
        id=uuid.uuid4(),
        user_id=user.id,
        view_url="https://example.com/cv.pdf",
        storage_file_id="resumes/cv.pdf",
        original_filename="cv.pdf",
        folder_id="test-bucket",
    )
    job = JobAnalysisModel(
        id=uuid.uuid4(),
        user_id=user.id,
        resume_id=resume.id,
        status=status,
        attempts=0,
    )
    session.add_all([resume, job])
    await session.commit()
    return job


class TestOutboxWrite:
    @pytest.mark.asyncio
    async def test_the_dispatch_is_written_without_committing(
        self, db_session: AsyncSession, test_user: User
    ):
        """The row must land in the caller's transaction, not in its own.

        Committing here would put the dispatch on one side of a boundary and
        the job on the other, which is exactly the failure the outbox exists to
        remove. So the assertion is that the transaction is still open and
        unfinished when the function returns.

        That the *rollback* then discards the row is a claim about savepoints,
        and pysqlite does not implement them faithfully — it is asserted on the
        PostgreSQL lane (``tests/integration/test_task_outbox_pg.py``), which is
        where it is true.
        """
        job_id = uuid.uuid4()
        committed: list[bool] = []
        original_commit = type(db_session).commit

        async def spy(self, *args, **kwargs):
            committed.append(True)
            return await original_commit(self, *args, **kwargs)

        type(db_session).commit = spy
        try:
            written = await outbox.enqueue_cv_analysis(db_session, job_id=job_id)
        finally:
            type(db_session).commit = original_commit

        assert written is True
        assert committed == [], "enqueue must leave the commit to its caller"
        assert db_session.in_transaction() is True

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_a_second_enqueue_for_one_job_writes_one_row(
        self, db_session: AsyncSession
    ):
        """A retried request joining an existing job must not queue it twice."""
        job_id = uuid.uuid4()

        first = await outbox.enqueue_cv_analysis(db_session, job_id=job_id)
        second = await outbox.enqueue_cv_analysis(db_session, job_id=job_id)
        await db_session.commit()

        assert first is True
        assert second is False
        total = await db_session.execute(select(func.count(TaskOutboxModel.id)))
        assert total.scalar_one() == 1

    @pytest.mark.asyncio
    async def test_a_duplicate_does_not_poison_the_caller_s_transaction(
        self, db_session: AsyncSession
    ):
        """The savepoint is the point: the request still has a response to build."""
        job_id = uuid.uuid4()
        await outbox.enqueue_cv_analysis(db_session, job_id=job_id)
        await db_session.commit()

        await outbox.enqueue_cv_analysis(db_session, job_id=job_id)

        # The session is still usable after the refused insert.
        usable = await db_session.execute(select(func.count(TaskOutboxModel.id)))
        assert usable.scalar_one() == 1

    @pytest.mark.asyncio
    async def test_creating_an_analysis_writes_its_dispatch(
        self, db_session: AsyncSession, test_user: User
    ):
        from app.services.ai.cvAnalysisService import CVAnalysisService

        resume = ResumeModel(
            id=uuid.uuid4(),
            user_id=test_user.id,
            view_url="https://example.com/cv.pdf",
            storage_file_id="resumes/cv.pdf",
            original_filename="cv.pdf",
            folder_id="test-bucket",
        )
        db_session.add(resume)
        await db_session.commit()

        job = await CVAnalysisService(db_session).create_pending_analysis(
            user_id=test_user.id, resume_id=resume.id
        )

        row = await db_session.execute(
            select(TaskOutboxModel).where(
                TaskOutboxModel.dedupe_key == outbox.cv_analysis_dedupe_key(job.id)
            )
        )
        written = row.scalar_one()
        assert written.task_type == TASK_CV_ANALYSIS
        assert written.status == OutboxStatus.PENDING
        assert written.payload["job_id"] == str(job.id)


class TestOutboxDelivery:
    @pytest.mark.asyncio
    async def test_a_delivered_row_is_not_delivered_again(self, db_session: AsyncSession):
        await outbox.enqueue_cv_analysis(db_session, job_id=uuid.uuid4())
        await db_session.commit()

        delivered: list[TaskOutboxModel] = []

        class Recording:
            async def deliver(self, row):
                delivered.append(row)

        first = await outbox.deliver_pending(db_session, Recording())
        second = await outbox.deliver_pending(db_session, Recording())

        assert first == 1
        assert second == 0
        assert len(delivered) == 1

    @pytest.mark.asyncio
    async def test_a_failed_delivery_backs_off_and_stays_pending(
        self, db_session: AsyncSession
    ):
        await outbox.enqueue_cv_analysis(db_session, job_id=uuid.uuid4())
        await db_session.commit()

        class Broken:
            async def deliver(self, row):
                raise RuntimeError("the queue said no")

        delivered = await outbox.deliver_pending(db_session, Broken())

        assert delivered == 0
        row = (await db_session.execute(select(TaskOutboxModel))).scalar_one()
        assert row.status == OutboxStatus.PENDING
        assert row.attempts == 1
        assert row.available_at > datetime.utcnow()
        assert "the queue said no" in row.last_error

    @pytest.mark.asyncio
    async def test_a_delivery_that_never_works_gives_up_visibly(
        self, db_session: AsyncSession
    ):
        """FAILED, and kept. A dispatch that never happened is what to look at."""
        from app.config import TASK_OUTBOX_MAX_ATTEMPTS

        await outbox.enqueue_cv_analysis(db_session, job_id=uuid.uuid4())
        await db_session.commit()

        class Broken:
            async def deliver(self, row):
                raise RuntimeError("still no")

        for _ in range(TASK_OUTBOX_MAX_ATTEMPTS):
            row = (await db_session.execute(select(TaskOutboxModel))).scalar_one()
            row.available_at = datetime.utcnow() - timedelta(seconds=1)
            await db_session.commit()
            await outbox.deliver_pending(db_session, Broken())

        row = (await db_session.execute(select(TaskOutboxModel))).scalar_one()
        assert row.status == OutboxStatus.FAILED
        assert row.attempts == TASK_OUTBOX_MAX_ATTEMPTS

    @pytest.mark.asyncio
    async def test_a_row_that_is_not_due_yet_is_left_alone(self, db_session: AsyncSession):
        await outbox.enqueue_cv_analysis(db_session, job_id=uuid.uuid4())
        await db_session.commit()
        row = (await db_session.execute(select(TaskOutboxModel))).scalar_one()
        row.available_at = datetime.utcnow() + timedelta(minutes=5)
        await db_session.commit()

        class Recording:
            async def deliver(self, row):
                raise AssertionError("must not be delivered yet")

        assert await outbox.deliver_pending(db_session, Recording()) == 0

    @pytest.mark.asyncio
    async def test_requeue_makes_a_dispatched_row_due_again(self, db_session: AsyncSession):
        job_id = uuid.uuid4()
        await outbox.enqueue_cv_analysis(db_session, job_id=job_id)
        await db_session.commit()
        row = (await db_session.execute(select(TaskOutboxModel))).scalar_one()
        row.status = OutboxStatus.DISPATCHED
        await db_session.commit()

        await outbox.requeue_for_job(db_session, job_id=job_id)
        await db_session.commit()

        row = (await db_session.execute(select(TaskOutboxModel))).scalar_one()
        assert row.status == OutboxStatus.PENDING

    @pytest.mark.asyncio
    async def test_requeue_writes_a_row_for_a_job_that_never_had_one(
        self, db_session: AsyncSession
    ):
        """A job queued before this table existed still has to be recoverable."""
        job_id = uuid.uuid4()

        await outbox.requeue_for_job(db_session, job_id=job_id)
        await db_session.commit()

        row = (await db_session.execute(select(TaskOutboxModel))).scalar_one()
        assert row.payload["job_id"] == str(job_id)


class TestTransports:
    def test_the_default_transport_refuses_instead_of_guessing(self):
        row = TaskOutboxModel(
            id=uuid.uuid4(), task_type=TASK_CV_ANALYSIS, payload={"job_id": str(uuid.uuid4())},
            dedupe_key="x", status=OutboxStatus.PENDING,
        )
        with pytest.raises(TransportNotConfigured):
            import asyncio

            asyncio.get_event_loop().run_until_complete(DisabledTransport().deliver(row))

    def test_the_task_url_is_derived_from_the_payload(self):
        job_id = uuid.uuid4()
        row = TaskOutboxModel(
            id=uuid.uuid4(), task_type=TASK_CV_ANALYSIS, payload={"job_id": str(job_id)},
            dedupe_key="x", status=OutboxStatus.PENDING,
        )

        assert task_path(row) == f"/internal/tasks/cv-analyses/{job_id}"

    def test_an_unknown_task_type_has_no_route(self):
        row = TaskOutboxModel(
            id=uuid.uuid4(), task_type="something_else", payload={"job_id": "x"},
            dedupe_key="x", status=OutboxStatus.PENDING,
        )
        with pytest.raises(TransportNotConfigured):
            task_path(row)

    def test_the_http_transport_needs_a_destination(self):
        with pytest.raises(TransportNotConfigured):
            HttpTransport("", "secret")

    def test_cloud_tasks_names_the_settings_it_is_missing(self):
        with pytest.raises(TransportNotConfigured) as raised:
            CloudTasksTransport(
                queue="", base_url="", service_account_email="", audience=""
            )

        message = str(raised.value)
        assert "CLOUD_TASKS_QUEUE" in message
        assert "INTERNAL_TASKS_BASE_URL" in message

    @pytest.mark.asyncio
    async def test_the_cloud_task_id_comes_from_the_dedupe_key(self):
        """A random task id would let a retry create a second task."""
        from app.services.tasks.transports import _task_id

        job_id = uuid.uuid4()
        row = TaskOutboxModel(
            id=uuid.uuid4(),
            task_type=TASK_CV_ANALYSIS,
            payload={"job_id": str(job_id)},
            dedupe_key=outbox.cv_analysis_dedupe_key(job_id),
            status=OutboxStatus.PENDING,
        )

        assert _task_id(row) == f"cv_analysis-{job_id}"
        assert ":" not in _task_id(row)


class TestInternalEndpointAuth:
    @pytest.mark.asyncio
    async def test_no_credential_is_rejected(self, client: AsyncClient):
        response = await client.post(f"/internal/tasks/cv-analyses/{uuid.uuid4()}")

        assert response.status_code == 401
        assert response.headers.get("X-Error-Code") == "internal_task_unauthorized"

    @pytest.mark.asyncio
    async def test_a_bearer_token_that_does_not_verify_is_rejected(
        self, client: AsyncClient
    ):
        response = await client.post(
            f"/internal/tasks/cv-analyses/{uuid.uuid4()}",
            headers={"Authorization": "Bearer not-a-real-token"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_the_reconcile_endpoint_is_protected_too(self, client: AsyncClient):
        response = await client.post("/internal/tasks/cv-analyses-reconcile")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_a_wrong_shared_secret_is_rejected(
        self, client: AsyncClient, monkeypatch
    ):
        monkeypatch.setattr(internalAuth, "INTERNAL_TASKS_SHARED_SECRET", "the-real-one")
        monkeypatch.setattr(internalAuth, "IS_PRODUCTION", False)

        response = await client.post(
            f"/internal/tasks/cv-analyses/{uuid.uuid4()}",
            headers={SHARED_SECRET_HEADER: "not-the-real-one"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_the_shared_secret_is_refused_in_production(
        self, client: AsyncClient, monkeypatch
    ):
        """A string in an env var is not an identity.

        It is enough for a laptop and not enough for a deployment, and the
        difference has to be enforced rather than documented.
        """
        monkeypatch.setattr(internalAuth, "INTERNAL_TASKS_SHARED_SECRET", "the-real-one")
        monkeypatch.setattr(internalAuth, "IS_PRODUCTION", True)

        response = await client.post(
            f"/internal/tasks/cv-analyses/{uuid.uuid4()}",
            headers={SHARED_SECRET_HEADER: "the-real-one"},
        )

        assert response.status_code == 401


class TestOidcClaims:
    """The checks applied to a token *after* its signature verifies."""

    def _claims(self, **overrides):
        base = {
            "iss": "https://accounts.google.com",
            "aud": "https://api.example.com",
            "email": "tasks@project.iam.gserviceaccount.com",
            "email_verified": True,
        }
        base.update(overrides)
        return base

    def _verify(self, monkeypatch, claims, *, audience="https://api.example.com",
                email="tasks@project.iam.gserviceaccount.com"):
        monkeypatch.setattr(internalAuth, "INTERNAL_TASKS_AUDIENCE", audience)
        monkeypatch.setattr(internalAuth, "CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL", email)
        return verify_google_oidc("token", verifier=lambda raw, aud: claims)

    def test_a_well_formed_token_is_accepted(self, monkeypatch):
        assert self._verify(monkeypatch, self._claims())["email_verified"] is True

    def test_a_token_minted_for_another_service_is_rejected(self, monkeypatch):
        """The audience is what stops a token being replayed here."""
        with pytest.raises(InternalTaskAuthError):
            self._verify(monkeypatch, self._claims(aud="https://other.example.com"))

    def test_a_token_from_another_identity_is_rejected(self, monkeypatch):
        with pytest.raises(InternalTaskAuthError):
            self._verify(monkeypatch, self._claims(email="someone@example.com"))

    def test_an_unverified_email_is_rejected(self, monkeypatch):
        with pytest.raises(InternalTaskAuthError):
            self._verify(monkeypatch, self._claims(email_verified=False))

    def test_an_unexpected_issuer_is_rejected(self, monkeypatch):
        with pytest.raises(InternalTaskAuthError):
            self._verify(monkeypatch, self._claims(iss="https://evil.example.com"))

    def test_a_signature_failure_is_an_auth_error(self, monkeypatch):
        monkeypatch.setattr(internalAuth, "INTERNAL_TASKS_AUDIENCE", "https://api.example.com")

        def failing(raw, aud):
            raise ValueError("bad signature")

        with pytest.raises(InternalTaskAuthError):
            verify_google_oidc("token", verifier=failing)

    def test_an_unconfigured_audience_refuses_everything(self, monkeypatch):
        """Not configured is not the same as not required."""
        monkeypatch.setattr(internalAuth, "INTERNAL_TASKS_AUDIENCE", "")

        with pytest.raises(InternalTaskAuthError):
            verify_google_oidc("token", verifier=lambda raw, aud: self._claims())


class TestInternalEndpointBehaviour:
    @pytest.fixture(autouse=True)
    def _allow_shared_secret(self, monkeypatch):
        monkeypatch.setattr(internalAuth, "INTERNAL_TASKS_SHARED_SECRET", "test-secret")
        monkeypatch.setattr(internalAuth, "IS_PRODUCTION", False)

    @property
    def headers(self) -> dict:
        return {SHARED_SECRET_HEADER: "test-secret"}

    @pytest.mark.asyncio
    async def test_a_task_for_a_finished_job_succeeds_without_running_anything(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """The replay case: the queue redelivers, and nothing is spent again."""
        job = await make_job(db_session, user=test_user, status=JobStatus.COMPLETED)

        response = await client.post(
            f"/internal/tasks/cv-analyses/{job.id}", headers=self.headers
        )

        assert response.status_code == 200
        assert response.json() == {
            "job_id": str(job.id),
            "status": "completed",
            "ran": False,
        }

    @pytest.mark.asyncio
    async def test_a_task_for_a_failed_job_is_also_terminal(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        job = await make_job(db_session, user=test_user, status=JobStatus.FAILED)

        response = await client.post(
            f"/internal/tasks/cv-analyses/{job.id}", headers=self.headers
        )

        assert response.status_code == 200
        assert response.json()["ran"] is False

    @pytest.mark.asyncio
    async def test_a_task_for_an_unknown_job_succeeds_rather_than_retrying_forever(
        self, client: AsyncClient
    ):
        """404 would make the queue retry a job that will never exist."""
        response = await client.post(
            f"/internal/tasks/cv-analyses/{uuid.uuid4()}", headers=self.headers
        )

        assert response.status_code == 200
        assert response.json()["status"] == "unknown"


class TestWebReplicaHasNoPollingLoop:
    def test_the_lifespan_does_not_start_the_runner_by_default(self):
        """§6.3: no AI polling loop inside a web replica.

        Asserted against the module's flag rather than by booting the app,
        because the failure this guards against is someone re-adding the call.
        """
        import inspect

        from app import app as app_module

        source = inspect.getsource(app_module.lifespan)
        assert "start_runner()" in source
        assert "if CV_ANALYSIS_INLINE_RUNNER:" in source
        assert app_module.CV_ANALYSIS_INLINE_RUNNER is False
