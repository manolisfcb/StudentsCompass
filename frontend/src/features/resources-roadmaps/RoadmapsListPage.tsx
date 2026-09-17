import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { Badge, Card, EmptyState, Input, PageHeader, ProgressBar, SectionHeader, Select } from "@/components/ui";
import { fetchRoadmaps, fetchSavedRoadmaps, type Roadmap, type SavedRoadmap } from "@/features/resources-roadmaps/api";

/**
 * The roadmap catalogue: the saved rail on top, then the in-demand three and
 * the full browse grid. All three are the same `Card` — they were three
 * different ones (`.saved-card`, `.demand-card`, `.roadmap-card`) for three
 * views of the same object.
 *
 * The toolbar filtered server-side in the template (`<form method="get">`);
 * here it filters the one fetched list, because the API answers the whole
 * catalogue in a single call and a round trip per keystroke would be a
 * regression, not a port.
 */
export function RoadmapsListPage() {
  const { t } = useTranslation();
  const roadmapsQuery = useQuery({ queryKey: queryKeys.roadmaps.list, queryFn: fetchRoadmaps });
  const savedQuery = useQuery({ queryKey: queryKeys.roadmaps.saved, queryFn: fetchSavedRoadmaps });
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"most_saved" | "newest">("most_saved");

  return (
    <div className="flex flex-col gap-6">
      <DocumentMeta title={t("roadmaps.seoTitle")} description={t("roadmaps.seoDescription")} path="/roadmaps" />

      <PageHeader
        title={t("roadmaps.title")}
        description={t("roadmaps.subtitle")}
        actions={
          <div className="flex gap-2">
            <Input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t("roadmaps.searchPlaceholder")}
              aria-label={t("roadmaps.searchPlaceholder")}
              className="sm:w-56"
            />
            <Select
              value={sort}
              onChange={(event) => setSort(event.target.value as "most_saved" | "newest")}
              aria-label={t("roadmaps.sortLabel")}
              className="w-auto"
            >
              <option value="most_saved">{t("roadmaps.sort.mostSaved")}</option>
              <option value="newest">{t("roadmaps.sort.newest")}</option>
            </Select>
          </div>
        }
      />

      <section className="flex flex-col gap-4">
        <SectionHeader title={t("roadmaps.saved.title")} description={t("roadmaps.saved.subtitle")} />
        <AsyncBoundary query={savedQuery}>
          {(saved) =>
            saved.length === 0 ? (
              <EmptyState title={t("roadmaps.saved.empty")} description={t("roadmaps.saved.emptyHint")} icon="🧭" />
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {saved.map((item) => (
                  <SavedRoadmapCard key={item.roadmap.slug} saved={item} />
                ))}
              </div>
            )
          }
        </AsyncBoundary>
      </section>

      <AsyncBoundary query={roadmapsQuery}>
        {(roadmaps) => <RoadmapSections roadmaps={roadmaps} search={search} sort={sort} />}
      </AsyncBoundary>
    </div>
  );
}

const DEMAND_ICONS: Record<string, string> = {
  "web-developer": "💻",
  "data-scientist": "📊",
  "product-manager": "🎯",
};

function RoadmapSections({
  roadmaps,
  search,
  sort,
}: {
  roadmaps: Roadmap[];
  search: string;
  sort: "most_saved" | "newest";
}) {
  const { t } = useTranslation();
  const visible = useMemo(() => {
    const term = search.trim().toLowerCase();
    const matches = roadmaps.filter(
      (roadmap) =>
        !term ||
        roadmap.title.toLowerCase().includes(term) ||
        (roadmap.description ?? "").toLowerCase().includes(term),
    );
    return [...matches].sort((left, right) =>
      sort === "newest" ? right.slug.localeCompare(left.slug) : right.popularity - left.popularity,
    );
  }, [roadmaps, search, sort]);

  return (
    <>
      <section className="flex flex-col gap-4">
        <SectionHeader title={t("roadmaps.inDemand.title")} description={t("roadmaps.inDemand.subtitle")} />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {visible.slice(0, 3).map((roadmap) => (
            <DemandCard key={roadmap.slug} roadmap={roadmap} icon={DEMAND_ICONS[roadmap.slug] ?? "🧭"} />
          ))}
        </div>
      </section>

      <section className="mt-6 flex flex-col gap-4">
        <SectionHeader title={t("roadmaps.browse.title")} description={t("roadmaps.browse.subtitle")} />
        {visible.length === 0 ? (
          <EmptyState title={t("roadmaps.browse.empty")} icon="🔍" />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {visible.map((roadmap) => (
              <DemandCard key={roadmap.slug} roadmap={roadmap} />
            ))}
          </div>
        )}
      </section>
    </>
  );
}

function DemandCard({ roadmap, icon }: { roadmap: Roadmap; icon?: string }) {
  const { t } = useTranslation();
  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        {icon ? (
          <span
            aria-hidden="true"
            className="flex size-9 shrink-0 items-center justify-center rounded-md bg-primary-subtle text-lg"
          >
            {icon}
          </span>
        ) : null}
        <span className="ml-auto text-caption text-ink-muted">
          {t("roadmaps.saveCount", { count: roadmap.popularity })}
        </span>
        {roadmap.is_saved ? <Badge tone="brand">{t("roadmaps.savedIndicator")}</Badge> : null}
      </div>

      <div className="min-w-0 flex-1">
        <h4 className="text-card-title text-ink">{roadmap.title}</h4>
        <p className="mt-1 line-clamp-2 text-body-sm text-ink-soft">{roadmap.description}</p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <Badge>
          {roadmap.duration_weeks_min}-{roadmap.duration_weeks_max} {t("roadmaps.weeks")}
        </Badge>
        <Badge>{roadmap.difficulty}</Badge>
      </div>
      {/* The template made the whole `.demand-card` clickable with a JS
          `data-href`, which left the card's only real link reading as a bare
          "Open roadmap" to a screen reader. The label names the roadmap
          instead — same target, an accessible name per card. */}
      <Link
        to={`/roadmaps/${roadmap.slug}`}
        aria-label={t("roadmaps.openRoadmapNamed", { title: roadmap.title })}
        className="mt-auto border-t border-border pt-3 text-body-sm font-medium text-primary transition-colors hover:text-primary-hover"
      >
        {t("roadmaps.openRoadmap")} →
      </Link>
    </Card>
  );
}

function SavedRoadmapCard({ saved }: { saved: SavedRoadmap }) {
  const { t } = useTranslation();
  const { roadmap } = saved;
  return (
    <Card className="flex flex-col gap-3">
      <div className="min-w-0">
        <h4 className="truncate text-card-title text-ink">{roadmap.title}</h4>
        <p className="text-caption text-ink-muted">
          {roadmap.duration_weeks_min}-{roadmap.duration_weeks_max} {t("roadmaps.weeks")} • {roadmap.difficulty}
        </p>
      </div>

      <ProgressBar
        label={t("roadmaps.tasksCompleted", {
          completed: roadmap.completed_tasks,
          total: roadmap.total_tasks,
        })}
        value={roadmap.overall_progress_percent}
      />

      <Link
        to={`/roadmaps/${roadmap.slug}`}
        aria-label={t("roadmaps.continueRoadmapNamed", { title: roadmap.title })}
        className="mt-auto border-t border-border pt-3 text-body-sm font-medium text-primary transition-colors hover:text-primary-hover"
      >
        {t("roadmaps.continueRoadmap")} →
      </Link>
    </Card>
  );
}
