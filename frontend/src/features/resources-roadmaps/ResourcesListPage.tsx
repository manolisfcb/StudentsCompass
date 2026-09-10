import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { EmptyState } from "@/components/patterns/EmptyState";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { fetchResources, type Resource } from "@/features/resources-roadmaps/api";

/**
 * The resources hub (`resources.html`/`resources.js`): one fetch, then
 * client-side category/search filtering over the fixed result set — the
 * legacy page never re-queries the API on a filter change, only server-renders
 * once, so this keeps the same shape rather than adding a query per keystroke.
 */
export function ResourcesListPage() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: queryKeys.resources.list, queryFn: fetchResources });

  return (
    <div className="space-y-6">
      <DocumentMeta
        title={t("resources.seoTitle")}
        description={t("resources.seoDescription")}
        path="/resources"
      />
      <h1 className="text-2xl font-bold text-ink">{t("resources.title")}</h1>
      <AsyncBoundary query={query}>{(resources) => <ResourceBrowser resources={resources} />}</AsyncBoundary>
    </div>
  );
}

function ResourceBrowser({ resources }: { resources: Resource[] }) {
  const { t } = useTranslation();
  const [category, setCategory] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const categories = useMemo(
    () => Array.from(new Set(resources.map((resource) => resource.category))).sort(),
    [resources],
  );

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return resources.filter((resource) => {
      if (category && resource.category !== category) return false;
      if (!term) return true;
      return (
        resource.title.toLowerCase().includes(term) || resource.description.toLowerCase().includes(term)
      );
    });
  }, [resources, category, search]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={t("resources.searchPlaceholder")}
          aria-label={t("resources.searchPlaceholder")}
          className="w-full max-w-xs rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-muted focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
        />
        <div className="flex flex-wrap gap-2">
          <CategoryChip label={t("resources.allCategories")} active={category === null} onClick={() => setCategory(null)} />
          {categories.map((value) => (
            <CategoryChip key={value} label={value} active={category === value} onClick={() => setCategory(value)} />
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState title={t("resources.empty")} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((resource) => (
            <ResourceCard key={resource.id} resource={resource} />
          ))}
        </div>
      )}
    </div>
  );
}

function CategoryChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
        active ? "bg-brand text-white" : "border border-border text-ink-soft hover:bg-canvas"
      }`}
    >
      {label}
    </button>
  );
}

function ResourceCard({ resource }: { resource: Resource }) {
  const { t } = useTranslation();
  const content = (
    <article
      className={`h-full rounded-lg border border-border bg-surface p-5 ${
        resource.is_locked ? "opacity-60" : "hover:border-brand"
      }`}
    >
      <div className="flex items-center justify-between">
        <span aria-hidden="true" className="text-2xl">
          {resource.icon ?? "📘"}
        </span>
        {resource.is_locked ? (
          <span className="text-xs font-medium text-ink-muted">{t("resources.locked")}</span>
        ) : null}
      </div>
      <h2 className="mt-2 font-semibold text-ink">{resource.title}</h2>
      <p className="mt-1 text-sm text-ink-soft">{resource.description}</p>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-ink-muted">
        <span>{resource.category}</span>
        {resource.level ? <span>· {resource.level}</span> : null}
        {resource.estimated_duration_minutes ? <span>· {resource.estimated_duration_minutes} min</span> : null}
      </div>
    </article>
  );

  if (resource.is_locked) return content;
  return (
    <Link to={`/resources/${resource.id}`} className="block h-full">
      {content}
    </Link>
  );
}
