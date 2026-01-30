"""
Pytest fixtures and configuration for tests
"""
import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.app import app
from app.db import Base, get_session
from app.models.userModel import User
from app.models.companyModel import Company
from app.services.userService import UserManager, get_user_manager
from fastapi_users.password import PasswordHelper
import uuid
import os

# Test database URL (use in-memory SQLite for tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Create test session factory
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def setup_db() -> AsyncGenerator[None, None]:
    """Create/drop all tables for each test.

    Uses a single shared in-memory SQLite connection (StaticPool) so the schema
    is visible to all sessions used during the test.
    """
    # Import all models before creating tables
    from app.models.userModel import User
    from app.models.companyModel import Company
    from app.models.applicationModel import ApplicationModel
    from app.models.jobPostingModel import JobPosting
    from app.models.resumeModel import ResumeModel
    from app.models.questionnaireModel import UserQuestionnaire
    from app.models.postModel import PostModel
    from app.models.jobAnalysisModel import JobAnalysisModel
    from app.models.resumeEmbeddingsModel import ResumeEmbedding
    from app.models.userStatsModel import UserStatsModel

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(setup_db) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client."""
    # Override get_session dependency
    async def override_get_session():
        async with TestSessionLocal() as session:
            yield session
    
    app.dependency_overrides[get_session] = override_get_session
    
    # Create test client
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac
    
    # Cleanup
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session(setup_db) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for direct DB access in tests."""
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    password_helper = PasswordHelper()
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password=password_helper.hash("password123"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        nickname="testuser",
        first_name="Test",
        last_name="User"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_company(db_session: AsyncSession) -> Company:
    """Create a test company."""
    password_helper = PasswordHelper()
    company = Company(
        id=uuid.uuid4(),
        email="company@example.com",
        hashed_password=password_helper.hash("password123"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        company_name="Test Company",
        industry="Technology",
        location="San Francisco, CA"
    )
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)
    return company


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, test_user: User) -> dict:
    """Get authentication headers for test user."""
    response = await client.post(
        "/auth/jwt/login",
        data={
            "username": test_user.email,
            "password": "password123"
        }
    )
    # CookieTransport returns 204 and sets an HttpOnly cookie on the client.
    assert response.status_code in (200, 204)
    # If a token-based backend is ever enabled, keep compatibility.
    if response.status_code == 200 and response.headers.get("content-type", "").startswith("application/json"):
        token = response.json().get("access_token")
        if token:
            return {"Authorization": f"Bearer {token}"}
    return {}


@pytest.fixture
def mock_s3_service(monkeypatch):
    """Mock S3 service to avoid actual AWS calls during tests."""
    class MockS3Service:
        async def upload_file(self, file_bytes: bytes, filename: str, mime_type: str):
            return {
                "file_key": f"test/{filename}",
                "file_url": f"https://test-bucket.s3.amazonaws.com/test/{filename}"
            }
        
        async def download_file(self, file_key: str):
            return b"Mock PDF content"
        
        async def delete_file(self, file_key: str):
            return True
    
    from app.services import s3Service
    monkeypatch.setattr(s3Service, "S3Service", MockS3Service)
    return MockS3Service()


@pytest.fixture
def mock_genai(monkeypatch):
    """Mock Google GenAI to avoid actual API calls during tests."""
    class MockGenAI:
        def generate_content(self, prompt: str):
            class MockResponse:
                text = '{"keywords": ["Python", "FastAPI", "PostgreSQL"], "summary": "Test summary"}'
            return MockResponse()
    
    import google.generativeai as genai
    monkeypatch.setattr(genai, "GenerativeModel", lambda *args, **kwargs: MockGenAI())
