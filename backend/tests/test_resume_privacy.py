import uuid

import pytest
from fastapi_users.password import PasswordHelper
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resumeModel import ResumeModel
from app.models.userModel import User


@pytest.mark.asyncio
async def test_profile_cv_list_only_returns_current_user_resumes(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession,
):
    password_helper = PasswordHelper()
    other_user = User(
        id=uuid.uuid4(),
        email="other@example.com",
        hashed_password=password_helper.hash("password123"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        nickname="other",
    )
    db_session.add(other_user)
    await db_session.commit()

    own_resume = ResumeModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        view_url="https://example.com/my-resume.pdf",
        storage_file_id="resumes/my.pdf",
        original_filename="my_resume.pdf",
        folder_id="test-bucket",
    )
    other_resume = ResumeModel(
        id=uuid.uuid4(),
        user_id=other_user.id,
        view_url="https://example.com/other-resume.pdf",
        storage_file_id="resumes/other.pdf",
        original_filename="other_resume.pdf",
        folder_id="test-bucket",
    )
    db_session.add_all([own_resume, other_resume])
    await db_session.commit()

    response = await client.get("/api/v1/profile/cv", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data] == [str(own_resume.id)]
    assert response.headers["cache-control"] == "no-store, private"
