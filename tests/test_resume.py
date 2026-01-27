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
    async def test_upload_resume_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        mock_s3_service
    ):
        """Test successful resume upload"""
        # Create a fake PDF file
        pdf_content = b"%PDF-1.4 fake pdf content"
        files = {
            "cv": ("test_resume.pdf", io.BytesIO(pdf_content), "application/pdf")
        }
        
        response = await client.post(
            "/api/v1/profile/cv/upload",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["original_filename"] == "test_resume.pdf"
        assert "view_url" in data
    
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
    async def test_get_user_resumes(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession
    ):
        """Test getting user's resumes"""
        # Create test resumes
        resume1 = ResumeModel(
            user_id=test_user.id,
            view_url="https://example.com/resume1.pdf",
            original_filename="resume1.pdf",
            storage_file_id="test/resume1.pdf"
        )
        resume2 = ResumeModel(
            user_id=test_user.id,
            view_url="https://example.com/resume2.pdf",
            original_filename="resume2.pdf",
            storage_file_id="test/resume2.pdf"
        )
        db_session.add_all([resume1, resume2])
        await db_session.commit()
        
        response = await client.get(
            "/api/v1/profile/cv",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all("original_filename" in resume for resume in data)
    
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
    async def test_delete_resume(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
        mock_s3_service
    ):
        """Test deleting a resume"""
        # Create test resume
        resume = ResumeModel(
            user_id=test_user.id,
            view_url="https://example.com/resume.pdf",
            original_filename="resume.pdf",
            storage_file_id="test/resume.pdf"
        )
        db_session.add(resume)
        await db_session.commit()
        await db_session.refresh(resume)
        
        response = await client.delete(
            f"/api/v1/profile/cv/{resume.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        # Verify resume is deleted
        response = await client.get(
            "/api/v1/profile/cv",
            headers=auth_headers
        )
        assert len(response.json()) == 0
    
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
    
    @pytest.mark.asyncio
    async def test_delete_other_user_resume(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession
    ):
        """Test users can't delete other users' resumes"""
        # Create another user
        from app.models.userModel import User
        import uuid
        
        other_user = User(
            id=uuid.uuid4(),
            email="other@example.com",
            hashed_password="hashed",
            is_active=True
        )
        db_session.add(other_user)
        
        # Create resume for other user
        resume = ResumeModel(
            user_id=other_user.id,
            view_url="https://example.com/resume.pdf",
            original_filename="resume.pdf",
            storage_file_id="test/resume.pdf"
        )
        db_session.add(resume)
        await db_session.commit()
        await db_session.refresh(resume)
        
        # Try to delete as test_user
        response = await client.delete(
            f"/api/v1/profile/cv/{resume.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 404  # Not found (user can't see it)
