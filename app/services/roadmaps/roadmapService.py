from __future__ import annotations

from collections import OrderedDict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.roadmapModel import (
    ProjectSubmissionStatus,
    TaskProgressStatus,
    UserProjectSubmissionModel,
    UserStageProgressModel,
    UserTaskProgressModel,
)
from app.repositories.roadmap_repository import RoadmapRepository
from app.schemas.roadmapSchema import (
    ProjectSubmissionRequest,
    ProjectSubmissionRead,
    RoadmapDetailRead,
    RoadmapListItemRead,
    SaveRoadmapResponse,
    SavedRoadmapRead,
    StageDetailRead,
    StageProjectRead,
    StageTaskRead,
    TaskProgressUpdateResponse,
)


class RoadmapService:
    TASK_TYPE_ORDER = ["learn", "watch", "read", "practice", "build"]

    def __init__(self, session: AsyncSession):
        self.repo = RoadmapRepository(session)

    @staticmethod
    def _percent(completed: int, total: int) -> int:
        if total <= 0:
            return 0
        return round((completed / total) * 100)

    async def list_public_roadmaps(
        self,
        user_id: UUID,
        search: str | None = None,
        sort: str = "most_saved",
    ) -> list[RoadmapListItemRead]:
        items = await self.repo.list_public_roadmaps(search=search, sort=sort)
        roadmap_ids = [roadmap.id for roadmap, _ in items]

        total_map = await self.repo.get_total_task_counts_for_roadmaps(roadmap_ids)
        completed_map = await self.repo.get_completed_task_counts_for_roadmaps(user_id=user_id, roadmap_ids=roadmap_ids)
        saved_ids = await self.repo.get_saved_roadmap_ids(user_id=user_id, roadmap_ids=roadmap_ids)

        payload: list[RoadmapListItemRead] = []
        for roadmap, popularity in items:
            total_tasks = total_map.get(roadmap.id, 0)
            completed_tasks = completed_map.get(roadmap.id, 0)
            payload.append(
                RoadmapListItemRead(
                    id=roadmap.id,
                    slug=roadmap.slug,
                    title=roadmap.title,
                    description=roadmap.description,
                    role_target=roadmap.role_target,
                    difficulty=roadmap.difficulty,
                    duration_weeks_min=roadmap.duration_weeks_min,
                    duration_weeks_max=roadmap.duration_weeks_max,
                    popularity=popularity,
                    is_saved=roadmap.id in saved_ids,
                    total_tasks=total_tasks,
                    completed_tasks=completed_tasks,
                    overall_progress_percent=self._percent(completed_tasks, total_tasks),
                )
            )

        return payload

    async def list_saved_roadmaps(self, user_id: UUID) -> list[SavedRoadmapRead]:
        rows = await self.repo.list_saved_roadmaps(user_id=user_id)
        roadmap_ids = [roadmap.id for _, roadmap, _ in rows]
        total_map = await self.repo.get_total_task_counts_for_roadmaps(roadmap_ids)
        completed_map = await self.repo.get_completed_task_counts_for_roadmaps(user_id=user_id, roadmap_ids=roadmap_ids)

        payload: list[SavedRoadmapRead] = []
        for saved, roadmap, popularity in rows:
            total_tasks = total_map.get(roadmap.id, 0)
            completed_tasks = completed_map.get(roadmap.id, 0)
            payload.append(
                SavedRoadmapRead(
                    saved_at=saved.saved_at,
                    roadmap=RoadmapListItemRead(
                        id=roadmap.id,
                        slug=roadmap.slug,
                        title=roadmap.title,
                        description=roadmap.description,
                        role_target=roadmap.role_target,
                        difficulty=roadmap.difficulty,
                        duration_weeks_min=roadmap.duration_weeks_min,
                        duration_weeks_max=roadmap.duration_weeks_max,
                        popularity=popularity,
                        is_saved=True,
                        total_tasks=total_tasks,
                        completed_tasks=completed_tasks,
                        overall_progress_percent=self._percent(completed_tasks, total_tasks),
                    ),
                )
            )

        return payload

    async def get_roadmap_detail(self, user_id: UUID, slug: str) -> RoadmapDetailRead | None:
        roadmap = await self.repo.get_roadmap_by_slug(slug=slug, public_only=True)
        if not roadmap:
            return None

        is_saved = await self.repo.user_saved_roadmap(user_id=user_id, roadmap_id=roadmap.id)
        popularity = await self.repo.get_popularity(roadmap.id)
        task_progress_map = await self.repo.get_user_task_progress_for_roadmap(user_id=user_id, roadmap_id=roadmap.id)
        stage_ids = [stage.id for stage in roadmap.stages]
        stored_stage_progress = await self.repo.get_stage_progress_map(user_id=user_id, stage_ids=stage_ids)
        submissions_map = await self.repo.get_submissions_for_roadmap(user_id=user_id, roadmap_id=roadmap.id)

        stage_items: list[StageDetailRead] = []
        total_tasks = 0
        completed_tasks = 0

        for stage in roadmap.stages:
            stage_task_items: list[StageTaskRead] = []
            stage_total = len(stage.tasks)
            stage_completed = 0

            for task in stage.tasks:
                status = task_progress_map.get(task.id, TaskProgressStatus.NOT_STARTED)
                if status == TaskProgressStatus.COMPLETED:
                    stage_completed += 1

                stage_task_items.append(
                    StageTaskRead(
                        id=task.id,
                        order_index=task.order_index,
                        title=task.title,
                        description=task.description,
                        estimated_hours=task.estimated_hours,
                        task_type=task.task_type,
                        resource_url=task.resource_url,
                        resource_title=task.resource_title,
                        status=status,
                    )
                )

            total_tasks += stage_total
            completed_tasks += stage_completed
            derived_stage_progress = self._percent(stage_completed, stage_total)

            stage_items.append(
                StageDetailRead(
                    id=stage.id,
                    order_index=stage.order_index,
                    title=stage.title,
                    objective=stage.objective,
                    duration_weeks=stage.duration_weeks,
                    progress_percent=stored_stage_progress.get(stage.id, derived_stage_progress),
                    tasks=stage_task_items,
                    projects=[
                        StageProjectRead(
                            id=project.id,
                            title=project.title,
                            brief=project.brief,
                            acceptance_criteria=list(project.acceptance_criteria or []),
                            rubric=dict(project.rubric or {}),
                            estimated_hours=project.estimated_hours,
                            submission=(
                                ProjectSubmissionRead.model_validate(submissions_map[project.id])
                                if project.id in submissions_map
                                else None
                            ),
                        )
                        for project in stage.projects
                    ],
                )
            )

        return RoadmapDetailRead(
            id=roadmap.id,
            slug=roadmap.slug,
            title=roadmap.title,
            description=roadmap.description,
            role_target=roadmap.role_target,
            difficulty=roadmap.difficulty,
            duration_weeks_min=roadmap.duration_weeks_min,
            duration_weeks_max=roadmap.duration_weeks_max,
            popularity=popularity,
            is_saved=is_saved,
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            overall_progress_percent=self._percent(completed_tasks, total_tasks),
            stages=stage_items,
        )

    async def save_roadmap(self, user_id: UUID, slug: str) -> SaveRoadmapResponse | None:
        roadmap = await self.repo.get_roadmap_by_slug(slug=slug, public_only=True)
        if not roadmap:
            return None

        await self.repo.save_roadmap(user_id=user_id, roadmap_id=roadmap.id)
        await self.repo.commit()

        return SaveRoadmapResponse(
            roadmap_slug=roadmap.slug,
            saved=True,
            popularity=await self.repo.get_popularity(roadmap.id),
        )

    async def unsave_roadmap(self, user_id: UUID, slug: str) -> SaveRoadmapResponse | None:
        roadmap = await self.repo.get_roadmap_by_slug(slug=slug, public_only=True)
        if not roadmap:
            return None

        await self.repo.unsave_roadmap(user_id=user_id, roadmap_id=roadmap.id)
        await self.repo.commit()

        return SaveRoadmapResponse(
            roadmap_slug=roadmap.slug,
            saved=False,
            popularity=await self.repo.get_popularity(roadmap.id),
        )

    async def update_task_progress(
        self,
        user_id: UUID,
        task_id: UUID,
        status: TaskProgressStatus,
    ) -> TaskProgressUpdateResponse | None:
        task = await self.repo.get_task_by_id(task_id)
        if not task:
            return None

        progress = await self.repo.get_task_progress_record(user_id=user_id, task_id=task_id)
        if progress:
            progress.status = status
        else:
            self.repo.add(UserTaskProgressModel(user_id=user_id, task_id=task_id, status=status))
            await self.repo.flush()

        stage_total_tasks = await self.repo.get_total_tasks_for_stage(task.stage_id)
        stage_completed_tasks = await self.repo.get_completed_tasks_for_stage(user_id=user_id, stage_id=task.stage_id)
        stage_progress_percent = self._percent(stage_completed_tasks, stage_total_tasks)

        stored_stage_progress = await self.repo.get_stage_progress_record(user_id=user_id, stage_id=task.stage_id)
        if stored_stage_progress:
            stored_stage_progress.progress_percent = stage_progress_percent
        else:
            self.repo.add(
                UserStageProgressModel(
                    user_id=user_id,
                    stage_id=task.stage_id,
                    progress_percent=stage_progress_percent,
                )
            )

        roadmap_id = task.stage.roadmap_id
        total_tasks = await self.repo.get_total_tasks_for_roadmap(roadmap_id)
        completed_tasks = await self.repo.get_completed_tasks_for_roadmap(user_id=user_id, roadmap_id=roadmap_id)

        await self.repo.commit()

        return TaskProgressUpdateResponse(
            task_id=task.id,
            status=status,
            stage_id=task.stage_id,
            stage_progress_percent=stage_progress_percent,
            roadmap_id=roadmap_id,
            roadmap_progress_percent=self._percent(completed_tasks, total_tasks),
            completed_tasks=completed_tasks,
            total_tasks=total_tasks,
        )

    async def submit_project(
        self,
        user_id: UUID,
        project_id: UUID,
        payload: ProjectSubmissionRequest,
    ) -> ProjectSubmissionRead | None:
        project = await self.repo.get_project_by_id(project_id)
        if not project:
            return None

        submission = await self.repo.get_submission(user_id=user_id, project_id=project_id)
        if submission:
            submission.repo_url = payload.repo_url
            submission.live_url = payload.live_url
            submission.notes = payload.notes
            if payload.status is not None:
                submission.status = payload.status
        else:
            status = payload.status or ProjectSubmissionStatus.DRAFT
            submission = UserProjectSubmissionModel(
                user_id=user_id,
                project_id=project_id,
                repo_url=payload.repo_url,
                live_url=payload.live_url,
                notes=payload.notes,
                status=status,
            )
            self.repo.add(submission)

        await self.repo.commit()
        return ProjectSubmissionRead.model_validate(submission)

    def build_stage_grouped_tasks(self, detail: RoadmapDetailRead) -> dict[str, dict[str, list[StageTaskRead]]]:
        grouped: dict[str, dict[str, list[StageTaskRead]]] = {}

        for stage in detail.stages:
            ordered: dict[str, list[StageTaskRead]] = OrderedDict()
            for task_type in self.TASK_TYPE_ORDER:
                items = [task for task in stage.tasks if task.task_type.value == task_type]
                if items:
                    ordered[task_type] = items
            grouped[str(stage.id)] = ordered

        return grouped
