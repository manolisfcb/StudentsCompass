"""TASK-011 — public errors are mapped, not echoed, and a failed request does
not leave a poisoned session behind.

The routes used to answer with ``str(e)``. A storage or driver exception carries
the DSN, the SQL and the bound parameters, so the body described the machine.
The marker below stands in for whatever a real exception would carry.
"""
from __future__ import annotations

import io
import logging
import uuid

import pytest
import sqlalchemy as sa
from httpx import AsyncClient

from app.core.errors import (
    CODE_ADMIN_RESOURCE_INVALID,
    CODE_ADMIN_RESOURCE_UPLOAD,
    CODE_QUESTIONNAIRE_PROFILE,
    CODE_RESOURCE_FILE,
    CODE_RESOURCE_STORAGE_UNCONFIGURED,
    CODE_RESUME_UPLOAD,
    client_failure,
    is_safe_client_message,
    redact,
    server_failure,
)
from app.app import app
from app.models.userModel import User

SECRET = "sup3r-s3cret-marker"
# What a real driver failure looks like: credentials, SQL and a path.
SENSITIVE_EXCEPTION_TEXT = (
    f"(psycopg2.OperationalError) connection to postgresql://app:{SECRET}@10.0.0.4:5432/prod "
    f'failed [SQL: SELECT users.hashed_password FROM users WHERE users.email = $1] '
    f"password={SECRET} file=/srv/app/secrets/service_account.json"
)


def _body_and_headers(response):
    return response.text, response.headers


def assert_no_secret(response, caplog=None):
    body = response.text
    assert SECRET not in body
    assert "psycopg2" not in body
    assert "SELECT" not in body
    assert "/srv/app/secrets" not in body
    assert "10.0.0.4" not in body
    reference = response.headers.get("X-Error-Id")
    assert reference and reference in body, "the caller needs the correlation id"
    if caplog is not None:
        logged = caplog.text
        assert reference in logged, "the log must be joinable to the response"
        assert SECRET not in logged, "the cause is logged redacted"
    return reference


class TestRedaction:
    def test_credentials_are_masked_wherever_they_are_shaped_like_credentials(self):
        masked = redact(SENSITIVE_EXCEPTION_TEXT)

        assert SECRET not in masked
        assert "postgresql://app:***@10.0.0.4:5432/prod" in masked
        assert "password=***" in masked
        # Non-credential context survives, otherwise the log is useless.
        assert "psycopg2.OperationalError" in masked

    @pytest.mark.parametrize(
        "text,leaked",
        [
            ("Authorization: Bearer abc.def.ghi", "abc.def.ghi"),
            ("proxied with Bearer abc.def.ghi", "abc.def.ghi"),
            ("api_key='live_1234567890'", "live_1234567890"),
            ("AKIAIOSFODNN7EXAMPLE used", "AKIAIOSFODNN7EXAMPLE"),
            ("db_password: hunter2", "hunter2"),
        ],
    )
    def test_common_credential_shapes(self, text, leaked):
        masked = redact(text)

        assert leaked not in masked
        assert "***" in masked

    @pytest.mark.parametrize(
        "message",
        [
            "Video lessons require a valid video URL.",
            "Link lessons require a valid resource URL.",
            "Title is required",
        ],
    )
    def test_author_written_validation_messages_are_still_shown(self, message):
        assert is_safe_client_message(message)

    @pytest.mark.parametrize(
        "message",
        [
            SENSITIVE_EXCEPTION_TEXT,
            "[SQL: INSERT INTO resources (id, title) VALUES ($1, $2)]",
            "/var/data/storage/key.pdf not found",
            "TimeoutError: provider did not answer",
            "x" * 250,
        ],
    )
    def test_machinery_never_reaches_the_caller(self, message):
        assert not is_safe_client_message(message)


class TestTransactionalRecovery:
    @pytest.mark.asyncio
    async def test_session_is_usable_again_after_a_failed_statement(self, db_session, caplog):
        """A failed flush leaves the session raising PendingRollbackError on any
        later use. The handler has to hand it back clean."""
        user = User(
            id=uuid.uuid4(),
            email=f"dup-{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="x",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(
            User(
                id=uuid.uuid4(),
                email=user.email,  # unique violation
                hashed_password="x",
                is_active=True,
                is_superuser=False,
                is_verified=True,
            )
        )
        with pytest.raises(Exception) as failure:
            await db_session.flush()

        with pytest.raises(Exception):
            # Precondition: the session is poisoned until someone rolls back.
            await db_session.execute(sa.select(User).limit(1))

        error = await server_failure(failure.value, logger=logging.getLogger(__name__), session=db_session)

        assert error.status_code == 500
        assert (await db_session.execute(sa.select(User).limit(1))) is not None

    @pytest.mark.asyncio
    async def test_client_failure_also_releases_the_transaction(self, db_session):
        error = await client_failure(
            ValueError("Title is required"), logger=logging.getLogger(__name__), session=db_session
        )

        assert error.status_code == 400
        assert error.detail.startswith("Title is required (ref: ")
        assert (await db_session.execute(sa.select(User).limit(1))) is not None


class TestRoutesDoNotEchoExceptions:
    @pytest.mark.asyncio
    async def test_questionnaire_profile(self, client: AsyncClient, auth_headers, monkeypatch, caplog):
        caplog.set_level(logging.ERROR)

        async def boom(self, user):
            raise RuntimeError(SENSITIVE_EXCEPTION_TEXT)

        monkeypatch.setattr(
            "app.services.accounts.questionnaireService.QuestionnaireService.get_user_questionnaire_profile",
            boom,
        )

        response = await client.get("/api/v1/questionnaire/profile", headers=auth_headers)

        assert response.status_code == 500
        assert response.headers["X-Error-Code"] == CODE_QUESTIONNAIRE_PROFILE
        assert_no_secret(response, caplog)

    @pytest.mark.asyncio
    async def test_resource_file_failure(self, client: AsyncClient, auth_headers, monkeypatch, caplog):
        caplog.set_level(logging.ERROR)

        async def boom(self, key):
            raise RuntimeError(SENSITIVE_EXCEPTION_TEXT)

        monkeypatch.setattr(
            "app.services.resources.resourceService.ResourceService.download_resource_file", boom
        )

        response = await client.get(
            "/api/v1/resources/file", params={"key": "resources/x.pdf"}, headers=auth_headers
        )

        assert response.status_code == 500
        assert response.headers["X-Error-Code"] == CODE_RESOURCE_FILE
        assert_no_secret(response, caplog)

    @pytest.mark.asyncio
    async def test_unconfigured_resource_storage_is_not_a_bad_request(
        self, client: AsyncClient, auth_headers, monkeypatch, caplog
    ):
        caplog.set_level(logging.ERROR)

        async def boom(self, key):
            raise ValueError("Resource storage is not configured.")

        monkeypatch.setattr(
            "app.services.resources.resourceService.ResourceService.download_resource_file", boom
        )

        response = await client.get(
            "/api/v1/resources/file", params={"key": "resources/x.pdf"}, headers=auth_headers
        )

        # Was 400 with the internal reason quoted back at the caller.
        assert response.status_code == 503
        assert response.headers["X-Error-Code"] == CODE_RESOURCE_STORAGE_UNCONFIGURED
        assert "not configured" not in response.text

    @pytest.mark.asyncio
    async def test_resume_upload_failure(
        self, client: AsyncClient, auth_headers, monkeypatch, caplog
    ):
        caplog.set_level(logging.ERROR)
        monkeypatch.setenv("BUCKET_NAME", "test-resume-bucket")

        async def boom(self, **kwargs):
            raise RuntimeError(SENSITIVE_EXCEPTION_TEXT)

        monkeypatch.setattr(
            "app.services.resumes.resumeService.ResumeService.create_resume_from_upload", boom
        )

        response = await client.post(
            "/api/v1/profile/cv/upload",
            headers=auth_headers,
            files={"cv": ("resume.pdf", io.BytesIO(b"%PDF-1.4 fake pdf content"), "application/pdf")},
        )

        assert response.status_code == 500
        assert response.headers["X-Error-Code"] == CODE_RESUME_UPLOAD
        assert_no_secret(response, caplog)

    @pytest.mark.asyncio
    async def test_valid_upload_still_works(self, client: AsyncClient, auth_headers, monkeypatch):
        """Contract check: the redaction work did not change the success path."""

        class FakeStorage:
            async def upload_file(
                self,
                file_bytes,
                file_name,
                content_type="application/octet-stream",
                folder="resumes",
                owner_id=None,
            ):
                return {
                    "file_key": "resumes/stored_resume.pdf",
                    "file_url": "https://storage.example/resumes/stored_resume.pdf",
                    "bucket": "test-resume-bucket",
                }

        monkeypatch.setenv("BUCKET_NAME", "test-resume-bucket")
        monkeypatch.setattr(
            "app.services.resumes.resumeService.get_storage_service", lambda: FakeStorage()
        )

        response = await client.post(
            "/api/v1/profile/cv/upload",
            headers=auth_headers,
            files={"cv": ("resume.pdf", io.BytesIO(b"%PDF-1.4 fake pdf content"), "application/pdf")},
        )

        assert response.status_code == 200
        assert response.json()["file_url"].endswith("stored_resume.pdf")


class _StubAdminService:
    """Stands in for AdminService so the mapping is exercised, not the DB."""

    def __init__(self, error: Exception):
        self.error = error
        self.session = None

    async def create_resource(self, payload):
        raise self.error

    async def update_resource(self, resource_id, payload):
        raise self.error

    async def upload_resource_file(self, **kwargs):
        raise self.error


RESOURCE_PAYLOAD = {
    "title": "A course",
    "description": "Description",
    "category": "career",
    "modules": [],
}


class TestAdminErrorMapping:
    @pytest.fixture(autouse=True)
    def _override_admin_deps(self, client, test_user):
        from app.routes import adminRoute

        test_user.is_superuser = True
        app.dependency_overrides[adminRoute.current_admin_user] = lambda: test_user
        app.dependency_overrides[adminRoute.require_same_origin_for_write] = lambda: None
        yield
        app.dependency_overrides.pop(adminRoute.current_admin_user, None)
        app.dependency_overrides.pop(adminRoute.require_same_origin_for_write, None)
        app.dependency_overrides.pop(adminRoute._get_service, None)

    def _use(self, error: Exception):
        from app.routes import adminRoute

        app.dependency_overrides[adminRoute._get_service] = lambda: _StubAdminService(error)

    @pytest.mark.asyncio
    async def test_validation_message_is_preserved(self, client: AsyncClient):
        self._use(ValueError("Video lessons require a valid video URL."))

        response = await client.post("/api/v1/admin/resources", json=RESOURCE_PAYLOAD)

        assert response.status_code == 400
        assert "Video lessons require a valid video URL." in response.json()["detail"]
        assert response.headers["X-Error-Code"] == CODE_ADMIN_RESOURCE_INVALID

    @pytest.mark.asyncio
    async def test_a_value_error_from_the_machinery_is_not_a_validation_message(
        self, client: AsyncClient, caplog
    ):
        caplog.set_level(logging.ERROR)
        self._use(ValueError(SENSITIVE_EXCEPTION_TEXT))

        response = await client.post("/api/v1/admin/resources", json=RESOURCE_PAYLOAD)

        assert response.status_code == 400  # 4xx preserved
        assert_no_secret(response, caplog)

    @pytest.mark.asyncio
    async def test_unexpected_failure_is_a_generic_500(self, client: AsyncClient, caplog):
        caplog.set_level(logging.ERROR)
        self._use(RuntimeError(SENSITIVE_EXCEPTION_TEXT))

        response = await client.put(
            f"/api/v1/admin/resources/{uuid.uuid4()}", json=RESOURCE_PAYLOAD
        )

        assert response.status_code == 500
        assert_no_secret(response, caplog)

    @pytest.mark.asyncio
    async def test_upload_failure_is_generic(self, client: AsyncClient, caplog):
        caplog.set_level(logging.ERROR)
        self._use(RuntimeError(SENSITIVE_EXCEPTION_TEXT))

        response = await client.post(
            "/api/v1/admin/resources/upload-file",
            files={"file": ("guide.pdf", io.BytesIO(b"content"), "application/pdf")},
        )

        assert response.status_code == 500
        assert response.headers["X-Error-Code"] == CODE_ADMIN_RESOURCE_UPLOAD
        assert_no_secret(response, caplog)
