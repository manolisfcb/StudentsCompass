from app.schemas.postSchema import PostCreate, PostRead
from fastapi import APIRouter, Depends, HTTPException
from app.services.postService import PostService
from app.db import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID


router = APIRouter()

@router.post("/posts", response_model=PostCreate)
async def create_post(post: PostCreate, session:AsyncSession = Depends(get_session)):
    post_service = PostService(session)
    return await post_service.create_post(post) if post else HTTPException(status_code=400, detail="Invalid post data")
    
    
@router.get("/posts/{post_id}", response_model=PostRead)
async def get_post(post_id: UUID, session:AsyncSession = Depends(get_session)):
    post_service = PostService(session)
    post = await post_service.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@router.get("/posts", response_model=list[PostRead])
async def get_all_posts(session:AsyncSession = Depends(get_session)):
    post_service = PostService(session)
    return await post_service.get_all_posts()