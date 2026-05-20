
from sqlalchemy import select
from app.schemas.postSchema import PostCreate, PostRead
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID


class MockIaInterviewService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_mock_interviews(self, user_id: UUID, job_description: str ):
        # Implementation for retrieving mock interviews
        pass

    async def create_mock_interview(self, user_id: UUID, data: dict):
        # Implementation for creating a mock interview session
        pass
