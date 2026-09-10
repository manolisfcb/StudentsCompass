/**
 * Resources hub and roadmaps (TASK-048). Resource paths were already
 * correctly named — only the roadmap "save" relation was renamed, to the
 * idempotent `PUT/DELETE /roadmaps/{slug}/saves/me` (plan 08 §5.2). Every
 * progress figure here (`progress_percent`, `roadmap_progress_percent`, …) is
 * `CourseProgressProjector`'s or the roadmap service's own computation — this
 * file never derives a percentage from a raw count (F-15).
 */

import { apiRequest } from "@/api/client";
import type { RequestOf, ResponseOf } from "@/api/types";

export type Resource = ResponseOf<"resources_get_resources">[number];
export type ResourceDetail = ResponseOf<"resources_get_resource">;
export type ResourceProgress = ResponseOf<"resources_get_resource_progress">;
export type Roadmap = ResponseOf<"roadmaps_list_roadmaps">[number];
export type SavedRoadmap = ResponseOf<"roadmaps_get_my_roadmaps">[number];
export type RoadmapDetail = ResponseOf<"roadmaps_get_roadmap">;
export type SaveRoadmapResult = ResponseOf<"roadmaps_save_roadmap">;
export type TaskProgressStatus = RequestOf<"roadmaps_patch_task_progress">["status"];
export type TaskProgressResult = ResponseOf<"roadmaps_patch_task_progress">;
export type ProjectSubmission = RequestOf<"roadmaps_submit_project">;
export type ProjectSubmissionResult = ResponseOf<"roadmaps_submit_project">;

export async function fetchResources(): Promise<Resource[]> {
  const { data } = await apiRequest<Resource[]>("/api/v1/resources");
  return data;
}

export async function fetchResourceDetail(resourceId: string): Promise<ResourceDetail> {
  const { data } = await apiRequest<ResourceDetail>(`/api/v1/resources/${resourceId}`);
  return data;
}

export async function fetchResourceProgress(resourceId: string): Promise<ResourceProgress> {
  const { data } = await apiRequest<ResourceProgress>(`/api/v1/resources/${resourceId}/progress`);
  return data;
}

export async function setLessonProgress(lessonId: string, completed: boolean): Promise<ResourceProgress> {
  const { data } = await apiRequest<ResourceProgress>(`/api/v1/resources/lessons/${lessonId}/progress`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ completed }),
  });
  return data;
}

export async function fetchRoadmaps(): Promise<Roadmap[]> {
  const { data } = await apiRequest<Roadmap[]>("/api/v1/roadmaps");
  return data;
}

export async function fetchSavedRoadmaps(): Promise<SavedRoadmap[]> {
  const { data } = await apiRequest<SavedRoadmap[]>("/api/v1/me/roadmaps");
  return data;
}

export async function fetchRoadmapDetail(slug: string): Promise<RoadmapDetail> {
  const { data } = await apiRequest<RoadmapDetail>(`/api/v1/roadmaps/${slug}`);
  return data;
}

export async function saveRoadmap(slug: string): Promise<SaveRoadmapResult> {
  const { data } = await apiRequest<SaveRoadmapResult>(`/api/v1/roadmaps/${slug}/saves/me`, {
    method: "PUT",
  });
  return data;
}

export async function unsaveRoadmap(slug: string): Promise<SaveRoadmapResult> {
  const { data } = await apiRequest<SaveRoadmapResult>(`/api/v1/roadmaps/${slug}/saves/me`, {
    method: "DELETE",
  });
  return data;
}

export async function setTaskProgress(
  taskId: string,
  status: TaskProgressStatus,
): Promise<TaskProgressResult> {
  const { data } = await apiRequest<TaskProgressResult>(`/api/v1/tasks/${taskId}/progress`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  return data;
}

export async function submitProject(
  projectId: string,
  payload: ProjectSubmission,
): Promise<ProjectSubmissionResult> {
  const { data } = await apiRequest<ProjectSubmissionResult>(`/api/v1/projects/${projectId}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return data;
}
