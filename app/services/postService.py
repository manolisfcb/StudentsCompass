from app.models import PostModel
from sqlalchemy import select
from app.schemas.postSchema import PostCreate, PostRead
from sqlalchemy.ext.asyncio import AsyncSession

class PostService:
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def create_post(self, post_create: PostCreate) -> PostModel:
        new_post = PostCreate(
            caption=post_create.caption,
            url=post_create.url,
            file_type=post_create.file_type,
            file_name=post_create.file_name
        )
        self.session.add(new_post)
        await self.session.commit()
        await self.session.refresh(new_post)
        return new_post
    
    async def get_post_by_id(self, post_id: int) -> PostRead | None:
        result = await self.session.get(PostRead, post_id)
        return PostRead.model_validate(result) if result else None
