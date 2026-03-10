import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi_users.password import PasswordHelper

from app.models.companyRecruiterModel import CompanyRecruiter


class TestCompanyRecruiterManagement:
    @pytest.mark.asyncio
    async def test_owner_can_list_company_recruiters(
        self,
        client: AsyncClient,
        company_auth_headers: dict,
        test_company_recruiter: CompanyRecruiter,
    ):
        response = await client.get(
            "/api/v1/companies/me/recruiters",
            headers=company_auth_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["id"] == str(test_company_recruiter.id)
        assert payload[0]["role"] == "owner"

    @pytest.mark.asyncio
    async def test_owner_can_create_company_recruiter(
        self,
        client: AsyncClient,
        company_auth_headers: dict,
        db_session: AsyncSession,
    ):
        response = await client.post(
            "/api/v1/companies/me/recruiters",
            headers=company_auth_headers,
            json={
                "email": "recruiter1@example.com",
                "password": "StrongPass123!",
                "first_name": "Jamie",
                "last_name": "Rivera",
                "role": "recruiter",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "recruiter1@example.com"
        assert data["role"] == "recruiter"

        recruiter_result = await db_session.execute(
            select(CompanyRecruiter).where(CompanyRecruiter.email == "recruiter1@example.com")
        )
        recruiter = recruiter_result.scalar_one_or_none()
        assert recruiter is not None
        assert recruiter.first_name == "Jamie"

    @pytest.mark.asyncio
    async def test_non_owner_cannot_manage_recruiters(
        self,
        client: AsyncClient,
        test_company_recruiter: CompanyRecruiter,
        db_session: AsyncSession,
    ):
        password_helper = PasswordHelper()
        non_owner = CompanyRecruiter(
            id=uuid.uuid4(),
            company_id=test_company_recruiter.company_id,
            email="viewer@example.com",
            hashed_password=password_helper.hash("password123"),
            is_active=True,
            is_superuser=False,
            is_verified=True,
            role="viewer",
        )
        db_session.add(non_owner)
        await db_session.commit()

        login_response = await client.post(
            "/api/v1/auth/company/login",
            data={
                "username": non_owner.email,
                "password": "password123",
            },
        )
        assert login_response.status_code in (200, 204)

        response = await client.get("/api/v1/companies/me/recruiters")
        assert response.status_code == 403
        assert response.json()["detail"] == "Only company owners can manage recruiters"

    @pytest.mark.asyncio
    async def test_owner_can_update_recruiter(
        self,
        client: AsyncClient,
        company_auth_headers: dict,
        test_company_recruiter: CompanyRecruiter,
        db_session: AsyncSession,
    ):
        password_helper = PasswordHelper()
        target_recruiter = CompanyRecruiter(
            id=uuid.uuid4(),
            company_id=test_company_recruiter.company_id,
            email="update-me@example.com",
            hashed_password=password_helper.hash("password123"),
            is_active=True,
            is_superuser=False,
            is_verified=True,
            role="recruiter",
            first_name="Taylor",
        )
        db_session.add(target_recruiter)
        await db_session.commit()

        response = await client.patch(
            f"/api/v1/companies/me/recruiters/{target_recruiter.id}",
            headers=company_auth_headers,
            json={
                "role": "admin",
                "is_active": False,
                "first_name": "Jordan",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "admin"
        assert data["is_active"] is False
        assert data["first_name"] == "Jordan"

    @pytest.mark.asyncio
    async def test_owner_cannot_delete_themselves(
        self,
        client: AsyncClient,
        company_auth_headers: dict,
        test_company_recruiter: CompanyRecruiter,
    ):
        response = await client.delete(
            f"/api/v1/companies/me/recruiters/{test_company_recruiter.id}",
            headers=company_auth_headers,
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "OWNERS_CANNOT_DELETE_THEMSELVES"

    @pytest.mark.asyncio
    async def test_company_must_keep_at_least_one_owner(
        self,
        client: AsyncClient,
        company_auth_headers: dict,
        test_company_recruiter: CompanyRecruiter,
    ):
        response = await client.patch(
            f"/api/v1/companies/me/recruiters/{test_company_recruiter.id}",
            headers=company_auth_headers,
            json={
                "role": "recruiter",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "COMPANY_MUST_KEEP_AT_LEAST_ONE_OWNER"

    @pytest.mark.asyncio
    async def test_owner_can_delete_other_recruiter(
        self,
        client: AsyncClient,
        company_auth_headers: dict,
        test_company_recruiter: CompanyRecruiter,
        db_session: AsyncSession,
    ):
        password_helper = PasswordHelper()
        target_recruiter = CompanyRecruiter(
            id=uuid.uuid4(),
            company_id=test_company_recruiter.company_id,
            email="delete-me@example.com",
            hashed_password=password_helper.hash("password123"),
            is_active=True,
            is_superuser=False,
            is_verified=True,
            role="recruiter",
        )
        db_session.add(target_recruiter)
        await db_session.commit()

        response = await client.delete(
            f"/api/v1/companies/me/recruiters/{target_recruiter.id}",
            headers=company_auth_headers,
        )

        assert response.status_code == 204

        recruiter_result = await db_session.execute(
            select(CompanyRecruiter).where(CompanyRecruiter.id == target_recruiter.id)
        )
        assert recruiter_result.scalar_one_or_none() is None
