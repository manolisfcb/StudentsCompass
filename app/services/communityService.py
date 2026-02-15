from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.models.communityModel import CommunityModel, CommunityMemberModel
from app.models.communityPostModel import (
    CommunityPostModel,
    CommunityPostLikeModel,
    CommunityPostCommentModel,
)
from app.models.userModel import User
from app.schemas.communitySchema import CommunityCreate, CommunityPostCreate, CommunityPostCommentCreate


class CommunityService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_community_by_name(self, name: str) -> CommunityModel | None:
        result = await self.session.execute(
            select(CommunityModel).where(CommunityModel.name == name)
        )
        return result.scalar_one_or_none()

    async def get_community_by_id(self, community_id: UUID) -> CommunityModel | None:
        result = await self.session.execute(
            select(CommunityModel).where(CommunityModel.id == community_id)
        )
        return result.scalar_one_or_none()

    async def list_communities(self) -> list[CommunityModel]:
        result = await self.session.execute(
            select(CommunityModel).order_by(CommunityModel.created_at.desc())
        )
        return result.scalars().all()

    async def create_community(self, community_data: CommunityCreate, user_id: UUID) -> CommunityModel:
        member_count = community_data.member_count if community_data.member_count is not None else 1
        community = CommunityModel(
            name=community_data.name,
            description=community_data.description,
            icon=community_data.icon,
            activity_status=community_data.activity_status,
            tags=community_data.tags,
            member_count=member_count,
            created_by=user_id,
        )
        self.session.add(community)
        await self.session.flush()

        membership = CommunityMemberModel(community_id=community.id, user_id=user_id)
        self.session.add(membership)

        await self.session.commit()
        await self.session.refresh(community)
        return community

    async def is_member(self, community_id: UUID, user_id: UUID) -> bool:
        result = await self.session.execute(
            select(CommunityMemberModel).where(
                CommunityMemberModel.community_id == community_id,
                CommunityMemberModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def join_community(self, community_id: UUID, user_id: UUID) -> CommunityMemberModel:
        community = await self.get_community_by_id(community_id)
        if not community:
            raise ValueError("Community not found")
        membership = CommunityMemberModel(community_id=community_id, user_id=user_id)
        self.session.add(membership)
        community.member_count = (community.member_count or 0) + 1
        await self.session.commit()
        await self.session.refresh(membership)
        return membership

    async def leave_community(self, community_id: UUID, user_id: UUID) -> None:
        """Remove user from community. Cannot leave if user is the creator."""
        community = await self.get_community_by_id(community_id)
        if not community:
            raise ValueError("Community not found")
        result = await self.session.execute(
            select(CommunityMemberModel).where(
                CommunityMemberModel.community_id == community_id,
                CommunityMemberModel.user_id == user_id,
            )
        )
        membership = result.scalar_one_or_none()
        if not membership:
            raise ValueError("Not a member")
        await self.session.delete(membership)
        community.member_count = max((community.member_count or 1) - 1, 0)
        await self.session.commit()

    async def list_posts(self, community_id: UUID) -> list[CommunityPostModel]:
        result = await self.session.execute(
            select(CommunityPostModel)
            .where(CommunityPostModel.community_id == community_id)
            .order_by(CommunityPostModel.created_at.desc())
        )
        return result.scalars().all()

    async def get_post_by_id(self, post_id: UUID) -> CommunityPostModel | None:
        result = await self.session.execute(
            select(CommunityPostModel).where(CommunityPostModel.id == post_id)
        )
        return result.scalar_one_or_none()

    async def create_post(
        self,
        community_id: UUID,
        user_id: UUID,
        post_data: CommunityPostCreate,
    ) -> CommunityPostModel:
        post = CommunityPostModel(
            community_id=community_id,
            user_id=user_id,
            title=post_data.title,
            content=post_data.content,
        )
        self.session.add(post)
        await self.session.commit()
        await self.session.refresh(post)
        return post

    async def like_post(self, post_id: UUID, user_id: UUID) -> CommunityPostLikeModel:
        like = CommunityPostLikeModel(post_id=post_id, user_id=user_id)
        self.session.add(like)
        await self.session.commit()
        await self.session.refresh(like)
        return like

    async def get_like(self, post_id: UUID, user_id: UUID) -> CommunityPostLikeModel | None:
        result = await self.session.execute(
            select(CommunityPostLikeModel).where(
                CommunityPostLikeModel.post_id == post_id,
                CommunityPostLikeModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def unlike_post(self, post_id: UUID, user_id: UUID) -> None:
        like = await self.get_like(post_id, user_id)
        if like:
            await self.session.delete(like)
            await self.session.commit()

    async def add_comment(
        self,
        post_id: UUID,
        user_id: UUID,
        comment_data: CommunityPostCommentCreate,
    ) -> CommunityPostCommentModel:
        comment = CommunityPostCommentModel(
            post_id=post_id,
            user_id=user_id,
            content=comment_data.content,
        )
        self.session.add(comment)
        await self.session.commit()
        await self.session.refresh(comment)
        return comment

    async def list_comments(self, post_id: UUID) -> list[CommunityPostCommentModel]:
        result = await self.session.execute(
            select(CommunityPostCommentModel)
            .where(CommunityPostCommentModel.post_id == post_id)
            .order_by(CommunityPostCommentModel.created_at.asc())
        )
        return result.scalars().all()

    # ── Enriched queries (author info, counts) ─────────────────────

    async def list_posts_enriched(self, community_id: UUID, current_user_id: UUID) -> list[dict]:
        """Return posts with author name, like count, comment count, and liked_by_me."""
        # Subquery: like count per post
        like_count_sq = (
            select(
                CommunityPostLikeModel.post_id,
                func.count(CommunityPostLikeModel.id).label("like_count"),
            )
            .group_by(CommunityPostLikeModel.post_id)
            .subquery()
        )

        # Subquery: comment count per post
        comment_count_sq = (
            select(
                CommunityPostCommentModel.post_id,
                func.count(CommunityPostCommentModel.id).label("comment_count"),
            )
            .group_by(CommunityPostCommentModel.post_id)
            .subquery()
        )

        # Subquery: did current user like?
        my_like_sq = (
            select(CommunityPostLikeModel.post_id)
            .where(CommunityPostLikeModel.user_id == current_user_id)
            .subquery()
        )

        stmt = (
            select(
                CommunityPostModel,
                User.first_name,
                User.last_name,
                User.nickname,
                func.coalesce(like_count_sq.c.like_count, 0).label("like_count"),
                func.coalesce(comment_count_sq.c.comment_count, 0).label("comment_count"),
                my_like_sq.c.post_id.label("my_like"),
            )
            .join(User, CommunityPostModel.user_id == User.id)
            .outerjoin(like_count_sq, CommunityPostModel.id == like_count_sq.c.post_id)
            .outerjoin(comment_count_sq, CommunityPostModel.id == comment_count_sq.c.post_id)
            .outerjoin(my_like_sq, CommunityPostModel.id == my_like_sq.c.post_id)
            .where(CommunityPostModel.community_id == community_id)
            .order_by(CommunityPostModel.created_at.desc())
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        enriched = []
        for post, first_name, last_name, nickname, lc, cc, my_like in rows:
            author = _build_author_name(first_name, last_name, nickname)
            enriched.append({
                "id": str(post.id),
                "community_id": str(post.community_id),
                "user_id": str(post.user_id),
                "title": post.title,
                "content": post.content,
                "created_at": post.created_at.isoformat(),
                "author_name": author,
                "like_count": lc,
                "comment_count": cc,
                "liked_by_me": my_like is not None,
            })
        return enriched

    async def list_comments_enriched(self, post_id: UUID) -> list[dict]:
        """Return comments with author name."""
        stmt = (
            select(
                CommunityPostCommentModel,
                User.first_name,
                User.last_name,
                User.nickname,
            )
            .join(User, CommunityPostCommentModel.user_id == User.id)
            .where(CommunityPostCommentModel.post_id == post_id)
            .order_by(CommunityPostCommentModel.created_at.asc())
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        enriched = []
        for comment, first_name, last_name, nickname in rows:
            author = _build_author_name(first_name, last_name, nickname)
            enriched.append({
                "id": str(comment.id),
                "post_id": str(comment.post_id),
                "user_id": str(comment.user_id),
                "content": comment.content,
                "created_at": comment.created_at.isoformat(),
                "author_name": author,
            })
        return enriched

    async def get_like_count(self, post_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count(CommunityPostLikeModel.id)).where(
                CommunityPostLikeModel.post_id == post_id
            )
        )
        return result.scalar() or 0


def _build_author_name(first_name: str | None, last_name: str | None, nickname: str | None) -> str:
    """Build a display name from user fields."""
    if first_name and last_name:
        return f"{first_name} {last_name}"
    if first_name:
        return first_name
    if nickname:
        return nickname
    return "Miembro"
