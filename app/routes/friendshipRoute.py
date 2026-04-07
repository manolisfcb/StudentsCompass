from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.userModel import User
from app.schemas.friendshipSchema import (
    FriendRequestCreate,
    FriendRequestRead,
    FriendshipRead,
    FriendshipStatusRead,
)
from app.services.friendshipService import FriendshipService
from app.services.userService import current_active_user

router = APIRouter()


@router.post("/friends/requests", response_model=FriendRequestRead, status_code=status.HTTP_201_CREATED)
async def send_friend_request(
    payload: FriendRequestCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    service = FriendshipService(session)

    if payload.receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot send a friend request to yourself")

    receiver = await service.get_user(payload.receiver_id)
    if not receiver:
        raise HTTPException(status_code=404, detail="User not found")

    if await service.are_friends(current_user.id, payload.receiver_id):
        raise HTTPException(status_code=409, detail="You are already friends")

    active_request = await service.get_active_request_between(current_user.id, payload.receiver_id)
    if active_request:
        if active_request.sender_id == current_user.id:
            raise HTTPException(status_code=409, detail="Friend request already sent")
        raise HTTPException(status_code=409, detail="This user already sent you a friend request")

    request = await service.send_request(sender_id=current_user.id, receiver_id=payload.receiver_id)
    return FriendRequestRead(
        id=request.id,
        status=request.status,
        created_at=request.created_at,
        responded_at=request.responded_at,
        sender=service._build_user_summary(current_user),
        receiver=service._build_user_summary(receiver),
    )


@router.get("/friends/requests/incoming", response_model=list[FriendRequestRead])
async def list_incoming_friend_requests(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    service = FriendshipService(session)
    return await service.list_incoming_requests(current_user.id)


@router.get("/friends/requests/outgoing", response_model=list[FriendRequestRead])
async def list_outgoing_friend_requests(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    service = FriendshipService(session)
    return await service.list_outgoing_requests(current_user.id)


@router.post("/friends/requests/{request_id}/accept", response_model=FriendRequestRead)
async def accept_friend_request(
    request_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    service = FriendshipService(session)
    request = await service.get_request_for_receiver(request_id=request_id, receiver_id=current_user.id)
    if not request:
        raise HTTPException(status_code=404, detail="Friend request not found")
    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Friend request is no longer pending")

    sender = await service.get_user(request.sender_id)
    accepted = await service.accept_request(request)
    return FriendRequestRead(
        id=accepted.id,
        status=accepted.status,
        created_at=accepted.created_at,
        responded_at=accepted.responded_at,
        sender=service._build_user_summary(sender),
        receiver=service._build_user_summary(current_user),
    )


@router.post("/friends/requests/{request_id}/reject", response_model=FriendRequestRead)
async def reject_friend_request(
    request_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    service = FriendshipService(session)
    request = await service.get_request_for_receiver(request_id=request_id, receiver_id=current_user.id)
    if not request:
        raise HTTPException(status_code=404, detail="Friend request not found")
    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Friend request is no longer pending")

    sender = await service.get_user(request.sender_id)
    rejected = await service.reject_request(request)
    return FriendRequestRead(
        id=rejected.id,
        status=rejected.status,
        created_at=rejected.created_at,
        responded_at=rejected.responded_at,
        sender=service._build_user_summary(sender),
        receiver=service._build_user_summary(current_user),
    )


@router.post("/friends/requests/{request_id}/cancel", response_model=FriendRequestRead)
async def cancel_friend_request(
    request_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    service = FriendshipService(session)
    request = await service.get_request_for_sender(request_id=request_id, sender_id=current_user.id)
    if not request:
        raise HTTPException(status_code=404, detail="Friend request not found")
    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Friend request is no longer pending")

    receiver = await service.get_user(request.receiver_id)
    cancelled = await service.cancel_request(request)
    return FriendRequestRead(
        id=cancelled.id,
        status=cancelled.status,
        created_at=cancelled.created_at,
        responded_at=cancelled.responded_at,
        sender=service._build_user_summary(current_user),
        receiver=service._build_user_summary(receiver),
    )


@router.get("/friends", response_model=list[FriendshipRead])
async def list_friends(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    service = FriendshipService(session)
    return await service.list_friends(current_user.id)


@router.delete("/friends/{friend_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unfriend_user(
    friend_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    service = FriendshipService(session)
    if not await service.are_friends(current_user.id, friend_id):
        raise HTTPException(status_code=404, detail="Friendship not found")
    await service.remove_friendship(user_id=current_user.id, friend_id=friend_id)


@router.get("/friends/status", response_model=list[FriendshipStatusRead])
async def get_friendship_statuses(
    user_ids: str = Query(default="", description="Comma-separated list of user ids"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    parsed_user_ids: list[UUID] = []
    for raw_value in user_ids.split(","):
        value = raw_value.strip()
        if not value:
            continue
        try:
            parsed_user_ids.append(UUID(value))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid user id: {value}") from exc

    service = FriendshipService(session)
    return await service.get_friendship_statuses(
        current_user_id=current_user.id,
        target_user_ids=parsed_user_ids,
    )
