from app.core.pagination import (
    MAX_COLLECTION_ROWS,
    InvalidCursor,
    clamp_page_size,
    encode_cursor,
    fetch_probe_limit,
    keyset_before,
    split_probe,
)
from app.models.postModel import PostModel
from sqlalchemy import select
from app.schemas.postSchema import PostCreate, PostPageRead, PostRead
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID


class InvalidPostCursor(InvalidCursor):
    """The feed cursor did not come from :meth:`PostService.encode_post_cursor`."""


class PostService:
    #: Posts returned when the caller does not say. One screenful of feed.
    DEFAULT_POST_PAGE_SIZE = 20
    #: The most any single feed request may return, whatever it asks for.
    MAX_POST_PAGE_SIZE = 100

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
        """Legacy shape: a bare list, newest first, now capped at one window.

        This was the one listing in F-22 not scoped to a user — the global feed
        — so its cost grew with the whole platform's activity and every reader
        paid it. The shape is unchanged while callers move to
        :meth:`list_post_page`; what changed is that it is finite.

        Truncating at the **newest** end is the correct direction for a feed: a
        client that renders what it is given shows the current conversation.
        Keeping the oldest rows instead would silently pin the feed to the day
        the platform launched.
        """
        result = await self.session.execute(
            select(PostModel)
            .order_by(PostModel.created_at.desc(), PostModel.id.desc())
            .limit(MAX_COLLECTION_ROWS)
        )
        posts = result.scalars().all()
        return [post for post in posts]

    @staticmethod
    def encode_post_cursor(post: PostModel) -> str:
        """An opaque cursor addressing one post by ``(created_at, id)``.

        The same contract TASK-024 established for messages, not a second one:
        the id is in the cursor because posts created in the same instant — a
        seeded batch, two people posting at once — would otherwise leave the
        page boundary ambiguous and drop or repeat a post.
        """
        return encode_cursor(post.created_at, post.id)

    async def list_post_page(
        self,
        *,
        before: str | None = None,
        limit: int | None = None,
    ) -> PostPageRead:
        """One bounded page of the feed, newest first.

        Newest first and *not* reversed, unlike the message page: a feed is read
        from the top, so the natural order of the query is already the order of
        the payload. Walking ``next_cursor`` moves backwards in time.
        """
        page_size = clamp_page_size(
            limit,
            default=self.DEFAULT_POST_PAGE_SIZE,
            maximum=self.MAX_POST_PAGE_SIZE,
        )

        conditions = []
        if before:
            try:
                conditions.append(keyset_before(PostModel.created_at, PostModel.id, before))
            except InvalidCursor as exc:
                raise InvalidPostCursor(before) from exc

        result = await self.session.execute(
            select(PostModel)
            .where(*conditions)
            .order_by(PostModel.created_at.desc(), PostModel.id.desc())
            # One extra row: whether a further page exists is a fact about the
            # data, not something to infer from a full page.
            .limit(fetch_probe_limit(page_size))
        )
        rows, has_more = split_probe(list(result.scalars().all()), page_size)

        return PostPageRead(
            items=[PostRead.model_validate(post) for post in rows],
            # The last item on this page is where the next one starts.
            next_cursor=self.encode_post_cursor(rows[-1]) if rows and has_more else None,
            has_more=has_more,
            limit=page_size,
        )

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
