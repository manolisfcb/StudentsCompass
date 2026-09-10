import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { EmptyState } from "@/components/patterns/EmptyState";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { fetchRoadmaps, fetchSavedRoadmaps, type Roadmap, type SavedRoadmap } from "@/features/resources-roadmaps/api";

export function RoadmapsListPage() {
  const { t } = useTranslation();
  const roadmapsQuery = useQuery({ queryKey: queryKeys.roadmaps.list, queryFn: fetchRoadmaps });
  const savedQuery = useQuery({ queryKey: queryKeys.roadmaps.saved, queryFn: fetchSavedRoadmaps });

  return (
    <div className="space-y-10">
      <DocumentMeta title={t("roadmaps.seoTitle")} description={t("roadmaps.seoDescription")} path="/roadmaps" />
      <h1 className="text-2xl font-bold text-ink">{t("roadmaps.title")}</h1>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-ink">{t("roadmaps.saved.title")}</h2>
        <AsyncBoundary query={savedQuery}>
          {(saved) =>
            saved.length === 0 ? (
              <EmptyState title={t("roadmaps.saved.empty")} />
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {saved.map((item) => (
                  <SavedRoadmapCard key={item.roadmap.slug} saved={item} />
                ))}
              </div>
            )
          }
        </AsyncBoundary>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-ink">{t("roadmaps.browse.title")}</h2>
        <AsyncBoundary query={roadmapsQuery}>
          {(roadmaps) => (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {roadmaps.map((roadmap) => (
                <RoadmapCard key={roadmap.slug} roadmap={roadmap} />
              ))}
            </div>
          )}
        </AsyncBoundary>
      </section>
    </div>
  );
}

function RoadmapCard({ roadmap }: { roadmap: Roadmap }) {
  const { t } = useTranslation();
  return (
    <Link
      to={`/roadmaps/${roadmap.slug}`}
      className="block rounded-lg border border-border bg-surface p-5 hover:border-brand"
    >
      <h3 className="font-semibold text-ink">{roadmap.title}</h3>
      <p className="mt-1 text-sm text-ink-soft">{roadmap.description}</p>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-ink-muted">
        <span>{roadmap.difficulty}</span>
        <span>
          · {roadmap.duration_weeks_min}–{roadmap.duration_weeks_max} {t("roadmaps.weeks")}
        </span>
        <span>· {t("roadmaps.saveCount", { count: roadmap.popularity })}</span>
      </div>
      {roadmap.total_tasks > 0 ? (
        <p className="mt-2 text-xs text-ink-muted">
          {t("roadmaps.progress", { percent: roadmap.overall_progress_percent })}
        </p>
      ) : null}
    </Link>
  );
}

function SavedRoadmapCard({ saved }: { saved: SavedRoadmap }) {
  const { t } = useTranslation();
  const { roadmap } = saved;
  return (
    <Link
      to={`/roadmaps/${roadmap.slug}`}
      className="block rounded-lg border border-border bg-surface p-5 hover:border-brand"
    >
      <h3 className="font-semibold text-ink">{roadmap.title}</h3>
      <p className="mt-2 text-sm text-ink-soft">
        {t("roadmaps.tasksCompleted", { completed: roadmap.completed_tasks, total: roadmap.total_tasks })}
      </p>
      <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-border">
        <div className="h-full bg-brand" style={{ width: `${roadmap.overall_progress_percent}%` }} />
      </div>
    </Link>
  );
}
