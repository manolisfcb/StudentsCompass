from app.models.resumeModel import ResumeModel
from sqlalchemy import select
from app.schemas.resumeSchema import CreateResumeSchema
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError
from io import BytesIO
import os
import pickle
import logging
import asyncio

LOGGER = logging.getLogger(__name__)

FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
SCOPES = ['https://www.googleapis.com/auth/drive.file']

class ResumeService:
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def create_resume(self, resume_create: CreateResumeSchema) -> ResumeModel:
        resume = ResumeModel(
            user_id = resume_create.user_id,
            view_url=resume_create.view_url,
            original_filename=resume_create.original_filename,
            storage_file_id=resume_create.storage_file_id,
            folder_id=resume_create.folder_id
        )
        self.session.add(resume)
        await self.session.commit()
        await self.session.refresh(resume)
        return resume

    async def list_user_resumes(self, user_id: UUID) -> list[ResumeModel]:
        result = await self.session.execute(
            select(ResumeModel)
            .where(ResumeModel.user_id == user_id)
            .order_by(ResumeModel.created_at.desc())
        )
        return list(result.scalars().all())
    
    
    async def get_drive_service(self):
        """Async method to get Google Drive service with non-blocking auth"""
        TOKEN_FILE = 'app/credentials/token.pickle'
        CLIENT_SECRET_FILE = 'app/credentials/google_oauth_client.json'
        
        if not os.path.exists(CLIENT_SECRET_FILE):
            raise FileNotFoundError(
                f"OAuth client file not found at {CLIENT_SECRET_FILE}. "
                "Please download OAuth 2.0 credentials from Google Cloud Console."
            )

        loop = asyncio.get_event_loop()
        
        # Load existing token if available (run in executor to avoid blocking)
        def load_token():
            if os.path.exists(TOKEN_FILE):
                with open(TOKEN_FILE, 'rb') as token:
                    return pickle.load(token)
            return None
        
        creds = await loop.run_in_executor(None, load_token)
        
        # If no valid credentials, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # Refresh token (blocking HTTP call - run in executor)
                LOGGER.info("Refreshing Google Drive credentials...")
                def refresh_creds(credentials):
                    credentials.refresh(Request())
                    return credentials
                creds = await loop.run_in_executor(None, refresh_creds, creds)
            else:
                # This should rarely happen in production - requires manual auth
                def run_oauth_flow():
                    flow = InstalledAppFlow.from_client_secrets_file(
                        CLIENT_SECRET_FILE, SCOPES)
                    return flow.run_local_server(port=8080)
                
                creds = await loop.run_in_executor(None, run_oauth_flow)
            
            # Save credentials for future use (run in executor)
            def save_token(credentials):
                with open(TOKEN_FILE, 'wb') as token:
                    pickle.dump(credentials, token)
            
            await loop.run_in_executor(None, save_token, creds)

        # Build service (can be blocking, run in executor)
        def build_service(credentials):
            return build('drive', 'v3', credentials=credentials)
        
        service = await loop.run_in_executor(None, build_service, creds)
        return service
    
    async def upload_pdf_to_drive(self, file_bytes: bytes, file_name: str, mime_type: str = "application/pdf") -> dict:
        """Async method to upload PDF to Google Drive"""
        service = await self.get_drive_service()
        
        file_metadata = {
            'name': file_name,
            'parents': [FOLDER_ID]
        }

        media = MediaIoBaseUpload(
            BytesIO(file_bytes),
            mimetype=mime_type,
            resumable=True
        )
        
        # Run the upload in executor to avoid blocking
        loop = asyncio.get_event_loop()
        
        def do_upload():
            return service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink',
                supportsAllDrives=True
            ).execute()
        
        file = await loop.run_in_executor(None, do_upload)
        
        return {
            "file_id": file.get('id'),
            "view_url": file.get('webViewLink'),
            "original_filename": file_name
        }

    async def delete_resume(self, resume_id: UUID, user_id: UUID) -> bool:
        resume = await self.session.get(ResumeModel, resume_id)
        if not resume or resume.user_id != user_id:
            return False

        # Try deleting from Drive, but don't fail DB deletion if file missing
        try:
            service = await self.get_drive_service()
            service.files().delete(fileId=resume.storage_file_id, supportsAllDrives=True).execute()
        except HttpError as e:
            # Log and continue (e.g., file already removed)
            LOGGER.warning("Drive delete failed for %s: %s", resume.storage_file_id, e)

        await self.session.delete(resume)
        await self.session.commit()
        return True