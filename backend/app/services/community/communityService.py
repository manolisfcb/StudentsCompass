from sqlalchemy import case, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.pagination import MAX_COLLECTION_ROWS
from app.models.communityModel import CommunityModel, CommunityMemberModel
from app.models.communityPostModel import (
    CommunityPostModel,
    CommunityPostLikeModel,
    CommunityPostCommentModel,
)
from app.models.userModel import User
from app.schemas.communitySchema import CommunityCreate, CommunityPostCreate, CommunityPostCommentCreate
from app.services.community.userDisplay import build_display_name


class AlreadyMemberError(Exception):
    """Raised when a user is already a member of a community."""


class CommunityService:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def normalize_tags(tags: list[str] | None) -> list[str]:
        if not tags:
            return []

        normalized: list[str] = []
        seen: set[str] = set()
        for raw_tag in tags:
            tag = (raw_tag or "").strip()
            if not tag:
                continue
            key = tag.casefold()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(tag)
        return normalized

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

    async def list_communities(self, tags: list[str] | None = None) -> list[CommunityModel]:
        # Bounded window. Tag filtering still happens in Python because `tags`
        # is a JSON column and a predicate over it behaves differently on SQLite
        # and PostgreSQL — the same problem TASK-063 has to settle for the
        # resource catalogue. What changes here is that the window the filter
        # runs over is finite: the query used to hand it every community on the
        # platform.
        result = await self.session.execute(
            select(CommunityModel)
            .order_by(CommunityModel.created_at.desc())
            .limit(MAX_COLLECTION_ROWS)
        )
        communities = result.scalars().all()
        normalized_tags = {tag.casefold() for tag in self.normalize_tags(tags)}
        if not normalized_tags:
            return communities

        filtered: list[CommunityModel] = []
        for community in communities:
            community_tags = {
                tag.casefold()
                for tag in self.normalize_tags(community.tags or [])
            }
            if normalized_tags.issubset(community_tags):
                filtered.append(community)
        return filtered

    async def list_available_tags(self, query: str | None = None, limit: int = 12) -> list[str]:
        result = await self.session.execute(
            select(CommunityModel.tags).limit(MAX_COLLECTION_ROWS)
        )
        tag_map: dict[str, str] = {}
        normalized_query = (query or "").strip().casefold()
        for community_tags in result.scalars().all():
            for tag in self.normalize_tags(community_tags or []):
                key = tag.casefold()
                if normalized_query and normalized_query not in key:
                    continue
                tag_map.setdefault(key, tag)
        sorted_tags = sorted(tag_map.values(), key=str.casefold)
        return sorted_tags[: max(limit, 1)]

    async def create_community(self, community_data: CommunityCreate, user_id: UUID) -> CommunityModel:
        # Always start at 1 (the creator). The member count is a server-owned
        # counter and must not be taken from client input.
        community = CommunityModel(
            name=community_data.name,
            description=community_data.description,
            icon=community_data.icon,
            activity_status=community_data.activity_status,
            tags=self.normalize_tags(community_data.tags),
            member_count_cache=1,
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
        try:
            # Flush inside a savepoint: the unique constraint decides whether
            # this join happens at all, and the counter must not be moved for a
            # membership the database is about to refuse. A refused insert then
            # rolls back only itself, so a duplicate join leaves everything else
            # in the transaction — and the caller's loaded objects — untouched.
            async with self.session.begin_nested():
                membership = CommunityMemberModel(community_id=community_id, user_id=user_id)
                self.session.add(membership)
                await self.session.flush()
        except IntegrityError as exc:
            # Two concurrent joins can both pass the is_member pre-check; the
            # unique constraint guards the data, so surface a clean conflict
            # instead of a 500.
            raise AlreadyMemberError("Already a member") from exc

        await self._bump_member_count_cache(community_id, 1)
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
        await self._bump_member_count_cache(community_id, -1)
        await self.session.commit()

    async def _bump_member_count_cache(self, community_id: UUID, amount: int) -> None:
        """Move the legacy cache column by ``amount``, in SQL.

        Read-modify-write in Python lost increments whenever two people joined
        at the same time: both read 7, both wrote 8. This cannot — but it is
        still only a cache. The answer served to clients comes from the
        membership rows themselves (``CommunityModel.member_count``), which is
        why a drift here is a tidiness problem and no longer a wrong number.
        """
        column = CommunityModel.__table__.c.member_count
        moved = column + amount
        # Clamped with CASE, not with a two-argument ``max``: that spelling is
        # SQLite-only — PostgreSQL reads ``max`` as the aggregate and rejects
        # the statement, which made every leave fail on the real database.
        await self.session.execute(
            update(CommunityModel)
            .where(CommunityModel.id == community_id)
            .values(member_count=case((moved < 0, 0), else_=moved))
        )

    async def member_count_drift(self, community_id: UUID | None = None) -> list[dict]:
        """Where the cached number disagrees with the memberships.

        Run it before and after changing what the API returns: it is the
        evidence for whether the switch moves any number a user can see.
        """
        live_count = (
            select(func.count(CommunityMemberModel.id))
            .where(CommunityMemberModel.community_id == CommunityModel.id)
            .correlate_except(CommunityMemberModel)
            .scalar_subquery()
        )
        cached = CommunityModel.__table__.c.member_count
        query = select(CommunityModel.id, CommunityModel.name, cached, live_count).where(
            cached != live_count
        )
        if community_id is not None:
            query = query.where(CommunityModel.id == community_id)
        rows = (await self.session.execute(query)).all()
        return [
            {"community_id": row[0], "name": row[1], "cached": row[2], "members": row[3]}
            for row in rows
        ]

    async def reconcile_member_counts(self, community_id: UUID | None = None) -> int:
        """Rewrite the cache from the memberships. Explicit, never on a read.

        A GET must not write: a listing that repaired the cache as a side effect
        would turn every page view into a write and hide the drift instead of
        reporting it.
        """
        drifted = await self.member_count_drift(community_id)
        for entry in drifted:
            await self.session.execute(
                update(CommunityModel)
                .where(CommunityModel.id == entry["community_id"])
                .values(member_count=entry["members"])
            )
        if drifted:
            await self.session.commit()
        return len(drifted)

    async def list_posts(self, community_id: UUID) -> list[CommunityPostModel]:
        result = await self.session.execute(
            select(CommunityPostModel)
            .where(CommunityPostModel.community_id == community_id)
            .order_by(CommunityPostModel.created_at.desc())
            .limit(MAX_COLLECTION_ROWS)
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
            post_type=post_data.post_type,
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
            .limit(MAX_COLLECTION_ROWS)
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
            .limit(MAX_COLLECTION_ROWS)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        enriched = []
        for post, first_name, last_name, nickname, lc, cc, my_like in rows:
            author = build_display_name(first_name=first_name, last_name=last_name, nickname=nickname)
            enriched.append({
                "id": str(post.id),
                "community_id": str(post.community_id),
                "user_id": str(post.user_id),
                "title": post.title,
                "content": post.content,
                "post_type": post.post_type,
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
            .limit(MAX_COLLECTION_ROWS)
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        enriched = []
        for comment, first_name, last_name, nickname in rows:
            author = build_display_name(first_name=first_name, last_name=last_name, nickname=nickname)
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
