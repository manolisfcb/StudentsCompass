from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db import get_session
from app.models.userModel import User
from app.services.userService import current_active_user
from app.services.communityService import CommunityService
from app.schemas.communitySchema import (
    CommunityCreate,
    CommunityRead,
    CommunityMemberRead,
    CommunityPostCreate,
    CommunityPostRead,
    CommunityPostEnriched,
    CommunityPostCommentCreate,
    CommunityPostCommentRead,
    CommunityPostCommentEnriched,
)

router = APIRouter()


# ── Single community detail ──────────────────────────────────────
@router.get("/communities/{community_id}", response_model=CommunityRead)
async def get_community(
    community_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = CommunityService(session)
    community = await service.get_community_by_id(community_id)
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    return community


# ── Membership check ─────────────────────────────────────────────
@router.get("/communities/{community_id}/membership")
async def check_membership(
    community_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = CommunityService(session)
    is_member = await service.is_member(community_id, user.id)
    return {"is_member": is_member}


@router.post("/communities", response_model=CommunityRead)
async def create_community(
    community: CommunityCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = CommunityService(session)
    existing = await service.get_community_by_name(community.name)
    if existing:
        raise HTTPException(status_code=409, detail="Community name already exists")
    return await service.create_community(community, user.id)


@router.get("/communities", response_model=list[CommunityRead])
async def list_communities(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = CommunityService(session)
    return await service.list_communities()


@router.post("/communities/{community_id}/join", response_model=CommunityMemberRead)
async def join_community(
    community_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = CommunityService(session)
    community = await service.get_community_by_id(community_id)
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    if await service.is_member(community_id, user.id):
        raise HTTPException(status_code=409, detail="Already a member")
    return await service.join_community(community_id, user.id)


@router.delete("/communities/{community_id}/leave")
async def leave_community(
    community_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = CommunityService(session)
    community = await service.get_community_by_id(community_id)
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    if not await service.is_member(community_id, user.id):
        raise HTTPException(status_code=400, detail="Not a member")
    if community.created_by == user.id:
        raise HTTPException(status_code=403, detail="El creador no puede abandonar la comunidad")
    await service.leave_community(community_id, user.id)
    return {"detail": "Left community"}@router.get("/communities/{community_id}/posts", response_model=list[CommunityPostRead])
async def list_community_posts(
    community_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = CommunityService(session)
    community = await service.get_community_by_id(community_id)
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    if not await service.is_member(community_id, user.id):
        raise HTTPException(status_code=403, detail="You must join the community to view posts")
    return await service.list_posts(community_id)


@router.post("/communities/{community_id}/posts", response_model=CommunityPostRead)
async def create_community_post(
    community_id: UUID,
    post: CommunityPostCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = CommunityService(session)
    community = await service.get_community_by_id(community_id)
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    if not await service.is_member(community_id, user.id):
        raise HTTPException(status_code=403, detail="You must join the community to post")
    return await service.create_post(community_id, user.id, post)


@router.post("/community-posts/{post_id}/likes")
async def like_post(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = CommunityService(session)
    post = await service.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if not await service.is_member(post.community_id, user.id):
        raise HTTPException(status_code=403, detail="You must join the community to like posts")
    if await service.get_like(post_id, user.id):
        raise HTTPException(status_code=409, detail="Already liked")
    return await service.like_post(post_id, user.id)


@router.delete("/community-posts/{post_id}/likes")
async def unlike_post(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = CommunityService(session)
    post = await service.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if not await service.is_member(post.community_id, user.id):
        raise HTTPException(status_code=403, detail="You must join the community to unlike posts")
    if not await service.get_like(post_id, user.id):
        raise HTTPException(status_code=404, detail="Like not found")
    await service.unlike_post(post_id, user.id)
    return {"detail": "Like removed"}


@router.post("/community-posts/{post_id}/comments", response_model=CommunityPostCommentRead)
async def create_comment(
    post_id: UUID,
    comment: CommunityPostCommentCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = CommunityService(session)
    post = await service.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if not await service.is_member(post.community_id, user.id):
        raise HTTPException(status_code=403, detail="You must join the community to comment")
    return await service.add_comment(post_id, user.id, comment)


@router.get("/community-posts/{post_id}/comments", response_model=list[CommunityPostCommentRead])
async def list_comments(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = CommunityService(session)
    post = await service.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if not await service.is_member(post.community_id, user.id):
        raise HTTPException(status_code=403, detail="You must join the community to view comments")
    return await service.list_comments(post_id)


# ── Enriched endpoints (author info + counts) ────────────────────

@router.get("/communities/{community_id}/posts/enriched")
async def list_community_posts_enriched(
    community_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = CommunityService(session)
    community = await service.get_community_by_id(community_id)
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    if not await service.is_member(community_id, user.id):
        raise HTTPException(status_code=403, detail="You must join the community to view posts")
    return await service.list_posts_enriched(community_id, user.id)


@router.get("/community-posts/{post_id}/comments/enriched")
async def list_comments_enriched(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = CommunityService(session)
    post = await service.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if not await service.is_member(post.community_id, user.id):
        raise HTTPException(status_code=403, detail="You must join the community to view comments")
    return await service.list_comments_enriched(post_id)
