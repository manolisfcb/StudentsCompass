import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  FormField,
  Icon,
  Input,
  PageHeader,
  Textarea,
  toIconName,
  type IconName,
} from "@/components/ui";

import { apiRequest } from "@/api/client";
import { cn } from "@/lib/cn";
import { fetchCommunities, type Community } from "@/features/community-messages/api";

const QUERY_KEY = ["communities"];

/** `community.html`/`community.js`: one fetch, client-side search. `member_count` is read as-is, never incremented locally. */
export function CommunitiesListPage() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: QUERY_KEY, queryFn: () => fetchCommunities() });
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);

  return (
    <div className="flex flex-col gap-6">
      <DocumentMeta
        title={t("community.list.seoTitle")}
        description={t("community.list.seoDescription")}
        path="/community"
      />

      <PageHeader
        title={t("community.list.title")}
        description={t("community.list.subtitle")}
        actions={
          <div className="flex gap-2">
            <Input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t("community.list.searchPlaceholder")}
              aria-label={t("community.list.searchPlaceholder")}
              className="sm:w-56"
            />
            <Button variant={creating ? "outline" : "primary"} onClick={() => setCreating((value) => !value)}>
              {creating ? t("community.list.cancel") : t("community.list.create")}
            </Button>
          </div>
        }
      />

      {creating ? (
        <Card>
          <CreateCommunityForm onDone={() => setCreating(false)} />
        </Card>
      ) : null}

      <AsyncBoundary query={query}>
        {(communities) => <CommunityGrid communities={communities} search={search} />}
      </AsyncBoundary>
    </div>
  );
}

function CommunityGrid({ communities, search }: { communities: Community[]; search: string }) {
  const { t } = useTranslation();
  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return communities;
    return communities.filter(
      (community) =>
        community.name.toLowerCase().includes(term) || (community.description ?? "").toLowerCase().includes(term),
    );
  }, [communities, search]);

  if (filtered.length === 0) {
    return <EmptyState title={t("community.list.empty")} icon="users" />;
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {filtered.map((community) => (
        <Card key={community.id} className="flex flex-col gap-3">
          <div className="flex items-start gap-3">
            <span
              aria-hidden="true"
              className="flex size-9 shrink-0 items-center justify-center rounded-md bg-primary-subtle text-primary"
            >
              <Icon name={toIconName(community.icon, "users")} size={18} />
            </span>
            <div className="min-w-0 flex-1">
              <h3 className="truncate text-card-title text-ink">{community.name}</h3>
              <p className="mt-0.5 line-clamp-2 text-body-sm text-ink-soft">
                {community.description ?? t("community.list.noDescription")}
              </p>
            </div>
          </div>

          <Badge className="self-start">{t("community.list.memberCount", { count: community.member_count })}</Badge>

          <Link to={`/community/${community.id}`} className="mt-auto">
            <Button variant="outline" size="sm" block>
              {t("community.list.view", { name: community.name })}
            </Button>
          </Link>
        </Card>
      ))}
    </div>
  );
}

/**
 * What a community may be marked with. Each key is written out in full rather
 * than built from the icon name, so a search for the key finds this table.
 */
const ICON_CHOICES: { name: IconName; labelKey: string }[] = [
  { name: "users", labelKey: "community.list.form.iconOption.users" },
  { name: "message", labelKey: "community.list.form.iconOption.message" },
  { name: "code", labelKey: "community.list.form.iconOption.code" },
  { name: "chart", labelKey: "community.list.form.iconOption.chart" },
  { name: "design", labelKey: "community.list.form.iconOption.design" },
  { name: "book", labelKey: "community.list.form.iconOption.book" },
  { name: "briefcase", labelKey: "community.list.form.iconOption.briefcase" },
  { name: "target", labelKey: "community.list.form.iconOption.target" },
];

function CreateCommunityForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [icon, setIcon] = useState<IconName>("users");

  const mutation = useMutation({
    mutationFn: () =>
      apiRequest<Community>("/api/v1/communities", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description: description || null, icon }),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      onDone();
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      {mutation.isError ? (
        <Alert tone="danger">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("community.list.createError")}
        </Alert>
      ) : null}

      <FormField label={t("community.list.form.name")} required>
        <Input id="community-name" value={name} onChange={(event) => setName(event.target.value)} />
      </FormField>

      <FormField label={t("community.list.form.description")}>
        <Textarea
          id="community-description"
          rows={3}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      </FormField>

      <FormField label={t("community.list.form.icon")}>
        {/* This was a four-character text box you typed an emoji into, which
          * is how the seeded communities ended up each carrying a different
          * platform's glyph. A fixed set of choices is the only way the grid
          * stays one icon family, and it retires a free-text field that had
          * no correct answer. */}
        <div role="radiogroup" aria-label={t("community.list.form.icon")} className="flex flex-wrap gap-2">
          {ICON_CHOICES.map((choice) => (
            <button
              key={choice.name}
              type="button"
              role="radio"
              aria-checked={icon === choice.name}
              aria-label={t(choice.labelKey)}
              title={t(choice.labelKey)}
              onClick={() => setIcon(choice.name)}
              className={cn(
                "flex size-10 items-center justify-center rounded-md border transition-colors",
                icon === choice.name
                  ? "border-primary bg-primary-subtle text-primary"
                  : "border-border text-ink-muted hover:border-border-strong hover:text-ink",
              )}
            >
              <Icon name={choice.name} size={18} />
            </button>
          ))}
        </div>
      </FormField>

      <Button type="submit" className="self-start" loading={mutation.isPending}>
        {mutation.isPending ? t("community.list.creating") : t("community.list.createSubmit")}
      </Button>
    </form>
  );
}
