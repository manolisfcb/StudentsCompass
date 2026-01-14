from app.schemas.postSchema import PostCreate
from fastapi import APIRouter, Depends, HTTPException


router = APIRouter()

@router.post("/posts")
async def create_post(post: PostCreate):
    return {"message": "Post created successfully"}
    