import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import {
  type ProjectSubmission,
  type RoadmapDetail,
  fetchRoadmapDetail,
  saveRoadmap,
  setTaskProgress,
  submitProject,
  type TaskProgressStatus,
  unsaveRoadmap,
} from "@/features/resources-roadmaps/api";

const TASK_STATUSES: TaskProgressStatus[] = ["not_started", "in_progress", "completed"];

/** Literal keys, not a template: see the note in `DashboardPage.tsx`. */
function taskStatusLabel(status: TaskProgressStatus, t: (key: string) => string): string {
  switch (status) {
    case "not_started":
      return t("roadmaps.detail.taskStatus.notStarted");
    case "in_progress":
      return t("roadmaps.detail.taskStatus.inProgress");
    case "completed":
      return t("roadmaps.detail.taskStatus.completed");
  }
}

/**
 * `roadmap_detail.html`/`roadmap_detail.js`. Save toggling and task progress
 * both write server responses straight back into the cache — the legacy JS
 * already did this without recomputing anything locally, which is the
 * pattern F-15 asks every screen in this vertical to keep.
 */
export function RoadmapDetailPage() {
  const { slug = "" } = useParams();
  const query = useQuery({ queryKey: queryKeys.roadmaps.detail(slug), queryFn: () => fetchRoadmapDetail(slug) });

  return (
    <div className="space-y-8">
      <AsyncBoundary query={query}>
        {(roadmap) => (
          <>
            <DocumentMeta title={roadmap.title} description={roadmap.description} path={`/roadmaps/${slug}`} />
            <RoadmapHeader roadmap={roadmap} />
            <div className="space-y-6">
              {roadmap.stages
                .slice()
                .sort((a, b) => a.order_index - b.order_index)
                .map((stage) => (
                  <StageCard key={stage.id} slug={slug} stage={stage} />
                ))}
            </div>
          </>
        )}
      </AsyncBoundary>
    </div>
  );
}

function RoadmapHeader({ roadmap }: { roadmap: RoadmapDetail }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => (roadmap.is_saved ? unsaveRoadmap(roadmap.slug) : saveRoadmap(roadmap.slug)),
    onSuccess: (result) => {
      queryClient.setQueryData(queryKeys.roadmaps.detail(roadmap.slug), {
        ...roadmap,
        is_saved: result.saved,
        popularity: result.popularity,
      });
    },
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-ink">{roadmap.title}</h1>
          <p className="mt-1 text-ink-soft">{roadmap.description}</p>
        </div>
        <Button
          variant={roadmap.is_saved ? "secondary" : "primary"}
          disabled={mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {roadmap.is_saved ? t("roadmaps.detail.unsave") : t("roadmaps.detail.save")}
        </Button>
      </div>
      <div className="flex flex-wrap gap-3 text-sm text-ink-muted">
        <span>{roadmap.difficulty}</span>
        <span>
          {roadmap.duration_weeks_min}–{roadmap.duration_weeks_max} {t("roadmaps.weeks")}
        </span>
        <span>{t("roadmaps.saveCount", { count: roadmap.popularity })}</span>
      </div>
      <div>
        <p className="text-sm text-ink-soft">
          {t("roadmaps.tasksCompleted", { completed: roadmap.completed_tasks, total: roadmap.total_tasks })}
        </p>
        <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-border">
          <div className="h-full bg-brand" style={{ width: `${roadmap.overall_progress_percent}%` }} />
        </div>
      </div>
    </div>
  );
}

function StageCard({ slug, stage }: { slug: string; stage: RoadmapDetail["stages"][number] }) {
  const { t } = useTranslation();
  return (
    <section className="rounded-lg border border-border bg-surface p-5">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-ink">{stage.title}</h2>
        <span className="text-sm text-ink-muted">{stage.progress_percent}%</span>
      </div>
      <p className="mt-1 text-sm text-ink-soft">{stage.objective}</p>

      <div className="mt-4 space-y-2">
        {stage.tasks
          .slice()
          .sort((a, b) => a.order_index - b.order_index)
          .map((task) => (
            <TaskRow key={task.id} slug={slug} stageId={stage.id} task={task} />
          ))}
      </div>

      {stage.projects.length > 0 ? (
        <div className="mt-4 space-y-4">
          <h3 className="text-sm font-semibold text-ink">{t("roadmaps.detail.projects")}</h3>
          {stage.projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      ) : null}
    </section>
  );
}

function TaskRow({
  slug,
  stageId,
  task,
}: {
  slug: string;
  stageId: string;
  task: RoadmapDetail["stages"][number]["tasks"][number];
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (status: TaskProgressStatus) => setTaskProgress(task.id, status),
    onSuccess: (result) => {
      queryClient.setQueryData<RoadmapDetail | undefined>(queryKeys.roadmaps.detail(slug), (current) => {
        if (!current) return current;
        return {
          ...current,
          completed_tasks: result.completed_tasks,
          total_tasks: result.total_tasks,
          overall_progress_percent: result.roadmap_progress_percent,
          stages: current.stages.map((stage) =>
            stage.id !== stageId
              ? stage
              : {
                  ...stage,
                  progress_percent: result.stage_progress_percent,
                  tasks: stage.tasks.map((candidate) =>
                    candidate.id === task.id ? { ...candidate, status: result.status } : candidate,
                  ),
                },
          ),
        };
      });
    },
  });

  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2">
      <div>
        <p className="text-sm font-medium text-ink">{task.title}</p>
        <p className="text-xs text-ink-muted">{task.description}</p>
      </div>
      <select
        value={task.status}
        disabled={mutation.isPending}
        onChange={(event) => mutation.mutate(event.target.value as TaskProgressStatus)}
        className="rounded-md border border-border bg-surface px-2 py-1 text-xs text-ink"
      >
        {TASK_STATUSES.map((status) => (
          <option key={status} value={status}>
            {taskStatusLabel(status, t)}
          </option>
        ))}
      </select>
    </div>
  );
}

function ProjectCard({ project }: { project: RoadmapDetail["stages"][number]["projects"][number] }) {
  const { t } = useTranslation();
  const [repoUrl, setRepoUrl] = useState(project.submission?.repo_url ?? "");
  const [liveUrl, setLiveUrl] = useState(project.submission?.live_url ?? "");
  const [notes, setNotes] = useState(project.submission?.notes ?? "");

  const mutation = useMutation({
    mutationFn: (payload: ProjectSubmission) => submitProject(project.id, payload),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate({
      repo_url: repoUrl || null,
      live_url: liveUrl || null,
      notes: notes || null,
      status: "submitted",
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-2 rounded-md border border-border p-3">
      <p className="text-sm font-medium text-ink">{project.title}</p>
      <p className="text-xs text-ink-soft">{project.brief}</p>
      <div className="grid gap-2 sm:grid-cols-2">
        <input
          value={repoUrl}
          onChange={(event) => setRepoUrl(event.target.value)}
          placeholder={t("roadmaps.detail.repoUrl")}
          className="rounded-md border border-border bg-surface px-2 py-1 text-xs text-ink"
        />
        <input
          value={liveUrl}
          onChange={(event) => setLiveUrl(event.target.value)}
          placeholder={t("roadmaps.detail.liveUrl")}
          className="rounded-md border border-border bg-surface px-2 py-1 text-xs text-ink"
        />
      </div>
      <textarea
        value={notes}
        onChange={(event) => setNotes(event.target.value)}
        placeholder={t("roadmaps.detail.notes")}
        rows={2}
        className="w-full rounded-md border border-border bg-surface px-2 py-1 text-xs text-ink"
      />
      {mutation.isError ? (
        <Alert tone="danger">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("roadmaps.detail.submitError")}
        </Alert>
      ) : null}
      {mutation.isSuccess ? <Alert tone="success">{t("roadmaps.detail.submitSuccess")}</Alert> : null}
      <Button type="submit" variant="secondary" disabled={mutation.isPending}>
        {mutation.isPending ? t("roadmaps.detail.submitting") : t("roadmaps.detail.submit")}
      </Button>
    </form>
  );
}
