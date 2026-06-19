"""
Tests for resume/CV endpoints
"""
import io
import uuid
from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resumeModel import ResumeModel
from app.models.userModel import User
from app.schemas.resumeSchema import ResumeReadSchema


class FakeResumeStorageService:
    def __init__(self):
        self.uploaded = None

    async def upload_file(
        self,
        file_bytes: bytes,
        file_name: str,
        content_type: str = "application/octet-stream",
        folder: str = "resumes",
    ) -> dict:
        self.uploaded = {
            "file_bytes": file_bytes,
            "file_name": file_name,
            "content_type": content_type,
            "folder": folder,
        }
        return {
            "file_key": f"{folder}/stored_resume.pdf",
            "file_url": "https://storage.example/resumes/stored_resume.pdf",
            "bucket": "test-resume-bucket",
        }

    async def download_file(self, file_key: str) -> bytes:
        return b"%PDF-1.4 fake pdf content"

    async def delete_file(self, file_key: str) -> bool:
        return True


class TestResume:
    """Test resume endpoints"""
    
    @pytest.mark.asyncio
    async def test_upload_resume_unauthorized(self, client: AsyncClient):
        """Test resume upload without authentication fails"""
        pdf_content = b"%PDF-1.4 fake pdf content"
        files = {
            "cv": ("test_resume.pdf", io.BytesIO(pdf_content), "application/pdf")
        }
        
        response = await client.post(
            "/api/v1/profile/cv/upload",
            files=files
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_upload_non_pdf_file(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test uploading non-PDF file fails"""
        files = {
            "cv": ("test.txt", io.BytesIO(b"Not a PDF"), "text/plain")
        }
        
        response = await client.post(
            "/api/v1/profile/cv/upload",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_resume_uses_configured_storage(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ):
        fake_storage = FakeResumeStorageService()
        monkeypatch.setenv("BUCKET_NAME", "test-resume-bucket")
        monkeypatch.setattr("app.services.resumes.resumeService.get_storage_service", lambda: fake_storage)

        response = await client.post(
            "/api/v1/profile/cv/upload",
            headers=auth_headers,
            files={
                "cv": (
                    "resume.pdf",
                    io.BytesIO(b"%PDF-1.4 fake pdf content"),
                    "application/pdf",
                )
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["file_url"] == "https://storage.example/resumes/stored_resume.pdf"

        created_resume = await db_session.get(ResumeModel, uuid.UUID(payload["resume_id"]))
        assert created_resume is not None
        assert created_resume.user_id == test_user.id
        assert created_resume.storage_file_id == "resumes/stored_resume.pdf"
        assert created_resume.folder_id == "test-resume-bucket"
        assert fake_storage.uploaded["content_type"] == "application/pdf"
   
    @pytest.mark.asyncio
    async def test_get_resumes_empty(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test getting resumes when user has none"""
        response = await client.get(
            "/api/v1/profile/cv",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json() == []
    
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_resume(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test deleting non-existent resume fails"""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await client.delete(
            f"/api/v1/profile/cv/{fake_uuid}",
            headers=auth_headers
        )
        
        assert response.status_code == 404


def test_resume_read_schema_serializes_model_created_at():
    created_at = datetime(2026, 1, 2, 3, 4, 5)
    user_id = uuid.uuid4()
    resume = ResumeModel(
        id=uuid.uuid4(),
        user_id=user_id,
        view_url="https://example.com/resume.pdf",
        original_filename="resume.pdf",
        storage_file_id="resumes/resume.pdf",
        folder_id="resume-bucket",
        ai_summary="Backend candidate",
        contact_phone="+1 416 555 0101",
        created_at=created_at,
    )

    payload = ResumeReadSchema.from_model(resume)

    assert payload.id == resume.id
    assert payload.user_id == user_id
    assert payload.view_url == "https://example.com/resume.pdf"
    assert payload.original_filename == "resume.pdf"
    assert payload.storage_file_id == "resumes/resume.pdf"
    assert payload.folder_id == "resume-bucket"
    assert payload.ai_summary == "Backend candidate"
    assert payload.contact_phone == "+1 416 555 0101"
    assert payload.created_at == "2026-01-02T03:04:05"
