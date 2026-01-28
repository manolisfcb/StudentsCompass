"""
Tests for resume/CV endpoints
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.userModel import User
from app.models.resumeModel import ResumeModel
import io


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
 