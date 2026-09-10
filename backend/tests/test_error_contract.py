"""TASK-040 — every ``/api/v1`` failure answers with one shape, and only there.

What this pins is the *shape*, not the policy: which operations fail and with
which status is TASK-011's and TASK-032's business and is explicitly out of this
task's Scope. So the assertions below are about keys, codes and correlation —
never about a route starting or stopping to fail.

The three things that used to differ per raise site, and now must not:

* the body is ``{"error": {"code", "message", "details", "request_id"}}``;
* ``code`` comes from the catalogue, so a client can branch without reading prose;
* ``request_id`` is the id of *this* request, so the log line and the body join.
"""
from __future__ import annotations

import logging

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.app import app
from app.core.error_handlers import ERROR_CODE_HEADER, install_error_handlers
from app.core.errors import (
    AppError,
    ErrorCode,
    code_for_status,
    error_envelope,
    server_failure,
)
from app.middleware.request_context import REQUEST_ID_HEADER, RequestContextMiddleware

ENVELOPE_KEYS = {"code", "message", "details", "request_id"}

# Text a driver failure would carry. If any of this reaches a client the whole
# point of the task is lost, so it is asserted against in every direction.
SECRET = "pa55w0rd-marker"
SENSITIVE = (
    f"(psycopg2.OperationalError) connection to postgresql://app:{SECRET}@10.0.0.4:5432/prod "
    "failed [SQL: SELECT * FROM users] /srv/app/secrets/key.pem"
)


def assert_envelope(body: dict) -> dict:
    """The body is the one shape, plus the legacy key TASK-059 retires."""
    assert set(body) <= {"error", "detail"}, body
    assert "error" in body, body
    error = body["error"]
    assert set(error) == ENVELOPE_KEYS, error
    assert isinstance(error["code"], str) and error["code"]
    assert isinstance(error["message"], str) and error["message"]
    assert isinstance(error["request_id"], str) and error["request_id"]
    return error


# --------------------------------------------------------------------------
# A dedicated app: the statuses below have to be produced on demand, and doing
# that through real routes would mean depending on their business rules.
# --------------------------------------------------------------------------

FAMILY_STATUSES = [400, 401, 403, 404, 409, 413, 422, 429, 503]


@pytest.fixture(scope="module")
def probe_app():
    from fastapi import FastAPI

    probe = FastAPI()
    probe.add_middleware(RequestContextMiddleware)
    install_error_handlers(probe)

    @probe.get("/api/v1/boom/{status_code}")
    async def _boom(status_code: int):
        raise HTTPException(status_code=status_code, detail="A plain sentence.")

    @probe.get("/api/v1/unhandled")
    async def _unhandled():
        raise RuntimeError(SENSITIVE)

    @probe.get("/api/v1/leaky")
    async def _leaky():
        # A raise site that puts driver text straight into ``detail``.
        raise HTTPException(status_code=400, detail=SENSITIVE)

    @probe.get("/api/v1/structured")
    async def _structured():
        raise AppError(
            ErrorCode.CONFLICT,
            "That slot is already taken.",
            status_code=409,
            details={"field": "slot_id"},
        )

    @probe.get("/api/v1/validated")
    async def _validated(count: int):  # noqa: ARG001 - the coercion is the test
        return {"ok": True}

    @probe.get("/legacy/page")
    async def _legacy():
        raise HTTPException(status_code=404, detail="No such page.")

    return probe


@pytest.fixture
async def probe(probe_app):
    async with AsyncClient(
        transport=ASGITransport(app=probe_app, raise_app_exceptions=False),
        base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.parametrize("status_code", FAMILY_STATUSES)
async def test_every_status_family_uses_the_one_shape(probe, status_code):
    response = await probe.get(f"/api/v1/boom/{status_code}")
    assert response.status_code == status_code
    error = assert_envelope(response.json())
    assert error["code"] == str(code_for_status(status_code))


async def test_unhandled_exception_is_a_500_envelope_without_the_cause(probe, caplog):
    with caplog.at_level(logging.ERROR):
        response = await probe.get("/api/v1/unhandled")
    assert response.status_code == 500
    error = assert_envelope(response.json())
    assert error["code"] == str(ErrorCode.INTERNAL)

    body = response.text
    assert SECRET not in body
    assert "psycopg2" not in body
    assert "SELECT" not in body
    assert "/srv/app" not in body

    # The cause survives in the log, under this request's id, with the
    # credential redacted.
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert error["request_id"] in logged
    assert "OperationalError" in logged
    assert SECRET not in logged


async def test_detail_that_smells_of_machinery_is_replaced(probe):
    response = await probe.get("/api/v1/leaky")
    assert response.status_code == 400
    error = assert_envelope(response.json())
    assert SECRET not in response.text
    assert "psycopg2" not in error["message"]


async def test_safe_detail_is_preserved(probe):
    response = await probe.get("/api/v1/boom/404")
    assert assert_envelope(response.json())["message"] == "A plain sentence."


async def test_app_error_carries_its_code_and_details(probe):
    response = await probe.get("/api/v1/structured")
    assert response.status_code == 409
    error = assert_envelope(response.json())
    assert error["code"] == str(ErrorCode.CONFLICT)
    assert error["details"] == {"field": "slot_id"}
    assert error["message"] == "That slot is already taken."


async def test_validation_error_puts_the_field_in_details(probe):
    response = await probe.get("/api/v1/validated", params={"count": "not-a-number"})
    assert response.status_code == 422
    error = assert_envelope(response.json())
    assert error["code"] == str(ErrorCode.VALIDATION_FAILED)
    assert isinstance(error["details"], list) and error["details"]
    entry = error["details"][0]
    assert set(entry) == {"loc", "type", "msg"}
    assert "count" in entry["loc"]


async def test_details_is_null_when_there_is_nothing_structured(probe):
    assert assert_envelope((await probe.get("/api/v1/boom/403")).json())["details"] is None


async def test_request_id_is_echoed_and_can_be_supplied_by_the_caller(probe):
    supplied = "client-chosen-id-42"
    response = await probe.get(
        "/api/v1/boom/404", headers={REQUEST_ID_HEADER: supplied}
    )
    error = assert_envelope(response.json())
    assert error["request_id"] == supplied
    assert response.headers[REQUEST_ID_HEADER] == supplied


async def test_code_is_also_a_header_for_clients_that_cannot_read_the_body(probe):
    response = await probe.get("/api/v1/boom/409")
    assert response.headers[ERROR_CODE_HEADER] == str(ErrorCode.CONFLICT)


async def test_routes_outside_the_api_prefix_are_untouched(probe):
    """The Jinja views must keep the framework's shape, not gain an envelope."""
    response = await probe.get("/legacy/page")
    assert response.status_code == 404
    assert response.json() == {"detail": "No such page."}


async def test_unknown_api_route_is_still_an_envelope(probe):
    error = assert_envelope((await probe.get("/api/v1/nope")).json())
    assert error["code"] == str(ErrorCode.NOT_FOUND)


# --------------------------------------------------------------------------
# The TASK-011 helpers keep their precise codes through the new handler.
# --------------------------------------------------------------------------


async def test_helper_code_survives_the_central_handler(probe_app):
    from app.core.errors import CODE_JOB_SEARCH

    @probe_app.get("/api/v1/helper")
    async def _helper():
        raise await server_failure(
            RuntimeError(SENSITIVE),
            logger=logging.getLogger("test"),
            code=CODE_JOB_SEARCH,
            message="Job search is unavailable.",
        )

    async with AsyncClient(
        transport=ASGITransport(app=probe_app, raise_app_exceptions=False),
        base_url="http://test"
    ) as ac:
        response = await ac.get("/api/v1/helper")

    assert response.status_code == 500
    error = assert_envelope(response.json())
    assert error["code"] == str(CODE_JOB_SEARCH)
    assert SECRET not in response.text


# --------------------------------------------------------------------------
# Unit level: the envelope builder and the catalogue.
# --------------------------------------------------------------------------


def test_envelope_builder_is_the_only_spelling_of_the_keys():
    body = error_envelope(ErrorCode.NOT_FOUND, "Gone.", request_id="abc")
    assert body == {
        "error": {
            "code": "not_found",
            "message": "Gone.",
            "details": None,
            "request_id": "abc",
        }
    }


def test_catalogue_codes_are_unique_and_snake_case():
    values = [member.value for member in ErrorCode]
    assert len(values) == len(set(values))
    assert all(value.islower() and " " not in value for value in values)


def test_unknown_status_falls_back_by_family():
    assert code_for_status(418) == ErrorCode.INVALID_INPUT
    assert code_for_status(502) == ErrorCode.INTERNAL


async def test_real_app_registers_the_handlers():
    """The probe app proves the handlers work; this proves they are installed."""
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test"
    ) as ac:
        response = await ac.get("/api/v1/definitely-not-a-route")
    assert response.status_code == 404
    assert_envelope(response.json())


async def test_legacy_detail_is_kept_for_the_jinja_screens(probe):
    """Retired by TASK-059, and only then: the templates still read it.

    Asserted rather than merely allowed, so removing the adapter is a decision
    someone makes on purpose instead of a break someone discovers in the UI.
    """
    body = (await probe.get("/api/v1/boom/404")).json()
    assert_envelope(body)
    # Verbatim: a bare raise site never carried a reference, and appending one
    # would put a correlation id in a sentence the user reads on screen.
    assert body["detail"] == "A plain sentence."


async def test_legacy_detail_never_carries_the_cause_either(probe):
    body = (await probe.get("/api/v1/unhandled")).json()
    assert SECRET not in body["detail"]
    assert "psycopg2" not in body["detail"]


async def test_a_code_outside_the_catalogue_never_reaches_the_client(probe_app, caplog):
    """An invented code degrades to the family code instead of becoming public."""

    @probe_app.get("/api/v1/typo")
    async def _typo():
        raise HTTPException(
            status_code=403,
            detail="Nope.",
            headers={ERROR_CODE_HEADER: "frobidden"},
        )

    async with AsyncClient(
        transport=ASGITransport(app=probe_app, raise_app_exceptions=False),
        base_url="http://test",
    ) as ac:
        with caplog.at_level(logging.WARNING):
            response = await ac.get("/api/v1/typo")

    assert assert_envelope(response.json())["code"] == str(ErrorCode.FORBIDDEN)
    assert "frobidden" in caplog.text
