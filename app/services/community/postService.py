from app.models.postModel import PostModel
from sqlalchemy import select
from app.schemas.postSchema import PostCreate, PostRead
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

class PostService:
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def create_post(self, post_create: PostCreate, user_id: UUID | None = None) -> PostModel:
        new_post = PostModel(
            caption=post_create.caption,
            url=post_create.url,
            file_type=post_create.file_type,
            file_name=post_create.file_name,
            user_id=user_id,
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
    
    
    async def delete_post(self, post_id: UUID, *, user_id: UUID) -> bool:
        """Delete a post the caller owns. Returns False if there is none.

        Ownership is part of the lookup, not a check after it: filtering by
        ``user_id`` means another user's post is indistinguishable from a
        missing one, so the endpoint cannot be used to probe which post IDs
        exist.

        Legacy posts with a NULL ``user_id`` (created before authorship was
        recorded) belong to nobody, so this comparison never matches them and
        they are not deletable through this path. Removing them is a separate,
        deliberate operation — it is not granted implicitly to whoever asks.
        """
        result = await self.session.execute(
            select(PostModel).where(
                PostModel.id == post_id,
                PostModel.user_id == user_id,
            )
        )
        post = result.scalar_one_or_none()
        if post is None:
            return False

        await self.session.delete(post)
        await self.session.commit()
        return True
