import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { PageScope } from "@/components/layout/PageScope";
import { Alert } from "@/components/primitives/Alert";
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
    <PageScope name="resources" className="resource-page-main">
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
    </PageScope>
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
    <div className="resources-container">
      <section className="resource-course-shell">
        <aside className="panel course-sidebar">
          <div className="course-sidebar-header">
            <Link to="/resources" className="course-back-link">
              {t("resources.detail.back")}
            </Link>
            <h2>
              <span aria-hidden="true">{resource.icon ?? "📚"}</span> {resource.title}
            </h2>
            <p>{resource.description}</p>
            <label className="course-search-wrap">
              <span className="sr-only">{t("resources.detail.searchLessons")}</span>
              <input
                type="search"
                autoComplete="off"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={t("resources.detail.searchPlaceholder")}
              />
            </label>
          </div>

          <div className="course-outline">
            {outline.map(({ module, lessons }) => {
              const moduleProgress = moduleProgressById.get(module.id);
              return (
                <section key={module.id} className="course-module">
                  <div className="course-module-btn">
                    <span className="course-module-caret" aria-hidden="true">
                      ▾
                    </span>
                    <span className="course-module-copy">
                      <span className="course-module-title">
                        {t("resources.detail.moduleLabel", { position: module.position, title: module.title })}
                      </span>
                      <span className="course-module-progress">
                        {t("resources.detail.moduleProgress", {
                          completed: moduleProgress?.completed_lessons ?? 0,
                          total: moduleProgress?.total_lessons ?? lessons.length,
                        })}
                      </span>
                    </span>
                  </div>
                  <ul className="course-lessons">
                    {lessons.map((moduleLesson) => (
                      <li key={moduleLesson.id} className="course-lesson-row">
                        <button
                          type="button"
                          onClick={() => setLessonId(moduleLesson.id)}
                          aria-current={moduleLesson.id === lesson?.id}
                          className={`outline-lesson-btn course-lesson-btn${
                            moduleLesson.id === lesson?.id ? " active" : ""
                          }`}
                        >
                          <span className="course-lesson-icon" aria-hidden="true">
                            {completed.has(moduleLesson.id) ? "✅" : "📄"}
                          </span>
                          <span className="course-lesson-copy">
                            <span className="course-lesson-title">{moduleLesson.title}</span>
                            <span className="course-lesson-meta">
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
                    ))}
                  </ul>
                </section>
              );
            })}
          </div>

          {outline.length === 0 ? <p className="lesson-search-empty">{t("resources.detail.searchEmpty")}</p> : null}
        </aside>

        <article className="panel course-main">
          <div className="course-main-toolbar" aria-live="polite">
            <span className="course-toolbar-pill">
              {t("resources.detail.lessonStep", { current: lessonNumber, total: allLessons.length })}
            </span>
            <span className="course-toolbar-pill course-toolbar-pill-muted">
              {t("resources.progressLabel", { percent: progress.progress_percent })}
            </span>
          </div>

          <div className="course-main-body">
            {lesson ? (
              <LessonContent
                resourceId={resource.id}
                lesson={lesson}
                allLessons={allLessons}
                completed={completed}
                onNavigate={setLessonId}
              />
            ) : (
              <p className="lesson-search-empty">{t("resources.noLessons")}</p>
            )}

            <section className="course-info-strip">
              <ul className="meta-list">
                <li>
                  <strong>{t("resources.detail.meta.category")}</strong> {resource.category}
                </li>
                <li>
                  <strong>{t("resources.detail.meta.level")}</strong>{" "}
                  {resource.level ?? t("resources.detail.notSpecified")}
                </li>
                <li>
                  <strong>{t("resources.detail.meta.duration")}</strong>{" "}
                  {resource.estimated_duration_minutes
                    ? t("resources.minutes", { count: resource.estimated_duration_minutes })
                    : t("resources.detail.notAvailable")}
                </li>
                <li>
                  <strong>{t("resources.detail.meta.modules")}</strong> {resource.modules.length}
                </li>
                <li>
                  <strong>{t("resources.detail.meta.lessons")}</strong> {allLessons.length}
                </li>
                <li>
                  <strong>{t("resources.detail.meta.progress")}</strong> {progress.progress_percent}%
                </li>
              </ul>
              {resource.external_url ? (
                <a
                  href={resource.external_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="open-resource"
                >
                  {t("resources.openResource")}
                </a>
              ) : null}
            </section>
          </div>
        </article>
      </section>
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
    <>
      <div className="lesson-head">
        <h3 className="lesson-title">{lesson.title}</h3>
        {lesson.notes ? <div className="lesson-subtitle">{lesson.notes}</div> : null}
      </div>

      <div className="lesson-content">
        <LessonBody lesson={lesson} />
      </div>

      {lesson.content_type === "resume_upload" ? null : (
        <div className="lesson-action-bar">
          <button
            type="button"
            className="lesson-complete-btn"
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
          </button>
          {mutation.isError ? (
            <p className="lesson-action-note">
              <Alert tone="danger">{t("resources.progressError")}</Alert>
            </p>
          ) : null}
        </div>
      )}
    </>
  );
}

function LessonBody({ lesson }: { lesson: Lesson }) {
  const { t } = useTranslation();

  if (lesson.content_type === "resume_upload") {
    return <ResumeAuditWidget />;
  }

  if (lesson.content_type === "video_url" && lesson.video_url) {
    const embedUrl = toEmbedUrl(lesson.video_url);
    if (!embedUrl) return <p>{t("resources.invalidVideo")}</p>;
    return (
      <div className="lesson-video">
        <div className="lesson-video-frame">
          <iframe
            src={embedUrl}
            title={lesson.title}
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
      <div className="lesson-external">
        <p>{t("resources.externalResourceIntro")}</p>
        <a href={lesson.resource_url} target="_blank" rel="noopener noreferrer" className="open-resource">
          {t("resources.openResource")}
        </a>
      </div>
    );
  }

  // `html`-typed content is authored by admins, but this app has no HTML
  // sanitizer on the frontend; rendering it as text (React escapes it) is the
  // safe default until one is added, even though it loses formatting for that
  // one lesson type. Plain-text lessons render the same way.
  return <p className="lesson-text">{lesson.content}</p>;
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
