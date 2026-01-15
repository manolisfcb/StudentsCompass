from app.models.postModel import PostModel
from sqlalchemy import select
from app.schemas.postSchema import PostCreate, PostRead
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

class PostService:
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def create_post(self, post_create: PostCreate) -> PostModel:
        new_post = PostModel(
            caption=post_create.caption,
            url=post_create.url,
            file_type=post_create.file_type,
            file_name=post_create.file_name
        )
        self.session.add(new_post)
        await self.session.commit()
        await self.session.refresh(new_post)
        return new_post
    
    async def get_post_by_id(self, post_id: UUID) -> PostRead | None:
        result = await self.session.get(PostModel, post_id)
        return PostRead.model_validate(result) if result else None

    async def get_all_posts(self) -> list[PostRead]:
        result = await self.session.execute(select(PostModel).order_by(PostModel.created_at.desc()))
        posts = result.scalars().all()
        return [post for post in posts]
    
    
    async def delete_post(self, post_id: UUID) -> None:
        post = await self.session.get(PostModel, post_id)
        if post:
            await self.session.delete(post)
            await self.session.commit()
        else:
            raise Exception("Post not found")