from app.schemas.postSchema import PostCreate, PostRead
from fastapi import APIRouter, Depends, HTTPException
from app.services.postService import PostService
from app.db import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from fastapi import UploadFile, Form, File
from app.services.images import upload_media

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


@router.post("/upload_post")
async def upload_file(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    caption: str = Form(...)):

    try:
        post_data = upload_media(
            file=file,
            file_name=file.filename,
            folder="posts/"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")
    
    post = PostCreate(
        caption=caption,
        url=post_data.url,
        file_type=post_data.file_type,
        file_name=post_data.name 
    )
    post_service = PostService(session)
    return await post_service.create_post(post) if post else HTTPException(status_code=400, detail="Invalid post data")


@router.delete("/delete_post/{post_id}")
async def delete_post(post_id: UUID, session:AsyncSession = Depends(get_session)):
    post_service = PostService(session)
    await post_service.delete_post(post_id)
    return {"detail": "Post deleted successfully"}
