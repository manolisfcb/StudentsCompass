from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.friendshipModel import FriendRequestModel, FriendshipModel
from app.models.userModel import User
from app.schemas.friendshipSchema import (
    FriendRequestRead,
    FriendshipRead,
    FriendshipStatusRead,
    FriendUserSummary,
)


class FriendshipService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user(self, user_id: UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def are_friends(self, user_id: UUID, friend_id: UUID) -> bool:
        result = await self.session.execute(
            select(FriendshipModel.id).where(
                FriendshipModel.user_id == user_id,
                FriendshipModel.friend_id == friend_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_active_request_between(self, first_user_id: UUID, second_user_id: UUID) -> FriendRequestModel | None:
        result = await self.session.execute(
            select(FriendRequestModel).where(
                FriendRequestModel.status == "pending",
                or_(
                    and_(
                        FriendRequestModel.sender_id == first_user_id,
                        FriendRequestModel.receiver_id == second_user_id,
                    ),
                    and_(
                        FriendRequestModel.sender_id == second_user_id,
                        FriendRequestModel.receiver_id == first_user_id,
                    ),
                ),
            ).order_by(FriendRequestModel.created_at.desc())
        )
        return result.scalars().first()

    async def send_request(self, *, sender_id: UUID, receiver_id: UUID) -> FriendRequestModel:
        request = FriendRequestModel(
            sender_id=sender_id,
            receiver_id=receiver_id,
            status="pending",
        )
        self.session.add(request)
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def get_request_for_receiver(self, *, request_id: UUID, receiver_id: UUID) -> FriendRequestModel | None:
        result = await self.session.execute(
            select(FriendRequestModel).where(
                FriendRequestModel.id == request_id,
                FriendRequestModel.receiver_id == receiver_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_request_for_sender(self, *, request_id: UUID, sender_id: UUID) -> FriendRequestModel | None:
        result = await self.session.execute(
            select(FriendRequestModel).where(
                FriendRequestModel.id == request_id,
                FriendRequestModel.sender_id == sender_id,
            )
        )
        return result.scalar_one_or_none()

    async def accept_request(self, request: FriendRequestModel) -> FriendRequestModel:
        request.status = "accepted"
        request.responded_at = datetime.utcnow()
        self.session.add(
            FriendshipModel(user_id=request.sender_id, friend_id=request.receiver_id)
        )
        self.session.add(
            FriendshipModel(user_id=request.receiver_id, friend_id=request.sender_id)
        )
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def reject_request(self, request: FriendRequestModel) -> FriendRequestModel:
        request.status = "rejected"
        request.responded_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def cancel_request(self, request: FriendRequestModel) -> FriendRequestModel:
        request.status = "cancelled"
        request.responded_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def remove_friendship(self, *, user_id: UUID, friend_id: UUID) -> None:
        result = await self.session.execute(
            select(FriendshipModel).where(
                or_(
                    and_(
                        FriendshipModel.user_id == user_id,
                        FriendshipModel.friend_id == friend_id,
                    ),
                    and_(
                        FriendshipModel.user_id == friend_id,
                        FriendshipModel.friend_id == user_id,
                    ),
                )
            )
        )
        rows = result.scalars().all()
        for row in rows:
            await self.session.delete(row)
        await self.session.commit()

    async def list_incoming_requests(self, user_id: UUID) -> list[FriendRequestRead]:
        result = await self.session.execute(
            select(FriendRequestModel)
            .where(
                FriendRequestModel.receiver_id == user_id,
                FriendRequestModel.status == "pending",
            )
            .order_by(FriendRequestModel.created_at.desc())
        )
        requests = result.scalars().all()
        senders = await self._get_users_by_ids([request.sender_id for request in requests])
        return [
            self._serialize_request(
                request=request,
                sender=senders.get(request.sender_id),
                receiver=None,
            )
            for request in requests
        ]

    async def list_outgoing_requests(self, user_id: UUID) -> list[FriendRequestRead]:
        result = await self.session.execute(
            select(FriendRequestModel)
            .where(
                FriendRequestModel.sender_id == user_id,
                FriendRequestModel.status == "pending",
            )
            .order_by(FriendRequestModel.created_at.desc())
        )
        requests = result.scalars().all()
        receivers = await self._get_users_by_ids([request.receiver_id for request in requests])
        return [
            self._serialize_request(
                request=request,
                sender=None,
                receiver=receivers.get(request.receiver_id),
            )
            for request in requests
        ]

    async def list_friends(self, user_id: UUID) -> list[FriendshipRead]:
        result = await self.session.execute(
            select(FriendshipModel)
            .where(FriendshipModel.user_id == user_id)
            .order_by(FriendshipModel.created_at.desc())
        )
        friendships = result.scalars().all()
        friends = await self._get_users_by_ids([friendship.friend_id for friendship in friendships])
        return [
            FriendshipRead(
                friend=self._build_user_summary(friends[friendship.friend_id]),
                created_at=friendship.created_at,
            )
            for friendship in friendships
            if friendship.friend_id in friends
        ]

    async def get_friendship_statuses(
        self,
        *,
        current_user_id: UUID,
        target_user_ids: list[UUID],
    ) -> list[FriendshipStatusRead]:
        if not target_user_ids:
            return []

        unique_target_ids = list(dict.fromkeys(target_user_ids))

        friendship_result = await self.session.execute(
            select(FriendshipModel.friend_id)
            .where(
                FriendshipModel.user_id == current_user_id,
                FriendshipModel.friend_id.in_(unique_target_ids),
            )
        )
        friend_ids = set(friendship_result.scalars().all())

        request_result = await self.session.execute(
            select(FriendRequestModel)
            .where(
                FriendRequestModel.status == "pending",
                or_(
                    and_(
                        FriendRequestModel.sender_id == current_user_id,
                        FriendRequestModel.receiver_id.in_(unique_target_ids),
                    ),
                    and_(
                        FriendRequestModel.receiver_id == current_user_id,
                        FriendRequestModel.sender_id.in_(unique_target_ids),
                    ),
                ),
            )
            .order_by(FriendRequestModel.created_at.desc())
        )
        pending_requests = request_result.scalars().all()

        outgoing_map: dict[UUID, UUID] = {}
        incoming_map: dict[UUID, UUID] = {}
        for request in pending_requests:
            if request.sender_id == current_user_id:
                outgoing_map.setdefault(request.receiver_id, request.id)
            elif request.receiver_id == current_user_id:
                incoming_map.setdefault(request.sender_id, request.id)

        statuses: list[FriendshipStatusRead] = []
        for target_user_id in unique_target_ids:
            if target_user_id == current_user_id:
                statuses.append(FriendshipStatusRead(user_id=target_user_id, status="self"))
            elif target_user_id in friend_ids:
                statuses.append(FriendshipStatusRead(user_id=target_user_id, status="friends"))
            elif target_user_id in incoming_map:
                statuses.append(
                    FriendshipStatusRead(
                        user_id=target_user_id,
                        status="incoming_request",
                        request_id=incoming_map[target_user_id],
                    )
                )
            elif target_user_id in outgoing_map:
                statuses.append(
                    FriendshipStatusRead(
                        user_id=target_user_id,
                        status="outgoing_request",
                        request_id=outgoing_map[target_user_id],
                    )
                )
            else:
                statuses.append(FriendshipStatusRead(user_id=target_user_id, status="none"))
        return statuses

    def _serialize_request(
        self,
        *,
        request: FriendRequestModel,
        sender: User | None,
        receiver: User | None,
    ) -> FriendRequestRead:
        sender_summary = self._build_user_summary(sender) if sender else FriendUserSummary(
            id=request.sender_id,
            display_name="You",
        )
        receiver_summary = self._build_user_summary(receiver) if receiver else FriendUserSummary(
            id=request.receiver_id,
            display_name="You",
        )
        return FriendRequestRead(
            id=request.id,
            status=request.status,
            created_at=request.created_at,
            responded_at=request.responded_at,
            sender=sender_summary,
            receiver=receiver_summary,
        )

    async def _get_users_by_ids(self, user_ids: list[UUID]) -> dict[UUID, User]:
        users: dict[UUID, User] = {}
        for user_id in dict.fromkeys(user_ids):
            user = await self.get_user(user_id)
            if user:
                users[user.id] = user
        return users

    def _build_user_summary(self, user: User) -> FriendUserSummary:
        display_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
        return FriendUserSummary(
            id=user.id,
            display_name=display_name or user.nickname or user.email or "Student",
            nickname=user.nickname,
            first_name=user.first_name,
            last_name=user.last_name,
        )
