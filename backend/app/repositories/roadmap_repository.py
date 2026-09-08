from __future__ import annotations

from typing import Iterable
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.roadmapModel import (
    RoadmapModel,
    RoadmapStageModel,
    StageProjectModel,
    StageTaskModel,
    TaskProgressStatus,
    UserProjectSubmissionModel,
    UserRoadmapModel,
    UserStageProgressModel,
    UserTaskProgressModel,
)


class RoadmapRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_public_roadmaps(
        self,
        search: str | None = None,
        sort: str = "most_saved",
    ) -> list[tuple[RoadmapModel, int]]:
        popularity_subq = (
            select(
                UserRoadmapModel.roadmap_id,
                func.count(UserRoadmapModel.id).label("popularity"),
            )
            .group_by(UserRoadmapModel.roadmap_id)
            .subquery()
        )

        popularity_col = func.coalesce(popularity_subq.c.popularity, 0).label("popularity")

        stmt = (
            select(RoadmapModel, popularity_col)
            .outerjoin(popularity_subq, popularity_subq.c.roadmap_id == RoadmapModel.id)
            .where(RoadmapModel.is_public.is_(True))
        )

        if search and search.strip():
            q = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    RoadmapModel.title.ilike(q),
                    RoadmapModel.description.ilike(q),
                    RoadmapModel.role_target.ilike(q),
                )
            )

        if sort == "newest":
            stmt = stmt.order_by(RoadmapModel.created_at.desc())
        else:
            stmt = stmt.order_by(popularity_col.desc(), RoadmapModel.created_at.desc())

        result = await self.session.execute(stmt)
        return [(item[0], int(item[1] or 0)) for item in result.all()]

    async def get_roadmap_by_slug(self, slug: str, public_only: bool = False) -> RoadmapModel | None:
        stmt = (
            select(RoadmapModel)
            .where(RoadmapModel.slug == slug)
            .options(
                selectinload(RoadmapModel.stages).selectinload(RoadmapStageModel.tasks),
                selectinload(RoadmapModel.stages).selectinload(RoadmapStageModel.projects),
            )
        )

        if public_only:
            stmt = stmt.where(RoadmapModel.is_public.is_(True))

        result = await self.session.execute(stmt)
        roadmap = result.scalar_one_or_none()
        if roadmap:
            roadmap.stages.sort(key=lambda stage: stage.order_index)
            for stage in roadmap.stages:
                stage.tasks.sort(key=lambda task: task.order_index)
        return roadmap

    async def get_roadmap_by_id(self, roadmap_id: UUID) -> RoadmapModel | None:
        result = await self.session.execute(select(RoadmapModel).where(RoadmapModel.id == roadmap_id))
        return result.scalar_one_or_none()

    async def get_saved_roadmap_ids(self, user_id: UUID, roadmap_ids: Iterable[UUID] | None = None) -> set[UUID]:
        stmt = select(UserRoadmapModel.roadmap_id).where(UserRoadmapModel.user_id == user_id)
        if roadmap_ids is not None:
            ids = list(roadmap_ids)
            if not ids:
                return set()
            stmt = stmt.where(UserRoadmapModel.roadmap_id.in_(ids))

        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def save_roadmap(self, user_id: UUID, roadmap_id: UUID) -> bool:
        exists = await self.session.execute(
            select(UserRoadmapModel.id).where(
                UserRoadmapModel.user_id == user_id,
                UserRoadmapModel.roadmap_id == roadmap_id,
            )
        )
        if exists.scalar_one_or_none():
            return False

        self.session.add(UserRoadmapModel(user_id=user_id, roadmap_id=roadmap_id))
        return True

    async def unsave_roadmap(self, user_id: UUID, roadmap_id: UUID) -> bool:
        result = await self.session.execute(
            select(UserRoadmapModel).where(
                UserRoadmapModel.user_id == user_id,
                UserRoadmapModel.roadmap_id == roadmap_id,
            )
        )
        entity = result.scalar_one_or_none()
        if not entity:
            return False

        await self.session.delete(entity)
        return True

    async def list_saved_roadmaps(self, user_id: UUID) -> list[tuple[UserRoadmapModel, RoadmapModel, int]]:
        popularity_subq = (
            select(
                UserRoadmapModel.roadmap_id,
                func.count(UserRoadmapModel.id).label("popularity"),
            )
            .group_by(UserRoadmapModel.roadmap_id)
            .subquery()
        )

        stmt = (
            select(
                UserRoadmapModel,
                RoadmapModel,
                func.coalesce(popularity_subq.c.popularity, 0).label("popularity"),
            )
            .join(RoadmapModel, RoadmapModel.id == UserRoadmapModel.roadmap_id)
            .outerjoin(popularity_subq, popularity_subq.c.roadmap_id == RoadmapModel.id)
            .where(UserRoadmapModel.user_id == user_id)
            .order_by(UserRoadmapModel.saved_at.desc())
        )

        result = await self.session.execute(stmt)
        return [(row[0], row[1], int(row[2] or 0)) for row in result.all()]

    async def get_popularity(self, roadmap_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count(UserRoadmapModel.id)).where(UserRoadmapModel.roadmap_id == roadmap_id)
        )
        return int(result.scalar_one() or 0)

    async def get_total_task_counts_for_roadmaps(self, roadmap_ids: list[UUID]) -> dict[UUID, int]:
        if not roadmap_ids:
            return {}

        stmt = (
            select(RoadmapStageModel.roadmap_id, func.count(StageTaskModel.id))
            .join(StageTaskModel, StageTaskModel.stage_id == RoadmapStageModel.id)
            .where(RoadmapStageModel.roadmap_id.in_(roadmap_ids))
            .group_by(RoadmapStageModel.roadmap_id)
        )
        result = await self.session.execute(stmt)
        return {row[0]: int(row[1]) for row in result.all()}

    async def get_completed_task_counts_for_roadmaps(self, user_id: UUID, roadmap_ids: list[UUID]) -> dict[UUID, int]:
        if not roadmap_ids:
            return {}

        stmt = (
            select(RoadmapStageModel.roadmap_id, func.count(UserTaskProgressModel.id))
            .join(StageTaskModel, StageTaskModel.stage_id == RoadmapStageModel.id)
            .join(UserTaskProgressModel, UserTaskProgressModel.task_id == StageTaskModel.id)
            .where(
                RoadmapStageModel.roadmap_id.in_(roadmap_ids),
                UserTaskProgressModel.user_id == user_id,
                UserTaskProgressModel.status == TaskProgressStatus.COMPLETED,
            )
            .group_by(RoadmapStageModel.roadmap_id)
        )
        result = await self.session.execute(stmt)
        return {row[0]: int(row[1]) for row in result.all()}

    async def get_user_task_progress_for_roadmap(self, user_id: UUID, roadmap_id: UUID) -> dict[UUID, TaskProgressStatus]:
        stmt = (
            select(UserTaskProgressModel.task_id, UserTaskProgressModel.status)
            .join(StageTaskModel, StageTaskModel.id == UserTaskProgressModel.task_id)
            .join(RoadmapStageModel, RoadmapStageModel.id == StageTaskModel.stage_id)
            .where(
                UserTaskProgressModel.user_id == user_id,
                RoadmapStageModel.roadmap_id == roadmap_id,
            )
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def get_stage_progress_map(self, user_id: UUID, stage_ids: list[UUID]) -> dict[UUID, int]:
        if not stage_ids:
            return {}

        result = await self.session.execute(
            select(UserStageProgressModel.stage_id, UserStageProgressModel.progress_percent).where(
                UserStageProgressModel.user_id == user_id,
                UserStageProgressModel.stage_id.in_(stage_ids),
            )
        )
        return {row[0]: int(row[1]) for row in result.all()}

    async def get_task_by_id(self, task_id: UUID) -> StageTaskModel | None:
        result = await self.session.execute(
            select(StageTaskModel)
            .where(StageTaskModel.id == task_id)
            .options(selectinload(StageTaskModel.stage))
        )
        return result.scalar_one_or_none()

    async def get_task_progress_record(self, user_id: UUID, task_id: UUID) -> UserTaskProgressModel | None:
        result = await self.session.execute(
            select(UserTaskProgressModel).where(
                UserTaskProgressModel.user_id == user_id,
                UserTaskProgressModel.task_id == task_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_stage_progress_record(self, user_id: UUID, stage_id: UUID) -> UserStageProgressModel | None:
        result = await self.session.execute(
            select(UserStageProgressModel).where(
                UserStageProgressModel.user_id == user_id,
                UserStageProgressModel.stage_id == stage_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_total_tasks_for_stage(self, stage_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count(StageTaskModel.id)).where(StageTaskModel.stage_id == stage_id)
        )
        return int(result.scalar_one() or 0)

    async def get_completed_tasks_for_stage(self, user_id: UUID, stage_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count(UserTaskProgressModel.id))
            .join(StageTaskModel, StageTaskModel.id == UserTaskProgressModel.task_id)
            .where(
                StageTaskModel.stage_id == stage_id,
                UserTaskProgressModel.user_id == user_id,
                UserTaskProgressModel.status == TaskProgressStatus.COMPLETED,
            )
        )
        return int(result.scalar_one() or 0)

    async def get_total_tasks_for_roadmap(self, roadmap_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count(StageTaskModel.id))
            .join(RoadmapStageModel, RoadmapStageModel.id == StageTaskModel.stage_id)
            .where(RoadmapStageModel.roadmap_id == roadmap_id)
        )
        return int(result.scalar_one() or 0)

    async def get_completed_tasks_for_roadmap(self, user_id: UUID, roadmap_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count(UserTaskProgressModel.id))
            .join(StageTaskModel, StageTaskModel.id == UserTaskProgressModel.task_id)
            .join(RoadmapStageModel, RoadmapStageModel.id == StageTaskModel.stage_id)
            .where(
                RoadmapStageModel.roadmap_id == roadmap_id,
                UserTaskProgressModel.user_id == user_id,
                UserTaskProgressModel.status == TaskProgressStatus.COMPLETED,
            )
        )
        return int(result.scalar_one() or 0)

    async def get_project_by_id(self, project_id: UUID) -> StageProjectModel | None:
        result = await self.session.execute(
            select(StageProjectModel)
            .where(StageProjectModel.id == project_id)
            .options(selectinload(StageProjectModel.stage))
        )
        return result.scalar_one_or_none()

    async def get_submission(self, user_id: UUID, project_id: UUID) -> UserProjectSubmissionModel | None:
        result = await self.session.execute(
            select(UserProjectSubmissionModel).where(
                UserProjectSubmissionModel.user_id == user_id,
                UserProjectSubmissionModel.project_id == project_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_submissions_for_roadmap(self, user_id: UUID, roadmap_id: UUID) -> dict[UUID, UserProjectSubmissionModel]:
        stmt = (
            select(UserProjectSubmissionModel)
            .join(StageProjectModel, StageProjectModel.id == UserProjectSubmissionModel.project_id)
            .join(RoadmapStageModel, RoadmapStageModel.id == StageProjectModel.stage_id)
            .where(
                UserProjectSubmissionModel.user_id == user_id,
                RoadmapStageModel.roadmap_id == roadmap_id,
            )
        )
        result = await self.session.execute(stmt)
        submissions = result.scalars().all()
        return {submission.project_id: submission for submission in submissions}

    async def user_saved_roadmap(self, user_id: UUID, roadmap_id: UUID) -> bool:
        result = await self.session.execute(
            select(UserRoadmapModel.id).where(
                UserRoadmapModel.user_id == user_id,
                UserRoadmapModel.roadmap_id == roadmap_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    def add(self, entity) -> None:
        self.session.add(entity)
