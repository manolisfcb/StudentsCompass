import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import MAX_POST_UPLOAD_BYTES, POST_MEDIA_CONTENT_TYPES
from app.core.uploads import ensure_allowed_upload, read_upload_within_limit
from app.db import get_session
from app.models.userModel import User
from app.schemas.postSchema import PostCreate, PostRead
from app.services.accounts.userService import current_active_user
from app.services.community.postService import PostService
from app.services.storage.mediaStorageService import get_media_storage_service

LOGGER = logging.getLogger(__name__)

router = APIRouter()


@router.post("/posts", response_model=PostCreate)
async def create_post(
    post: PostCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    post_service = PostService(session)
    return await post_service.create_post(post, user_id=user.id)


@router.get("/posts/{post_id}", response_model=PostRead)
async def get_post(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    post_service = PostService(session)
    post = await post_service.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@router.get("/posts", response_model=list[PostRead])
async def get_all_posts(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    post_service = PostService(session)
    return await post_service.get_all_posts()


@router.post("/upload_post")
async def upload_file(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    caption: str = Form(...),
    user: User = Depends(current_active_user),
):

    # Nothing was bounded here before: the parser had already spooled the body to
    # disk and the bytes went straight to a paid provider. The raw body is capped
    # by RequestBodySizeLimitMiddleware; this reads the part incrementally and
    # checks the payload really is the media type it claims to be, so neither
    # disk nor the provider is spent on something this endpoint does not serve.
    file_bytes = await read_upload_within_limit(file, MAX_POST_UPLOAD_BYTES)
    content_type = ensure_allowed_upload(
        data=file_bytes,
        content_type=file.content_type,
        allowed_content_types=POST_MEDIA_CONTENT_TYPES,
        what="media",
    )

    try:
        post_data = await get_media_storage_service().upload_media(
            file=file,
            file_name=file.filename,
            folder="posts/",
            file_bytes=file_bytes,
            content_type=content_type,
        )
    except Exception:
        LOGGER.exception("Post media upload failed for user %s", user.id)
        raise HTTPException(status_code=500, detail="File upload failed. Please try again.")

    post = PostCreate(
        caption=caption,
        url=post_data.url,
        file_type=post_data.file_type,
        file_name=post_data.name,
    )
    post_service = PostService(session)
    return await post_service.create_post(post, user_id=user.id)


@router.delete("/delete_post/{post_id}")
async def delete_post(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    post_service = PostService(session)
    deleted = await post_service.delete_post(post_id, user_id=user.id)
    if not deleted:
        # Same response for "not yours" and "does not exist": the endpoint must
        # not confirm that another user's post ID is real.
        raise HTTPException(status_code=404, detail="Post not found")
    return {"detail": "Post deleted successfully"}
