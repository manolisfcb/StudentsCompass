import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { PageScope } from "@/components/layout/PageScope";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
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
    <PageScope name="community" className="communities-container">
      <DocumentMeta
        title={t("community.list.seoTitle")}
        description={t("community.list.seoDescription")}
        path="/community"
      />

      <div className="communities-header page-shell-header">
        <div className="communities-header-row page-shell-header-row">
          <div className="page-shell-header-copy">
            <h2>{t("community.list.title")}</h2>
            <p>{t("community.list.subtitle")}</p>
          </div>
          <button type="button" className="create-community-btn" onClick={() => setCreating((value) => !value)}>
            {creating ? t("community.list.cancel") : t("community.list.create")}
          </button>
        </div>
      </div>

      {creating ? <CreateCommunityForm onDone={() => setCreating(false)} /> : null}

      <div className="filter-bar">
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={t("community.list.searchPlaceholder")}
          aria-label={t("community.list.searchPlaceholder")}
        />
      </div>

      <AsyncBoundary query={query}>{(communities) => <CommunityGrid communities={communities} search={search} />}</AsyncBoundary>
    </PageScope>
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
    return (
      <div className="empty-state">
        <p>{t("community.list.empty")}</p>
      </div>
    );
  }

  return (
    <div className="communities-grid">
      {filtered.map((community) => (
        <article key={community.id} className="community-card">
          <div className="community-icon" aria-hidden="true">
            {community.icon ?? "👥"}
          </div>
          <h3 className="community-title">{community.name}</h3>
          <p className="community-description">{community.description ?? t("community.list.noDescription")}</p>
          <div className="community-stats">
            <div className="stat-item">
              <span>{t("community.list.memberCount", { count: community.member_count })}</span>
            </div>
          </div>
          <Link to={`/community/${community.id}`} className="join-btn">
            {t("community.list.view", { name: community.name })}
          </Link>
        </article>
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
    <form onSubmit={handleSubmit} className="community-form">
      {mutation.isError ? (
        <p className="form__error" role="alert">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("community.list.createError")}
        </p>
      ) : null}

      <div className="form__group">
        <label className="form__label" htmlFor="community-name">
          {t("community.list.form.name")}
        </label>
        <input
          id="community-name"
          className="form__field"
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </div>

      <div className="form__group">
        <label className="form__label" htmlFor="community-description">
          {t("community.list.form.description")}
        </label>
        <textarea
          id="community-description"
          className="form__field"
          rows={3}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      </div>

      <div className="form__group">
        <label className="form__label" htmlFor="community-icon">
          {t("community.list.form.icon")}
        </label>
        <div className="icon-input">
          <div className="icon-input__group">
            <span className="icon-input__preview" aria-hidden="true">
              {icon || "👥"}
            </span>
            <input
              id="community-icon"
              className="icon-input__field"
              value={icon}
              maxLength={4}
              onChange={(event) => setIcon(event.target.value)}
            />
          </div>
        </div>
      </div>

      <div className="modal__footer">
        <button type="submit" className="primary-btn" disabled={mutation.isPending}>
          {mutation.isPending ? t("community.list.creating") : t("community.list.createSubmit")}
        </button>
      </div>
    </form>
  );
}
