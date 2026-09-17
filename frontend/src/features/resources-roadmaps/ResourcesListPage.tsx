import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { PageScope } from "@/components/layout/PageScope";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { fetchResources, type Resource } from "@/features/resources-roadmaps/api";

/**
 * The resources hub (`resources.html`/`resources.js`): one fetch, then
 * client-side category/search filtering over the fixed result set — the
 * legacy page never re-queries the API on a filter change, only server-renders
 * once, so this keeps the same shape rather than adding a query per keystroke.
 *
 * Markup and classes are the template's (`.resources-container`,
 * `.filter-bar > .filter-chip`, `.control-bar`, `.resources-grid` of
 * `.resource-card`s), which is what `resources.css` styles.
 */
export function ResourcesListPage() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: queryKeys.resources.list, queryFn: fetchResources });

  return (
    <PageScope name="resources">
      <DocumentMeta
        title={t("resources.seoTitle")}
        description={t("resources.seoDescription")}
        path="/resources"
      />
      <div className="resources-container">
        <div className="resources-header page-shell-header">
          <div className="resources-header-row page-shell-header-row">
            <div className="page-shell-header-copy">
              <h2>{t("resources.title")}</h2>
              <p>{t("resources.subtitle")}</p>
            </div>
          </div>
        </div>
        <AsyncBoundary query={query}>{(resources) => <ResourceBrowser resources={resources} />}</AsyncBoundary>
      </div>
    </PageScope>
  );
}

type SortKey = "recent" | "name" | "duration";

function ResourceBrowser({ resources }: { resources: Resource[] }) {
  const { t } = useTranslation();
  const [category, setCategory] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortKey>("recent");

  const categories = useMemo(
    () => Array.from(new Set(resources.map((resource) => resource.category))).sort(),
    [resources],
  );

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    const matches = resources.filter((resource) => {
      if (category && resource.category !== category) return false;
      if (!term) return true;
      return (
        resource.title.toLowerCase().includes(term) ||
        resource.description.toLowerCase().includes(term) ||
        (resource.tags ?? []).some((tag) => tag.toLowerCase().includes(term))
      );
    });

    // Same three orders the `#resource-sort` control offered.
    return [...matches].sort((left, right) => {
      if (sort === "name") return left.title.localeCompare(right.title);
      if (sort === "duration") {
        return (left.estimated_duration_minutes ?? Number.MAX_SAFE_INTEGER) -
          (right.estimated_duration_minutes ?? Number.MAX_SAFE_INTEGER);
      }
      return right.created_at.localeCompare(left.created_at);
    });
  }, [resources, category, search, sort]);

  return (
    <>
      <div className="filter-bar">
        <button
          type="button"
          className={`filter-chip${category === null ? " active" : ""}`}
          onClick={() => setCategory(null)}
        >
          {t("resources.allCategories")}
        </button>
        {categories.map((value) => (
          <button
            key={value}
            type="button"
            className={`filter-chip${category === value ? " active" : ""}`}
            onClick={() => setCategory(value)}
          >
            {value}
          </button>
        ))}
      </div>

      <div className="control-bar">
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={t("resources.searchPlaceholder")}
          aria-label={t("resources.searchPlaceholder")}
        />
        <select
          value={sort}
          onChange={(event) => setSort(event.target.value as SortKey)}
          aria-label={t("resources.sortLabel")}
        >
          <option value="recent">{t("resources.sort.recent")}</option>
          <option value="name">{t("resources.sort.name")}</option>
          <option value="duration">{t("resources.sort.duration")}</option>
        </select>
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state">{t("resources.empty")}</div>
      ) : (
        <section className="resource-group" aria-label={t("resources.title")}>
          <div className="resources-grid resources-grid-group">
            {filtered.map((resource) => (
              <ResourceCard key={resource.id} resource={resource} />
            ))}
          </div>
        </section>
      )}
    </>
  );
}

function ResourceCard({ resource }: { resource: Resource }) {
  const { t } = useTranslation();
  return (
    <article className={`resource-card${resource.is_locked ? " resource-card-locked" : ""}`}>
      <div className="resource-icon" aria-hidden="true">
        {resource.icon ?? "📚"}
      </div>
      <h3 className="resource-title">{resource.title}</h3>
      <p className="resource-description">{resource.description}</p>
      <div className="resource-meta">
        {resource.is_locked ? <span className="meta-pill meta-pill-locked">{t("resources.locked")}</span> : null}
        <span className="meta-pill">{resource.category}</span>
        {resource.level ? <span className="meta-pill">{resource.level}</span> : null}
        {resource.estimated_duration_minutes ? (
          <span className="meta-pill">{t("resources.minutes", { count: resource.estimated_duration_minutes })}</span>
        ) : null}
      </div>
      {resource.tags && resource.tags.length > 0 ? (
        <div className="resource-tags">
          {resource.tags.map((tag) => (
            <span key={tag} className="tag">
              {tag}
            </span>
          ))}
        </div>
      ) : null}
      {resource.is_locked ? (
        <button type="button" className="resource-open-btn resource-open-btn-locked" disabled aria-disabled="true">
          {t("resources.accessLocked")}
        </button>
      ) : (
        <Link
          className="resource-open-btn"
          to={`/resources/${resource.id}`}
          aria-label={t("resources.openCourseNamed", { title: resource.title })}
        >
          {t("resources.openCourse")}
        </Link>
      )}
    </article>
  );
}
