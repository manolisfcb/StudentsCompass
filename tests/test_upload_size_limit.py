import pytest
from httpx import AsyncClient

import app.routes.resumeRoute as resume_route


@pytest.mark.asyncio
async def test_oversized_cv_upload_is_rejected(client: AsyncClient, auth_headers: dict, monkeypatch):
    monkeypatch.setattr(resume_route, "MAX_UPLOAD_BYTES", 50)

    response = await client.post(
        "/api/v1/profile/cv/upload",
        headers=auth_headers,
        files={"cv": ("resume.pdf", b"x" * 500, "application/pdf")},
    )

    assert response.status_code == 413
