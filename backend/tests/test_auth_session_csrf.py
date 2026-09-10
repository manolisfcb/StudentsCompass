"""TASK-042 - the session contract and the CSRF barrier in front of it.

Two things are proven here. That a client can ask who it is instead of inferring
it from a 401 on some unrelated endpoint, and that a cookie alone is no longer
enough to change anything: the request must also echo back a token only a
same-origin page can read.

Tests about the barrier itself take ``raw_client``, which sends exactly what
they tell it to. The ordinary ``client`` supplies the token automatically, the
way a browser does, which is what makes it useless for proving what happens when
the token is absent, stale or someone else's.
"""
import pytest
from httpx import AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.middleware.csrf import CODE_CSRF
from app.models.companyRecruiterModel import CompanyRecruiter
from app.models.userModel import User
from app.services.accounts.userService import cookie_transport
from app.services.companies.companyService import cookie_transport_company

SESSION = "/api/v1/auth/session"
REFRESH = "/api/v1/auth/session/refresh"
STUDENT_LOGIN = "/api/v1/auth/student/login"
STUDENT_LOGOUT = "/api/v1/auth/student/logout"
COMPANY_LOGIN = "/api/v1/auth/company/login"
ME = "/api/v1/users/me"


async def _csrf_headers(client: AsyncClient) -> dict:
    """What a browser sends: the token from the cookie, in the header.

    ``raw_client`` does none of this for itself, so a test that wants a login to
    succeed has to do what the page would do - fetch a token, then use it.
    """
    token = client.cookies.get(CSRF_COOKIE_NAME)
    if not token:
        await client.get(SESSION)
        token = client.cookies.get(CSRF_COOKIE_NAME)
    return {CSRF_HEADER_NAME: token} if token else {}


async def login_student(client: AsyncClient, user: User, path: str = STUDENT_LOGIN):
    return await client.post(
        path,
        data={"username": user.email, "password": "password123"},
        headers=await _csrf_headers(client),
    )


async def login_recruiter(client: AsyncClient, recruiter: CompanyRecruiter):
    return await client.post(
        COMPANY_LOGIN,
        data={"username": recruiter.email, "password": "password123"},
        headers=await _csrf_headers(client),
    )


class TestSessionContract:
    """GET /auth/session - the client's first call."""

    @pytest.mark.asyncio
    async def test_anonymous_session_is_401(self, client: AsyncClient):
        assert (await client.get(SESSION)).status_code == 401

    @pytest.mark.asyncio
    async def test_anonymous_session_does_not_reveal_whether_an_account_exists(
        self, client: AsyncClient, test_user: User
    ):
        """The refusal must read the same however the caller probes it.

        Otherwise the endpoint is an account-enumeration oracle: someone learns
        who is registered by watching the answer change.
        """
        unknown = await client.get(SESSION, headers={"X-Probe": "nobody@example.com"})
        known = await client.get(SESSION, headers={"X-Probe": test_user.email})

        assert unknown.status_code == known.status_code == 401
        # Everything but the request id, which is per-request by design and
        # is the one field that must differ. The oracle would be a difference
        # in code, message or status.
        def _comparable(payload: dict) -> dict:
            body = {k: v for k, v in payload.items() if k != "detail"}
            body["error"] = {
                k: v for k, v in body["error"].items() if k != "request_id"
            }
            return body

        assert _comparable(unknown.json()) == _comparable(known.json())
        assert test_user.email not in unknown.text

    @pytest.mark.asyncio
    async def test_student_session_returns_the_actor_and_its_type(
        self, client: AsyncClient, test_user: User
    ):
        assert (await login_student(client, test_user)).status_code in (200, 204)

        response = await client.get(SESSION)

        assert response.status_code == 200
        body = response.json()
        assert body["actor"]["actor_type"] == "student"
        assert body["actor"]["id"] == str(test_user.id)
        assert body["actor"]["email"] == test_user.email
        assert body["csrf_token"]

    @pytest.mark.asyncio
    async def test_recruiter_session_carries_company_and_role(
        self, client: AsyncClient, test_company_recruiter: CompanyRecruiter
    ):
        assert (await login_recruiter(client, test_company_recruiter)).status_code in (200, 204)

        body = (await client.get(SESSION)).json()

        assert body["actor"]["actor_type"] == "recruiter"
        assert body["actor"]["company_id"] == str(test_company_recruiter.company_id)
        assert body["actor"]["role"] == test_company_recruiter.role

    @pytest.mark.asyncio
    async def test_session_never_exposes_the_password_hash(
        self, client: AsyncClient, test_user: User
    ):
        await login_student(client, test_user)

        assert "hashed_password" not in (await client.get(SESSION)).text

    @pytest.mark.asyncio
    async def test_both_identities_at_once_are_both_reported(
        self,
        client: AsyncClient,
        test_user: User,
        test_company_recruiter: CompanyRecruiter,
    ):
        """The two cookies coexist, so the contract has to say so.

        Reporting only one would make a client believe the other session had
        expired and offer a login the person does not need.
        """
        await login_student(client, test_user)
        await login_recruiter(client, test_company_recruiter)

        body = (await client.get(SESSION)).json()

        assert {actor["actor_type"] for actor in body["actors"]} == {"student", "recruiter"}
        assert body["actor"]["actor_type"] == "student"


class TestCSRFBarrier:
    """No token, no mutation - whatever the session cookie says."""

    @pytest.mark.asyncio
    async def test_a_mutation_without_a_token_is_refused(
        self, raw_client: AsyncClient, test_user: User
    ):
        await login_student(raw_client, test_user)
        raw_client.cookies.delete(CSRF_COOKIE_NAME)

        response = await raw_client.patch(ME, json={"first_name": "Mallory"})

        assert response.status_code == 403
        assert response.headers["X-Error-Code"] == CODE_CSRF

    @pytest.mark.asyncio
    async def test_a_mutation_with_someone_elses_token_is_refused(
        self, raw_client: AsyncClient, test_user: User
    ):
        """The two halves must be the same token, not merely both present.

        A token harvested elsewhere is the realistic version of this: perfectly
        well formed, just not this client's.
        """
        await login_student(raw_client, test_user)

        response = await raw_client.patch(
            ME,
            json={"first_name": "Mallory"},
            headers={CSRF_HEADER_NAME: "a-well-formed-token-from-somewhere-else"},
        )

        assert response.status_code == 403
        assert response.headers["X-Error-Code"] == CODE_CSRF

    @pytest.mark.asyncio
    async def test_a_matching_token_is_accepted(
        self, raw_client: AsyncClient, test_user: User
    ):
        await login_student(raw_client, test_user)
        token = raw_client.cookies.get(CSRF_COOKIE_NAME)
        assert token, "login must leave the client holding a token"

        response = await raw_client.patch(
            ME, json={"first_name": "Legitimate"}, headers={CSRF_HEADER_NAME: token}
        )

        assert response.status_code == 200
        assert response.json()["first_name"] == "Legitimate"

    @pytest.mark.asyncio
    async def test_a_foreign_origin_is_refused_even_with_a_valid_token(
        self, raw_client: AsyncClient, test_user: User
    ):
        """Origin is checked alongside the token, not instead of it."""
        await login_student(raw_client, test_user)
        token = raw_client.cookies.get(CSRF_COOKIE_NAME)

        response = await raw_client.patch(
            ME,
            json={"first_name": "Mallory"},
            headers={CSRF_HEADER_NAME: token, "Origin": "https://attacker.example"},
        )

        assert response.status_code == 403
        assert response.headers["X-Error-Code"] == CODE_CSRF

    @pytest.mark.asyncio
    async def test_the_refusal_does_not_say_which_half_failed(
        self, raw_client: AsyncClient, test_user: User
    ):
        """A probing page must not learn whether it needs a token or a better one."""
        await login_student(raw_client, test_user)
        token = raw_client.cookies.get(CSRF_COOKIE_NAME)

        missing = await raw_client.patch(
            ME, json={"first_name": "x"}, headers={CSRF_HEADER_NAME: ""}
        )
        foreign = await raw_client.patch(
            ME,
            json={"first_name": "x"},
            headers={CSRF_HEADER_NAME: token, "Origin": "https://attacker.example"},
        )

        assert missing.status_code == foreign.status_code == 403
        # Only the per-request reference may differ between the two.
        assert (
            missing.json()["detail"].split(" (ref:")[0]
            == foreign.json()["detail"].split(" (ref:")[0]
        )

    @pytest.mark.asyncio
    async def test_reads_need_no_token(self, raw_client: AsyncClient, test_user: User):
        await login_student(raw_client, test_user)
        raw_client.cookies.delete(CSRF_COOKIE_NAME)

        assert (await raw_client.get(ME)).status_code == 200

    @pytest.mark.asyncio
    async def test_a_cold_client_is_issued_a_token_by_reading(self, raw_client: AsyncClient):
        """Bootstrapping: the first GET hands back what the first POST will need."""
        response = await raw_client.get(SESSION)

        assert response.status_code == 401
        assert raw_client.cookies.get(CSRF_COOKIE_NAME)

    @pytest.mark.asyncio
    async def test_the_token_cookie_is_readable_by_the_page(self, raw_client: AsyncClient):
        """Not httpOnly, on purpose: the client has to copy it into the header.

        Safe only because the token authorizes nothing by itself - it is checked
        against the session cookie, which stays httpOnly.
        """
        response = await raw_client.get(SESSION)

        cookie = next(
            value
            for key, value in response.headers.multi_items()
            if key.lower() == "set-cookie" and value.startswith(CSRF_COOKIE_NAME)
        )
        assert "httponly" not in cookie.lower()
        assert "samesite=lax" in cookie.lower()


class TestCookieHardening:
    def test_session_cookies_are_httponly_lax_and_secure_in_production(self):
        """Secure tracks the environment; httpOnly and SameSite never relax.

        Asserted on the transports rather than on one response, so the check
        covers both identities and does not need the test env to be production.
        """
        from app.config import IS_PRODUCTION

        for transport in (cookie_transport, cookie_transport_company):
            assert transport.cookie_httponly is True
            assert transport.cookie_samesite == "lax"
            assert transport.cookie_secure is IS_PRODUCTION


class TestRotation:
    @pytest.mark.asyncio
    async def test_login_rotates_the_token(self, raw_client: AsyncClient, test_user: User):
        """A token planted before login must not survive it (session fixation)."""
        await raw_client.get(SESSION)
        before = raw_client.cookies.get(CSRF_COOKIE_NAME)

        await login_student(raw_client, test_user)
        after = raw_client.cookies.get(CSRF_COOKIE_NAME)

        assert before and after and before != after

    @pytest.mark.asyncio
    async def test_logout_rotates_the_token(self, raw_client: AsyncClient, test_user: User):
        await login_student(raw_client, test_user)
        before = raw_client.cookies.get(CSRF_COOKIE_NAME)

        await raw_client.post(STUDENT_LOGOUT, headers={CSRF_HEADER_NAME: before})
        after = raw_client.cookies.get(CSRF_COOKIE_NAME)

        assert before and after and before != after

    @pytest.mark.asyncio
    async def test_a_failed_login_does_not_rotate(
        self, raw_client: AsyncClient, test_user: User
    ):
        """Nothing changed identity, so nothing needs re-issuing."""
        await raw_client.get(SESSION)
        before = raw_client.cookies.get(CSRF_COOKIE_NAME)

        refused = await raw_client.post(
            STUDENT_LOGIN,
            data={"username": test_user.email, "password": "wrongpassword"},
            headers={CSRF_HEADER_NAME: before},
        )

        assert refused.status_code == 400
        assert raw_client.cookies.get(CSRF_COOKIE_NAME) == before

    @pytest.mark.asyncio
    async def test_refresh_reissues_both_halves(self, client: AsyncClient, test_user: User):
        await login_student(client, test_user)
        before = client.cookies.get(CSRF_COOKIE_NAME)

        response = await client.post(REFRESH)

        assert response.status_code == 200
        assert response.json()["actor"]["id"] == str(test_user.id)
        assert client.cookies.get(CSRF_COOKIE_NAME) not in (None, before)

        # Read off this response rather than off the jar: the jar would still
        # hold the login's cookie and the assertion would pass without a refresh
        # having happened at all.
        reissued = {
            value.split("=", 1)[0]
            for key, value in response.headers.multi_items()
            if key.lower() == "set-cookie"
        }
        assert cookie_transport.cookie_name in reissued
        assert CSRF_COOKIE_NAME in reissued

    @pytest.mark.asyncio
    async def test_refresh_requires_an_actor(self, client: AsyncClient):
        assert (await client.post(REFRESH)).status_code == 401


class TestActorSeparation:
    """Each cookie reaches its own surface and no further."""

    @pytest.mark.asyncio
    async def test_a_recruiter_cookie_is_not_a_student(
        self, client: AsyncClient, test_company_recruiter: CompanyRecruiter
    ):
        await login_recruiter(client, test_company_recruiter)

        assert (await client.get(ME)).status_code == 401

    @pytest.mark.asyncio
    async def test_a_student_cookie_is_not_a_recruiter(
        self, client: AsyncClient, test_user: User
    ):
        await login_student(client, test_user)

        assert (await client.get("/api/v1/companies/me")).status_code == 401


class TestLoginPathParity:
    """Both actors are addressed the same way, and the old path still answers."""

    @pytest.mark.asyncio
    async def test_the_student_login_path_mirrors_the_company_one(
        self, client: AsyncClient, test_user: User
    ):
        assert (await login_student(client, test_user)).status_code in (200, 204)
        assert client.cookies.get(cookie_transport.cookie_name)

    @pytest.mark.asyncio
    async def test_the_legacy_jwt_path_still_works(self, client: AsyncClient, test_user: User):
        """The Jinja pages still call it; breaking it would log everyone out."""
        response = await login_student(client, test_user, path="/auth/jwt/login")

        assert response.status_code in (200, 204)
        assert (await client.get(SESSION)).json()["actor"]["id"] == str(test_user.id)
