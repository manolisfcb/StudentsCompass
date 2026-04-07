from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.userModel import User
from app.schemas.messageSchema import (
    ConversationReadReceipt,
    ConversationSummaryRead,
    DirectConversationCreate,
    MessageCreate,
    MessageRead,
)
from app.services.messageService import MessageService
from app.services.userService import current_active_user

router = APIRouter()


@router.post("/conversations/direct", response_model=ConversationSummaryRead, status_code=status.HTTP_201_CREATED)
async def create_direct_conversation(
    payload: DirectConversationCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    service = MessageService(session)

    if payload.friend_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot message yourself")

    friend = await service.get_user(payload.friend_id)
    if not friend:
        raise HTTPException(status_code=404, detail="User not found")

    if not await service.are_friends(current_user.id, payload.friend_id):
        raise HTTPException(status_code=403, detail="You can only start chats with friends")

    conversation = await service.create_or_get_direct_conversation(
        user_id=current_user.id,
        friend_id=payload.friend_id,
    )
    summary = await service.build_conversation_summary(
        conversation=conversation,
        current_user_id=current_user.id,
    )
    if not summary:
        raise HTTPException(status_code=500, detail="Conversation was created but could not be loaded")
    return summary


@router.get("/conversations", response_model=list[ConversationSummaryRead])
async def list_conversations(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    service = MessageService(session)
    return await service.list_conversations(current_user.id)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageRead])
async def list_messages(
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    service = MessageService(session)
    conversation = await service.get_conversation_for_user(conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return await service.list_messages(conversation_id=conversation_id, user_id=current_user.id)


@router.post("/conversations/{conversation_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def send_message(
    conversation_id: UUID,
    payload: MessageCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    service = MessageService(session)
    conversation = await service.get_conversation_for_user(conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return await service.send_message(
        conversation_id=conversation_id,
        sender_id=current_user.id,
        content=content,
    )


@router.post("/conversations/{conversation_id}/read", response_model=ConversationReadReceipt)
async def mark_conversation_read(
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    service = MessageService(session)
    conversation = await service.get_conversation_for_user(conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    marked_at = await service.mark_conversation_read(
        conversation_id=conversation_id,
        user_id=current_user.id,
    )
    return ConversationReadReceipt(conversation_id=conversation_id, marked_read_at=marked_at)
