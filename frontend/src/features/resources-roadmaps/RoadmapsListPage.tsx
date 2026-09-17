import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { PageScope } from "@/components/layout/PageScope";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { fetchRoadmaps, fetchSavedRoadmaps, type Roadmap, type SavedRoadmap } from "@/features/resources-roadmaps/api";

/**
 * `roadmaps_list.html` over `roadmaps.css`: the saved rail on top
 * (`.saved-grid` of `.saved-card`s with their progress track), then the
 * in-demand three and the full `.demand-grid`.
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
    <PageScope name="roadmaps">
      <DocumentMeta title={t("roadmaps.seoTitle")} description={t("roadmaps.seoDescription")} path="/roadmaps" />
      <section className="roadmaps-page">
        <div className="roadmaps-hero page-shell-header">
          <div className="page-shell-header-row">
            <div className="page-shell-header-copy">
              <h2>{t("roadmaps.title")}</h2>
              <p>{t("roadmaps.subtitle")}</p>
            </div>
          </div>
        </div>

        <div className="roadmaps-toolbar">
          <div className="toolbar-form">
            <input
              type="search"
              className="toolbar-input"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t("roadmaps.searchPlaceholder")}
              aria-label={t("roadmaps.searchPlaceholder")}
            />
            <select
              className="toolbar-select"
              value={sort}
              onChange={(event) => setSort(event.target.value as "most_saved" | "newest")}
              aria-label={t("roadmaps.sortLabel")}
            >
              <option value="most_saved">{t("roadmaps.sort.mostSaved")}</option>
              <option value="newest">{t("roadmaps.sort.newest")}</option>
            </select>
          </div>
        </div>

        <section className="roadmaps-section">
          <div className="section-heading">
            <h3>{t("roadmaps.saved.title")}</h3>
            <p>{t("roadmaps.saved.subtitle")}</p>
          </div>
          <AsyncBoundary query={savedQuery}>
            {(saved) =>
              saved.length === 0 ? (
                <div className="empty-state">
                  <h4>{t("roadmaps.saved.empty")}</h4>
                  <p>{t("roadmaps.saved.emptyHint")}</p>
                </div>
              ) : (
                <div className="saved-grid">
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
      </section>
    </PageScope>
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
      <section className="roadmaps-section">
        <div className="section-heading">
          <h3>{t("roadmaps.inDemand.title")}</h3>
          <p>{t("roadmaps.inDemand.subtitle")}</p>
        </div>
        <div className="demand-grid">
          {visible.slice(0, 3).map((roadmap) => (
            <DemandCard key={roadmap.slug} roadmap={roadmap} icon={DEMAND_ICONS[roadmap.slug] ?? "🧭"} />
          ))}
        </div>
      </section>

      <section className="roadmaps-section">
        <div className="section-heading">
          <h3>{t("roadmaps.browse.title")}</h3>
          <p>{t("roadmaps.browse.subtitle")}</p>
        </div>
        {visible.length === 0 ? (
          <div className="empty-state">
            <h4>{t("roadmaps.browse.empty")}</h4>
          </div>
        ) : (
          <div className="demand-grid">
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
    <article className="demand-card">
      <div className="demand-header">
        {icon ? (
          <span className="icon-pill" aria-hidden="true">
            {icon}
          </span>
        ) : null}
        <span className="save-count">{t("roadmaps.saveCount", { count: roadmap.popularity })}</span>
        {roadmap.is_saved ? <span className="saved-indicator">{t("roadmaps.savedIndicator")}</span> : null}
      </div>
      <h4>{roadmap.title}</h4>
      <p>{roadmap.description}</p>
      <div className="meta-row">
        <span>
          {roadmap.duration_weeks_min}-{roadmap.duration_weeks_max} {t("roadmaps.weeks")}
        </span>
        <span>{roadmap.difficulty}</span>
      </div>
      {/* The template made the whole `.demand-card` clickable with a JS
          `data-href`, which left the card's only real link reading as a bare
          "Open roadmap" to a screen reader. The label names the roadmap
          instead — same target, an accessible name per card. */}
      <Link
        to={`/roadmaps/${roadmap.slug}`}
        className="card-link"
        aria-label={t("roadmaps.openRoadmapNamed", { title: roadmap.title })}
      >
        {t("roadmaps.openRoadmap")}
      </Link>
    </article>
  );
}

function SavedRoadmapCard({ saved }: { saved: SavedRoadmap }) {
  const { t } = useTranslation();
  const { roadmap } = saved;
  return (
    <article className="saved-card">
      <div className="saved-card-top">
        <h4>{roadmap.title}</h4>
        <span className="progress-chip">{roadmap.overall_progress_percent}%</span>
      </div>
      <p>
        {roadmap.duration_weeks_min}-{roadmap.duration_weeks_max} {t("roadmaps.weeks")} • {roadmap.difficulty}
      </p>
      <div className="progress-track">
        <span className="roadmap-progress-fill" style={{ width: `${roadmap.overall_progress_percent}%` }} />
      </div>
      <small>{t("roadmaps.tasksCompleted", { completed: roadmap.completed_tasks, total: roadmap.total_tasks })}</small>
      <Link
        to={`/roadmaps/${roadmap.slug}`}
        className="card-link"
        aria-label={t("roadmaps.continueRoadmapNamed", { title: roadmap.title })}
      >
        {t("roadmaps.continueRoadmap")}
      </Link>
    </article>
  );
}
