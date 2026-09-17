import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { Alert, Arrow, Badge, Button, Card, Icon, Input, ProgressBar, toIconName } from "@/components/ui";
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
  );
}

type ResourceModule = ResourceDetail["modules"][number];
type Lesson = NonNullable<ResourceModule["lessons"]>[number];

function LessonViewer({ resource, progress }: { resource: ResourceDetail; progress: ResourceProgress }) {
  const { t } = useTranslation();
  const allLessons: Lesson[] = resource.modules.flatMap((module) => module.lessons ?? []);
  const [lessonId, setLessonId] = useState(allLessons[0]?.id ?? "");
  const [search, setSearch] = useState("");
  const lesson = allLessons.find((candidate) => candidate.id === lessonId) ?? allLessons[0] ?? null;
  const completed = new Set(progress.completed_lesson_ids);
  const moduleProgressById = new Map(progress.modules.map((module) => [module.module_id, module]));
  const lessonNumber = lesson ? allLessons.findIndex((candidate) => candidate.id === lesson.id) + 1 : 0;

  // The `#lesson-search` box filtered the outline in place; a module whose
  // lessons all fall out of the filter disappears with them.
  const outline = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return resource.modules.map((module) => ({ module, lessons: module.lessons ?? [] }));
    return resource.modules
      .map((module) => ({
        module,
        lessons: (module.lessons ?? []).filter(
          (item) => item.title.toLowerCase().includes(term) || module.title.toLowerCase().includes(term),
        ),
      }))
      .filter((entry) => entry.lessons.length > 0);
  }, [resource.modules, search]);

  return (
    // Two columns on a laptop, stacked below it. The outline is `order-2` on a
    // phone so the lesson you came to read is the first thing on the screen.
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
      <aside className="order-2 flex w-full shrink-0 flex-col gap-3 lg:order-1 lg:w-72">
        <Card className="flex flex-col gap-3">
          <Link to="/resources" className="text-body-sm text-ink-soft transition-colors hover:text-ink">
            <Arrow direction="back" />
            {t("resources.detail.back")}
          </Link>

          <div className="min-w-0">
            <h2 className="flex items-center gap-2 text-card-title text-ink">
              <Icon name={toIconName(resource.icon, "book")} size={20} className="text-primary" />
              {resource.title}
            </h2>
            <p className="mt-1 text-caption text-ink-soft">{resource.description}</p>
          </div>

          <label>
            <span className="sr-only">{t("resources.detail.searchLessons")}</span>
            <Input
              type="search"
              autoComplete="off"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t("resources.detail.searchPlaceholder")}
            />
          </label>
        </Card>

        <Card padding="sm" className="flex max-h-[32rem] flex-col gap-4 overflow-y-auto">
          {outline.map(({ module, lessons }) => {
            const moduleProgress = moduleProgressById.get(module.id);
            return (
              <section key={module.id}>
                <div className="px-2 pb-1.5">
                  <p className="text-label text-ink">
                    {t("resources.detail.moduleLabel", { position: module.position, title: module.title })}
                  </p>
                  <p className="text-caption text-ink-muted">
                    {t("resources.detail.moduleProgress", {
                      completed: moduleProgress?.completed_lessons ?? 0,
                      total: moduleProgress?.total_lessons ?? lessons.length,
                    })}
                  </p>
                </div>

                <ul className="flex flex-col gap-0.5">
                  {lessons.map((moduleLesson) => {
                    const active = moduleLesson.id === lesson?.id;
                    return (
                      <li key={moduleLesson.id}>
                        <button
                          type="button"
                          onClick={() => setLessonId(moduleLesson.id)}
                          aria-current={active}
                          className={
                            active
                              ? "flex w-full items-start gap-2 rounded-md bg-primary-subtle px-2 py-1.5 text-left text-primary"
                              : "flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-ink-soft transition-colors hover:bg-surface-hover hover:text-ink"
                          }
                        >
                          <Icon
                            name={completed.has(moduleLesson.id) ? "check-circle" : "document"}
                            size={16}
                            variant={completed.has(moduleLesson.id) ? "Bold" : "Linear"}
                            className="mt-0.5"
                          />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-body-sm font-medium">{moduleLesson.title}</span>
                            <span className="block text-caption text-ink-muted">
                              {moduleLesson.reading_time_minutes
                                ? t("resources.detail.readingTime", { count: moduleLesson.reading_time_minutes })
                                : t("resources.detail.lessonNumber", {
                                    module: module.position,
                                    lesson: moduleLesson.position,
                                  })}
                            </span>
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </section>
            );
          })}

          {outline.length === 0 ? (
            <p className="px-2 py-4 text-center text-caption text-ink-muted">{t("resources.detail.searchEmpty")}</p>
          ) : null}
        </Card>
      </aside>

      <div className="order-1 flex min-w-0 flex-1 flex-col gap-4 lg:order-2">
        <Card className="flex flex-col gap-3" aria-live="polite">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">
              {t("resources.detail.lessonStep", { current: lessonNumber, total: allLessons.length })}
            </Badge>
          </div>
          <ProgressBar
            label={t("resources.progressLabel", { percent: progress.progress_percent })}
            value={progress.progress_percent}
            showValue={false}
          />
        </Card>

        <Card padding="lg">
          {lesson ? (
            <LessonContent
              resourceId={resource.id}
              lesson={lesson}
              allLessons={allLessons}
              completed={completed}
              onNavigate={setLessonId}
            />
          ) : (
            <p className="text-center text-body-sm text-ink-muted">{t("resources.noLessons")}</p>
          )}
        </Card>

        <Card className="flex flex-col gap-3">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
            {(
              [
                [t("resources.detail.meta.category"), resource.category],
                [t("resources.detail.meta.level"), resource.level ?? t("resources.detail.notSpecified")],
                [
                  t("resources.detail.meta.duration"),
                  resource.estimated_duration_minutes
                    ? t("resources.minutes", { count: resource.estimated_duration_minutes })
                    : t("resources.detail.notAvailable"),
                ],
                [t("resources.detail.meta.modules"), String(resource.modules.length)],
                [t("resources.detail.meta.lessons"), String(allLessons.length)],
                [t("resources.detail.meta.progress"), `${progress.progress_percent}%`],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="min-w-0">
                <dt className="text-overline text-ink-muted uppercase">{label}</dt>
                <dd className="truncate text-body-sm text-ink">{value}</dd>
              </div>
            ))}
          </dl>

          {resource.external_url ? (
            <a href={resource.external_url} target="_blank" rel="noopener noreferrer" className="self-start">
              <Button variant="outline" size="sm">
                {t("resources.openResource")}
              </Button>
            </a>
          ) : null}
        </Card>
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
    <div className="flex flex-col gap-4">
      <div className="min-w-0">
        <h3 className="text-section-title text-ink">{lesson.title}</h3>
        {lesson.notes ? <p className="mt-1 text-body-sm text-ink-soft">{lesson.notes}</p> : null}
      </div>

      <LessonBody lesson={lesson} />

      {lesson.content_type === "resume_upload" ? null : (
        <div className="flex flex-col gap-2 border-t border-border pt-4">
          <Button
            className="self-start"
            loading={mutation.isPending}
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
    if (!embedUrl) return <p className="text-body-sm text-ink-muted">{t("resources.invalidVideo")}</p>;
    return (
      <div className="overflow-hidden rounded-lg bg-ink">
        <div className="relative aspect-video w-full">
          <iframe
            src={embedUrl}
            title={lesson.title}
            allowFullScreen
            loading="lazy"
            referrerPolicy="strict-origin-when-cross-origin"
            className="absolute inset-0 size-full border-0"
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
      <div className="flex flex-col gap-3">
        <p className="text-body-sm text-ink-soft">{t("resources.externalResourceIntro")}</p>
        <a href={lesson.resource_url} target="_blank" rel="noopener noreferrer" className="self-start">
          <Button variant="outline">{t("resources.openResource")}</Button>
        </a>
      </div>
    );
  }

  // `html`-typed content is authored by admins, but this app has no HTML
  // sanitizer on the frontend; rendering it as text (React escapes it) is the
  // safe default until one is added, even though it loses formatting for that
  // one lesson type. Plain-text lessons render the same way.
  return <p className="text-body whitespace-pre-wrap text-ink-soft">{lesson.content}</p>;
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
