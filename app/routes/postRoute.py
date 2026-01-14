from app.schemas.postSchema import PostCreate
from fastapi import APIRouter, Depends, HTTPException
from app.services.postService import PostService
from app.db import get_session
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter()

@router.post("/posts", response_model=PostCreate)
async def create_post(post: PostCreate, session:AsyncSession = Depends(get_session)):
    post_service = PostService(session)
    return await post_service.create_post(post) if post else HTTPException(status_code=400, detail="Invalid post data")
    
    