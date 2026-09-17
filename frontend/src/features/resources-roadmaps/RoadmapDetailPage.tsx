import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { PageScope } from "@/components/layout/PageScope";
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
    <PageScope name={["roadmaps", "roadmap"]}>
      <AsyncBoundary query={query}>
        {(roadmap) => (
          <section className="roadmap-detail-page">
            <DocumentMeta title={roadmap.title} description={roadmap.description} path={`/roadmaps/${slug}`} />
            <RoadmapHeader roadmap={roadmap} />
            <div className="detail-layout">
              <section className="stages-column">
                {roadmap.stages
                  .slice()
                  .sort((a, b) => a.order_index - b.order_index)
                  .map((stage) => (
                    <StageCard key={stage.id} slug={slug} stage={stage} />
                  ))}
              </section>
            </div>
          </section>
        )}
      </AsyncBoundary>
    </PageScope>
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
    <>
      <div className="detail-topbar">
        <div>
          <p className="eyebrow">{roadmap.difficulty}</p>
          <h2>{roadmap.title}</h2>
          <p>{roadmap.description}</p>
        </div>
        <div className="topbar-actions">
          <button
            type="button"
            className="save-button"
            data-saved={roadmap.is_saved ? 1 : 0}
            disabled={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {roadmap.is_saved ? t("roadmaps.detail.unsave") : t("roadmaps.detail.save")}
          </button>
          <span className="save-counter">{t("roadmaps.saveCount", { count: roadmap.popularity })}</span>
        </div>
      </div>

      <div className="overall-progress">
        <div className="progress-head">
          <span>{t("roadmaps.detail.overallProgress")}</span>
          <span>{roadmap.overall_progress_percent}%</span>
        </div>
        <div className="progress-track">
          <span className="roadmap-progress-fill" style={{ width: `${roadmap.overall_progress_percent}%` }} />
        </div>
        <small>{t("roadmaps.tasksCompleted", { completed: roadmap.completed_tasks, total: roadmap.total_tasks })}</small>
      </div>
    </>
  );
}

function StageCard({ slug, stage }: { slug: string; stage: RoadmapDetail["stages"][number] }) {
  const { t } = useTranslation();
  return (
    <article className="stage-card">
      <div className="stage-header">
        <div>
          <h3>{t("roadmaps.detail.stageLabel", { order: stage.order_index, title: stage.title })}</h3>
          <p>{t("roadmaps.weeksCount", { count: stage.duration_weeks })}</p>
        </div>
        <div className="stage-progress-wrap">
          <span>{stage.progress_percent}%</span>
          <div className="progress-track stage-track">
            <span className="roadmap-progress-fill" style={{ width: `${stage.progress_percent}%` }} />
          </div>
        </div>
      </div>

      <div className="stage-body">
        <p className="stage-objective">{stage.objective}</p>

        <div className="task-group">
          <ul className="task-list">
            {stage.tasks
              .slice()
              .sort((a, b) => a.order_index - b.order_index)
              .map((task) => (
                <TaskRow key={task.id} slug={slug} stageId={stage.id} task={task} />
              ))}
          </ul>
        </div>

        {stage.projects.map((project) => (
          <ProjectCard key={project.id} project={project} />
        ))}
      </div>
    </article>
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
    <li className="task-item">
      <div className="task-main">
        <input
          type="checkbox"
          className="task-checkbox"
          checked={task.status === "completed"}
          disabled={mutation.isPending}
          aria-label={task.title}
          onChange={(event) => mutation.mutate(event.target.checked ? "completed" : "not_started")}
        />
        <span className="task-open">{task.title}</span>
      </div>
      <div className="task-meta">
        {task.estimated_hours ? <span>{t("roadmaps.detail.hours", { count: task.estimated_hours })}</span> : null}
        <select
          className="task-status"
          value={task.status}
          disabled={mutation.isPending}
          aria-label={t("roadmaps.detail.statusFor", { title: task.title })}
          onChange={(event) => mutation.mutate(event.target.value as TaskProgressStatus)}
        >
          {TASK_STATUSES.map((status) => (
            <option key={status} value={status}>
              {taskStatusLabel(status, t)}
            </option>
          ))}
        </select>
      </div>
    </li>
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
    <form onSubmit={handleSubmit} className="submission-form">
      <p className="project-label">{t("roadmaps.detail.projects")}</p>
      <h4>{project.title}</h4>
      <p>{project.brief}</p>
      <input
        type="url"
        value={repoUrl}
        onChange={(event) => setRepoUrl(event.target.value)}
        placeholder={t("roadmaps.detail.repoUrl")}
        aria-label={t("roadmaps.detail.repoUrl")}
      />
      <input
        type="url"
        value={liveUrl}
        onChange={(event) => setLiveUrl(event.target.value)}
        placeholder={t("roadmaps.detail.liveUrl")}
        aria-label={t("roadmaps.detail.liveUrl")}
      />
      <textarea
        value={notes}
        onChange={(event) => setNotes(event.target.value)}
        placeholder={t("roadmaps.detail.notes")}
        aria-label={t("roadmaps.detail.notes")}
        rows={4}
      />
      {mutation.isError ? (
        <small role="alert">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("roadmaps.detail.submitError")}
        </small>
      ) : null}
      {mutation.isSuccess ? <small role="status">{t("roadmaps.detail.submitSuccess")}</small> : null}
      <button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? t("roadmaps.detail.submitting") : t("roadmaps.detail.submit")}
      </button>
    </form>
  );
}
