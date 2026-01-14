from fastapi import FastAPI, File, UploadFile, Form, Depends
from app.db import create_db_and_tables, get_session
from app.models.postModel import PostModel
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "Hello World"}