import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { ResumeAuditWidget } from "@/features/profile-resumes/ResumeAuditWidget";
import {
  fetchResourceDetail,
  fetchResourceProgress,
  setLessonProgress,
  type ResourceDetail,
  type ResourceProgress,
} from "@/features/resources-roadmaps/api";

/**
 * The lesson viewer (`resource_detail.html`/`resource_detail.js`), minus the
 * `resume_upload` lesson type's own implementation — that widget is
 * TASK-047's `ResumeAuditWidget`, reused here rather than rebuilt, since it
 * already owns `/resume-course-audits`.
 *
 * Progress is read from `ResourceProgressRead.progress_percent` and each
 * module's `progress_percent`, never recomputed from `completed_lesson_ids`
 * (the legacy JS derived percentages client-side; F-15 is why this doesn't).
 */
export function ResourceDetailPage() {
  const { resourceId = "" } = useParams();
  const detailQuery = useQuery({
    queryKey: queryKeys.resources.detail(resourceId),
    queryFn: () => fetchResourceDetail(resourceId),
  });
  const progressQuery = useQuery({
    queryKey: queryKeys.resources.progress(resourceId),
    queryFn: () => fetchResourceProgress(resourceId),
  });

  return (
    <div className="space-y-6">
      <AsyncBoundary query={detailQuery}>
        {(resource) => (
          <>
            <DocumentMeta title={resource.title} description={resource.description} path={`/resources/${resourceId}`} />
            <AsyncBoundary query={progressQuery}>
              {(progress) => <LessonViewer resource={resource} progress={progress} />}
            </AsyncBoundary>
          </>
        )}
      </AsyncBoundary>
    </div>
  );
}

type ResourceModule = ResourceDetail["modules"][number];
type Lesson = NonNullable<ResourceModule["lessons"]>[number];

function LessonViewer({ resource, progress }: { resource: ResourceDetail; progress: ResourceProgress }) {
  const { t } = useTranslation();
  const allLessons: Lesson[] = resource.modules.flatMap((module) => module.lessons ?? []);
  const [lessonId, setLessonId] = useState(allLessons[0]?.id ?? "");
  const lesson = allLessons.find((candidate) => candidate.id === lessonId) ?? allLessons[0] ?? null;
  const completed = new Set(progress.completed_lesson_ids);

  const moduleProgressById = new Map(progress.modules.map((module) => [module.module_id, module]));

  return (
    <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
      <aside className="space-y-4">
        <div>
          <h1 className="text-xl font-bold text-ink">{resource.title}</h1>
          <p className="mt-1 text-sm text-ink-soft">
            {t("resources.progressLabel", { percent: progress.progress_percent })}
          </p>
          <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-border">
            <div className="h-full bg-brand" style={{ width: `${progress.progress_percent}%` }} />
          </div>
        </div>
        <nav aria-label={t("resources.outline")} className="space-y-4">
          {resource.modules.map((module) => {
            const moduleProgress = moduleProgressById.get(module.id);
            return (
              <div key={module.id}>
                <div className="flex items-center justify-between text-sm font-semibold text-ink">
                  <span>{module.title}</span>
                  {moduleProgress ? (
                    <span className="text-xs font-normal text-ink-muted">
                      {moduleProgress.completed_lessons}/{moduleProgress.total_lessons}
                    </span>
                  ) : null}
                </div>
                <ul className="mt-1 space-y-1">
                  {(module.lessons ?? []).map((moduleLesson) => (
                    <li key={moduleLesson.id}>
                      <button
                        type="button"
                        onClick={() => setLessonId(moduleLesson.id)}
                        aria-current={moduleLesson.id === lesson?.id}
                        className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm ${
                          moduleLesson.id === lesson?.id
                            ? "bg-brand/10 font-medium text-brand"
                            : "text-ink-soft hover:bg-canvas"
                        }`}
                      >
                        <span aria-hidden="true">{completed.has(moduleLesson.id) ? "✅" : "○"}</span>
                        {moduleLesson.title}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </nav>
      </aside>

      <div className="space-y-4">
        {lesson ? (
          <LessonContent
            resourceId={resource.id}
            lesson={lesson}
            allLessons={allLessons}
            completed={completed}
            onNavigate={setLessonId}
          />
        ) : (
          <p className="text-sm text-ink-soft">{t("resources.noLessons")}</p>
        )}
      </div>
    </div>
  );
}

function LessonContent({
  resourceId,
  lesson,
  allLessons,
  completed,
  onNavigate,
}: {
  resourceId: string;
  lesson: Lesson;
  allLessons: Lesson[];
  completed: Set<string>;
  onNavigate: (lessonId: string) => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const isCompleted = completed.has(lesson.id);
  const currentIndex = allLessons.findIndex((candidate) => candidate.id === lesson.id);
  const nextLesson = allLessons[currentIndex + 1] ?? null;

  const mutation = useMutation({
    mutationFn: () => setLessonProgress(lesson.id, true),
    onSuccess: (progress) => {
      queryClient.setQueryData(queryKeys.resources.progress(resourceId), progress);
      onNavigate(nextLesson ? nextLesson.id : lesson.id);
    },
  });

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-ink">{lesson.title}</h2>

      <div className="rounded-lg border border-border bg-surface p-5">
        <LessonBody lesson={lesson} />
      </div>

      {lesson.content_type === "resume_upload" ? null : (
        <div className="flex items-center gap-3">
          <Button
            variant={isCompleted ? "secondary" : "primary"}
            disabled={mutation.isPending}
            onClick={() => (isCompleted && nextLesson ? onNavigate(nextLesson.id) : mutation.mutate())}
          >
            {isCompleted
              ? nextLesson
                ? t("resources.nextLesson")
                : t("resources.completed")
              : mutation.isPending
                ? t("resources.markingComplete")
                : t("resources.markComplete")}
          </Button>
          {mutation.isError ? <Alert tone="danger">{t("resources.progressError")}</Alert> : null}
        </div>
      )}
    </div>
  );
}

function LessonBody({ lesson }: { lesson: Lesson }) {
  const { t } = useTranslation();

  if (lesson.content_type === "resume_upload") {
    return <ResumeAuditWidget />;
  }

  if (lesson.content_type === "video_url" && lesson.video_url) {
    const embedUrl = toEmbedUrl(lesson.video_url);
    if (!embedUrl) return <p className="text-sm text-ink-soft">{t("resources.invalidVideo")}</p>;
    return (
      <div className="space-y-2">
        {lesson.notes ? <p className="text-sm text-ink-soft">{lesson.notes}</p> : null}
        <div className="aspect-video w-full overflow-hidden rounded-md">
          <iframe
            src={embedUrl}
            title={lesson.title}
            className="h-full w-full"
            allowFullScreen
            loading="lazy"
            referrerPolicy="strict-origin-when-cross-origin"
          />
        </div>
      </div>
    );
  }

  if (
    (lesson.content_type === "external_link" || lesson.content_type === "pdf_url" || lesson.content_type === "ppt_url") &&
    lesson.resource_url &&
    isSafeHttpUrl(lesson.resource_url)
  ) {
    return (
      <div className="space-y-2">
        {lesson.notes ? <p className="text-sm text-ink-soft">{lesson.notes}</p> : null}
        <p className="text-sm text-ink-soft">{t("resources.externalResourceIntro")}</p>
        <a
          href={lesson.resource_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-strong"
        >
          {t("resources.openResource")}
        </a>
      </div>
    );
  }

  // `html`-typed content is authored by admins, but this app has no HTML
  // sanitizer on the frontend; rendering it as text (React escapes it) is the
  // safe default until one is added, even though it loses formatting for that
  // one lesson type. Plain-text lessons render the same way.
  return <p className="whitespace-pre-wrap text-sm text-ink-soft">{lesson.content}</p>;
}

function isSafeHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function toEmbedUrl(url: string): string | null {
  try {
    const parsed = new URL(url);
    if (parsed.hostname.includes("youtube.com") || parsed.hostname.includes("youtu.be")) {
      const videoId = parsed.hostname.includes("youtu.be")
        ? parsed.pathname.slice(1)
        : parsed.searchParams.get("v");
      return videoId ? `https://www.youtube.com/embed/${videoId}` : null;
    }
    if (parsed.hostname.includes("vimeo.com")) {
      const videoId = parsed.pathname.split("/").filter(Boolean).pop();
      return videoId ? `https://player.vimeo.com/video/${videoId}` : null;
    }
    return null;
  } catch {
    return null;
  }
}
