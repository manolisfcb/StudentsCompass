import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { EmptyState } from "@/components/patterns/EmptyState";
import { FormField, INPUT_CLASS } from "@/components/patterns/FormField";
import { DocumentMeta } from "@/components/seo/DocumentMeta";

import { apiRequest } from "@/api/client";
import { fetchCommunities, type Community } from "@/features/community-messages/api";

const QUERY_KEY = ["communities"];

/** `community.html`/`community.js`: one fetch, client-side search. `member_count` is read as-is, never incremented locally. */
export function CommunitiesListPage() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: QUERY_KEY, queryFn: () => fetchCommunities() });
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);

  return (
    <div className="space-y-6">
      <DocumentMeta
        title={t("community.list.seoTitle")}
        description={t("community.list.seoDescription")}
        path="/community"
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-ink">{t("community.list.title")}</h1>
        <Button onClick={() => setCreating((value) => !value)}>
          {creating ? t("community.list.cancel") : t("community.list.create")}
        </Button>
      </div>

      {creating ? <CreateCommunityForm onDone={() => setCreating(false)} /> : null}

      <input
        type="search"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder={t("community.list.searchPlaceholder")}
        aria-label={t("community.list.searchPlaceholder")}
        className={`${INPUT_CLASS} max-w-sm`}
      />

      <AsyncBoundary query={query}>{(communities) => <CommunityGrid communities={communities} search={search} />}</AsyncBoundary>
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

  if (filtered.length === 0) return <EmptyState title={t("community.list.empty")} />;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {filtered.map((community) => (
        <Link
          key={community.id}
          to={`/community/${community.id}`}
          className="block rounded-lg border border-border bg-surface p-5 hover:border-brand"
        >
          <div className="flex items-center gap-2">
            <span aria-hidden="true" className="text-2xl">
              {community.icon ?? "👥"}
            </span>
            <h2 className="font-semibold text-ink">{community.name}</h2>
          </div>
          {community.description ? <p className="mt-2 text-sm text-ink-soft">{community.description}</p> : null}
          <p className="mt-3 text-xs text-ink-muted">
            {t("community.list.memberCount", { count: community.member_count })}
          </p>
        </Link>
      ))}
    </div>
  );
}

function CreateCommunityForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [icon, setIcon] = useState("👥");

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
    <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-border bg-surface p-4">
      {mutation.isError ? (
        <Alert tone="danger">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("community.list.createError")}
        </Alert>
      ) : null}
      <div className="grid gap-4 sm:grid-cols-[auto_1fr]">
        <FormField label={t("community.list.form.icon")}>
          <input
            value={icon}
            onChange={(event) => setIcon(event.target.value)}
            maxLength={4}
            className={`${INPUT_CLASS} w-16 text-center text-xl`}
          />
        </FormField>
        <FormField label={t("community.list.form.name")}>
          <input required value={name} onChange={(event) => setName(event.target.value)} className={INPUT_CLASS} />
        </FormField>
      </div>
      <FormField label={t("community.list.form.description")}>
        <textarea
          rows={3}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          className={INPUT_CLASS}
        />
      </FormField>
      <div className="flex gap-2">
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? t("community.list.creating") : t("community.list.createSubmit")}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          {t("community.list.cancel")}
        </Button>
      </div>
    </form>
  );
}
