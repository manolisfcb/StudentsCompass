import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import {
  Badge,
  Card,
  EmptyState,
  Icon,
  Input,
  PageHeader,
  Select,
  Tabs,
  toIconName,
  type TabItem,
} from "@/components/ui";
import { fetchResources, type Resource } from "@/features/resources-roadmaps/api";

/**
 * The resources hub: one fetch, then client-side category/search filtering
 * over the fixed result set — the legacy page never re-queries the API on a
 * filter change, so this keeps the same shape rather than adding a query per
 * keystroke.
 */
export function ResourcesListPage() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: queryKeys.resources.list, queryFn: fetchResources });

  return (
    <div className="flex flex-col gap-6">
      <DocumentMeta title={t("resources.seoTitle")} description={t("resources.seoDescription")} path="/resources" />
      <PageHeader title={t("resources.title")} description={t("resources.subtitle")} />
      <AsyncBoundary query={query}>{(resources) => <ResourceBrowser resources={resources} />}</AsyncBoundary>
    </div>
  );
}

type SortKey = "recent" | "name" | "duration";

function ResourceBrowser({ resources }: { resources: Resource[] }) {
  const { t } = useTranslation();
  const [category, setCategory] = useState("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortKey>("recent");

  const categories = useMemo(
    () => Array.from(new Set(resources.map((resource) => resource.category))).sort(),
    [resources],
  );

  // Counts on the filters turn a blind guess into a decision — you can see
  // there are two Career courses before spending a click to find out.
  const tabs: TabItem[] = useMemo(
    () => [
      { value: "all", label: t("resources.allCategories"), count: resources.length },
      ...categories.map((value) => ({
        value,
        label: value,
        count: resources.filter((resource) => resource.category === value).length,
      })),
    ],
    [categories, resources, t],
  );

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    const matches = resources.filter((resource) => {
      if (category !== "all" && resource.category !== category) return false;
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
        return (
          (left.estimated_duration_minutes ?? Number.MAX_SAFE_INTEGER) -
          (right.estimated_duration_minutes ?? Number.MAX_SAFE_INTEGER)
        );
      }
      return right.created_at.localeCompare(left.created_at);
    });
  }, [resources, category, search, sort]);

  return (
    <div className="flex flex-col gap-5">
      {/* Filters sit on the canvas rather than in a card of their own. The
        * ported page wrapped them in a white panel, which read as content and
        * pushed the actual results below the fold. */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Tabs items={tabs} value={category} onChange={setCategory} label={t("resources.title")} className="sm:flex-1" />
        <div className="flex gap-2">
          <Input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t("resources.searchPlaceholder")}
            aria-label={t("resources.searchPlaceholder")}
            className="sm:w-56"
          />
          <Select
            value={sort}
            onChange={(event) => setSort(event.target.value as SortKey)}
            aria-label={t("resources.sortLabel")}
            className="w-auto"
          >
            <option value="recent">{t("resources.sort.recent")}</option>
            <option value="name">{t("resources.sort.name")}</option>
            <option value="duration">{t("resources.sort.duration")}</option>
          </Select>
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState title={t("resources.empty")} icon="book" />
      ) : (
        <section aria-label={t("resources.title")}>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {filtered.map((resource) => (
              <ResourceCard key={resource.id} resource={resource} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function ResourceCard({ resource }: { resource: Resource }) {
  const { t } = useTranslation();

  return (
    <Card padding="none" className="flex flex-col">
      <div className="flex flex-1 flex-col gap-3 p-4">
        <div className="flex items-start gap-3">
          <span
            aria-hidden="true"
            className="flex size-9 shrink-0 items-center justify-center rounded-md bg-primary-subtle text-primary"
          >
            <Icon name={toIconName(resource.icon, "book")} size={18} />
          </span>
          <div className="min-w-0 flex-1">
            <h3 className="text-card-title text-ink">{resource.title}</h3>
            {/* Two lines, so a long description cannot make one card in a row
              * twice the height of its neighbours. */}
            <p className="mt-1 line-clamp-2 text-body-sm text-ink-soft">{resource.description}</p>
          </div>
        </div>

        {/* The ported card rendered its category, level and duration as pills
          * and then repeated the same words again as tags underneath. One row,
          * deduplicated against what is already shown above it. */}
        <div className="mt-auto flex flex-wrap gap-1.5">
          {resource.is_locked ? <Badge tone="warning">{t("resources.locked")}</Badge> : null}
          <Badge tone="brand">{resource.category}</Badge>
          {resource.level ? <Badge>{resource.level}</Badge> : null}
          {resource.estimated_duration_minutes ? (
            <Badge>{t("resources.minutes", { count: resource.estimated_duration_minutes })}</Badge>
          ) : null}
          {(resource.tags ?? [])
            .filter(
              (tag) =>
                tag.toLowerCase() !== resource.category.toLowerCase() &&
                tag.toLowerCase() !== (resource.level ?? "").toLowerCase(),
            )
            .map((tag) => (
              <Badge key={tag}>{tag}</Badge>
            ))}
        </div>
      </div>

      <div className="border-t border-border p-3">
        {resource.is_locked ? (
          <button
            type="button"
            disabled
            aria-disabled="true"
            className="flex h-9 w-full items-center justify-center rounded-md bg-surface-subtle text-body-sm font-medium text-ink-muted"
          >
            {t("resources.accessLocked")}
          </button>
        ) : (
          <Link
            to={`/resources/${resource.id}`}
            aria-label={t("resources.openCourseNamed", { title: resource.title })}
            className="flex h-9 w-full items-center justify-center rounded-md bg-primary text-body-sm font-medium text-primary-fg transition-colors hover:bg-primary-hover"
          >
            {t("resources.openCourse")}
          </Link>
        )}
      </div>
    </Card>
  );
}
