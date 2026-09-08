"""
Tests for authentication endpoints
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.userModel import User
from app.models.companyRecruiterModel import CompanyRecruiter
from sqlalchemy import select


class TestAuth:
    """Test authentication endpoints"""
    
    @pytest.mark.asyncio
    async def test_register_user_success(self, client: AsyncClient):
        """Test successful user registration"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "StrongPass123!",
                "is_active": True,
                "is_superuser": False,
                "is_verified": False
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert "id" in data
        assert "hashed_password" not in data  # Should not expose password
    
    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, test_user: User):
        """Test registration with duplicate email fails"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user.email,
                "password": "AnotherPass123!",
                "is_active": True,
                "is_superuser": False,
                "is_verified": False
            }
        )
        
        assert response.status_code == 400
        assert "REGISTER_USER_ALREADY_EXISTS" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email fails"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "StrongPass123!",
                "is_active": True,
                "is_superuser": False,
                "is_verified": False
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user: User):
        """Test successful login"""
        response = await client.post(
            "/auth/jwt/login",
            data={
                "username": test_user.email,
                "password": "password123"
            }
        )

        # CookieTransport login typically returns 204 No Content and sets cookie.
        assert response.status_code in (200, 204)
        if response.status_code == 204:
            assert "set-cookie" in {k.lower() for k in response.headers.keys()}
    
    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        """Test login with wrong password fails"""
        response = await client.post(
            "/auth/jwt/login",
            data={
                "username": test_user.email,
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 400
        assert "LOGIN_BAD_CREDENTIALS" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with non-existent user fails"""
        response = await client.post(
            "/auth/jwt/login",
            data={
                "username": "nonexistent@example.com",
                "password": "password123"
            }
        )
        
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_get_current_user(self, client: AsyncClient, auth_headers: dict, test_user: User):
        """Test getting current authenticated user"""
        response = await client.get(
            "/api/v1/users/me",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["id"] == str(test_user.id)
    
    @pytest.mark.asyncio
    async def test_get_current_user_unauthorized(self, client: AsyncClient):
        """Test getting current user without auth fails"""
        response = await client.get("/api/v1/users/me")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_logout(self, client: AsyncClient, auth_headers: dict):
        """Test logout endpoint"""
        response = await client.post(
            "/auth/jwt/logout",
            headers=auth_headers
        )
        
        # Note: JWT logout typically returns 204 or 200
        assert response.status_code in [200, 204]

    @pytest.mark.asyncio
    async def test_register_company_creates_owner_recruiter(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Company registration should create both company profile and owner recruiter."""
        response = await client.post(
            "/api/v1/auth/company/register",
            json={
                "email": "newcompany@example.com",
                "password": "StrongPass123!",
                "company_name": "New Company Inc.",
                "industry": "Technology",
                "contact_person": "Owner Name",
                "location": "Toronto",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "email" not in data
        assert data["company_name"] == "New Company Inc."

        recruiter_result = await db_session.execute(
            select(CompanyRecruiter).where(CompanyRecruiter.email == "newcompany@example.com")
        )
        recruiter = recruiter_result.scalar_one_or_none()
        assert recruiter is not None
        assert recruiter.role == "owner"

    @pytest.mark.asyncio
    async def test_company_login_and_profile_me(
        self,
        client: AsyncClient,
    ):
        """Company recruiter should login and fetch /companies/me profile."""
        register_response = await client.post(
            "/api/v1/auth/company/register",
            json={
                "email": "companyme@example.com",
                "password": "StrongPass123!",
                "company_name": "Profile Co",
            },
        )
        assert register_response.status_code == 201

        login_response = await client.post(
            "/api/v1/auth/company/login",
            data={
                "username": "companyme@example.com",
                "password": "StrongPass123!",
            },
        )
        assert login_response.status_code in (200, 204)

        profile_response = await client.get("/api/v1/companies/me")
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert "email" not in profile_data
        assert profile_data["company_name"] == "Profile Co"
