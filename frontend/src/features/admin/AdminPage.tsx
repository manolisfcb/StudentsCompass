import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DataTable, type Column } from "@/components/patterns/DataTable";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import {
  createAdminResource,
  deleteAdminResource,
  deleteAdminUser,
  fetchAdminResource,
  fetchAdminResources,
  fetchAdminStats,
  fetchAdminUsers,
  replaceAdminResource,
  updateAdminResourceState,
  updateAdminUser,
  type AdminResource,
  type AdminResourceCreate,
  type AdminResourceDetail,
  type AdminUser,
} from "@/features/admin/api";
import { ResourceEditor } from "@/features/admin/ResourceEditor";

type Section = "dashboard" | "users" | "resources";
const PAGE_SIZE = 20;

function currentSection(value: string | null): Section {
  return value === "users" || value === "resources" ? value : "dashboard";
}

export function AdminPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const section = currentSection(searchParams.get("section"));
  const sectionTitle = {
    dashboard: t("admin.section.dashboard"),
    users: t("admin.section.users"),
    resources: t("admin.section.resources"),
  }[section];

  return (
    <div className="space-y-6">
      <DocumentMeta title={t("admin.seoTitle")} description={t("admin.seoDescription")} path="/admin" />
      <header>
        <p className="text-xs font-semibold uppercase tracking-widest text-brand-soft">{t("admin.kicker")}</p>
        <h1 className="mt-1 text-2xl font-bold text-white">{sectionTitle}</h1>
      </header>
      {section === "dashboard" ? <AdminDashboard /> : null}
      {section === "users" ? <UsersPanel /> : null}
      {section === "resources" ? <ResourcesPanel /> : null}
    </div>
  );
}

function AdminDashboard() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: queryKeys.admin.stats, queryFn: fetchAdminStats });

  return (
    <AsyncBoundary query={query}>
      {(stats) => (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[
            ["👥", stats.total_users, t("admin.stats.users")],
            ["📚", stats.total_resources, t("admin.stats.resources")],
            ["📄", stats.total_resumes, t("admin.stats.resumes")],
            ["📝", stats.total_questionnaires, t("admin.stats.questionnaires")],
          ].map(([icon, value, label]) => (
            <article key={String(label)} className="rounded-xl border border-white/10 bg-white/5 p-4 sm:p-5">
              <span aria-hidden="true" className="inline-flex rounded-lg bg-brand/20 p-2.5 text-xl">{icon}</span>
              <strong className="mt-3 block text-3xl text-white tabular-nums">{value}</strong>
              <span className="text-sm text-ink-muted">{label}</span>
            </article>
          ))}
        </div>
      )}
    </AsyncBoundary>
  );
}

function UsersPanel() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const query = useQuery({
    queryKey: queryKeys.admin.users(page),
    queryFn: () => fetchAdminUsers(page, PAGE_SIZE),
  });

  const update = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Parameters<typeof updateAdminUser>[1] }) =>
      updateAdminUser(id, payload),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
  const remove = useMutation({
    mutationFn: deleteAdminUser,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.admin.stats }),
      ]);
    },
  });

  return (
    <section className="space-y-4 rounded-xl border border-white/10 bg-white/5 p-4 sm:p-5">
      <label className="block max-w-sm">
        <span className="sr-only">{t("admin.users.search")}</span>
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={t("admin.users.search")}
          className="w-full rounded-md border border-white/15 bg-ink px-3 py-2 text-sm text-white placeholder:text-ink-muted focus:border-brand-soft focus:outline-none"
        />
      </label>
      {update.isError || remove.isError ? <MutationError error={update.error ?? remove.error} /> : null}
      <AsyncBoundary query={query}>
        {(data) => {
          const needle = search.trim().toLowerCase();
          const users = needle
            ? data.items.filter((user) =>
                [user.email, user.first_name, user.last_name, user.nickname]
                  .filter(Boolean)
                  .some((value) => value!.toLowerCase().includes(needle)),
              )
            : data.items;
          return (
            <>
              <UsersTable users={users} pendingId={update.variables?.id ?? remove.variables} onUpdate={update.mutate} onDelete={remove.mutate} />
              <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
            </>
          );
        }}
      </AsyncBoundary>
    </section>
  );
}

function UsersTable({
  users,
  pendingId,
  onUpdate,
  onDelete,
}: {
  users: AdminUser[];
  pendingId: string | undefined;
  onUpdate: (change: { id: string; payload: Parameters<typeof updateAdminUser>[1] }) => void;
  onDelete: (id: string) => void;
}) {
  const { t } = useTranslation();
  const columns: Column<AdminUser>[] = [
    { key: "email", header: t("admin.users.email"), cell: (user) => <span className="text-white">{user.email}</span> },
    { key: "name", header: t("admin.users.name"), cell: (user) => `${user.first_name ?? ""} ${user.last_name ?? ""}`.trim() || "—" },
    { key: "verified", header: t("admin.users.verified"), cell: (user) => user.is_verified ? t("admin.yes") : t("admin.no") },
    {
      key: "status",
      header: t("admin.users.status"),
      cell: (user) => (
        <Button
          variant="secondary"
          disabled={pendingId === user.id}
          onClick={() => onUpdate({ id: user.id, payload: { is_active: !user.is_active } })}
        >
          {user.is_active ? t("admin.users.deactivate") : t("admin.users.activate")}
        </Button>
      ),
    },
    {
      key: "role",
      header: t("admin.users.role"),
      cell: (user) => (
        <Button
          variant="secondary"
          disabled={pendingId === user.id}
          onClick={() => onUpdate({ id: user.id, payload: { is_superuser: !user.is_superuser } })}
        >
          {user.is_superuser ? t("admin.users.removeAdmin") : t("admin.users.makeAdmin")}
        </Button>
      ),
    },
    {
      key: "delete",
      header: t("admin.users.actions"),
      cell: (user) => (
        <Button
          variant="danger"
          disabled={pendingId === user.id}
          onClick={() => {
            if (window.confirm(t("admin.users.confirmDelete", { email: user.email }))) onDelete(user.id);
          }}
        >
          {t("admin.delete")}
        </Button>
      ),
    },
  ];
  return (
    <div className="admin-dark-table">
      <DataTable rows={users} columns={columns} rowKey={(user) => user.id} caption={t("admin.users.title")} empty={{ title: t("admin.users.empty") }} />
    </div>
  );
}

function ResourcesPanel() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [editor, setEditor] = useState<AdminResourceDetail | "new" | null>(null);
  const query = useQuery({
    queryKey: queryKeys.admin.resources(page),
    queryFn: () => fetchAdminResources(page, PAGE_SIZE),
  });
  const loadEditor = useMutation({ mutationFn: fetchAdminResource, onSuccess: setEditor });
  const state = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Parameters<typeof updateAdminResourceState>[1] }) =>
      updateAdminResourceState(id, payload),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["admin", "resources"] }),
  });
  const remove = useMutation({
    mutationFn: deleteAdminResource,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin", "resources"] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.admin.stats }),
      ]);
    },
  });

  async function saveResource(payload: AdminResourceCreate) {
    if (editor === "new") await createAdminResource(payload);
    else if (editor) await replaceAdminResource(editor.id, payload);
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["admin", "resources"] }),
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.stats }),
    ]);
    setEditor(null);
  }

  return (
    <section className="space-y-4 rounded-xl border border-white/10 bg-white/5 p-4 sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <label className="block w-full flex-1">
          <span className="sr-only">{t("admin.resources.search")}</span>
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t("admin.resources.search")}
            className="w-full rounded-md border border-white/15 bg-ink px-3 py-2 text-sm text-white placeholder:text-ink-muted focus:border-brand-soft focus:outline-none"
          />
        </label>
        <Button className="w-full sm:w-auto" onClick={() => setEditor("new")}>{t("admin.resources.new")}</Button>
      </div>
      {state.isError || remove.isError || loadEditor.isError ? (
        <MutationError error={state.error ?? remove.error ?? loadEditor.error} />
      ) : null}
      <AsyncBoundary query={query}>
        {(data) => {
          const needle = search.trim().toLowerCase();
          const resources = needle
            ? data.items.filter((resource) =>
                [resource.title, resource.category, resource.level]
                  .filter(Boolean)
                  .some((value) => value!.toLowerCase().includes(needle)),
              )
            : data.items;
          return (
            <>
              <ResourcesTable
                resources={resources}
                pendingId={state.variables?.id ?? remove.variables ?? loadEditor.variables}
                onEdit={loadEditor.mutate}
                onState={state.mutate}
                onDelete={remove.mutate}
              />
              <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
            </>
          );
        }}
      </AsyncBoundary>
      {editor ? (
        <ResourceEditor
          {...(editor === "new" ? {} : { resource: editor })}
          onSave={saveResource}
          onCancel={() => setEditor(null)}
        />
      ) : null}
    </section>
  );
}

function ResourcesTable({
  resources,
  pendingId,
  onEdit,
  onState,
  onDelete,
}: {
  resources: AdminResource[];
  pendingId: string | undefined;
  onEdit: (id: string) => void;
  onState: (change: { id: string; payload: Parameters<typeof updateAdminResourceState>[1] }) => void;
  onDelete: (id: string) => void;
}) {
  const { t } = useTranslation();
  const columns: Column<AdminResource>[] = useMemo(() => [
    { key: "title", header: t("admin.resources.title"), cell: (resource) => <span className="font-medium text-white">{resource.icon} {resource.title}</span> },
    { key: "category", header: t("admin.resources.category"), cell: (resource) => resource.category },
    { key: "level", header: t("admin.resources.level"), cell: (resource) => resource.level ?? "—" },
    {
      key: "published",
      header: t("admin.resources.visibility"),
      cell: (resource) => (
        <Button variant="secondary" disabled={pendingId === resource.id} onClick={() => onState({ id: resource.id, payload: { is_published: !resource.is_published } })}>
          {resource.is_published ? t("admin.resources.unpublish") : t("admin.resources.publish")}
        </Button>
      ),
    },
    {
      key: "locked",
      header: t("admin.resources.access"),
      cell: (resource) => (
        <Button variant="secondary" disabled={pendingId === resource.id} onClick={() => onState({ id: resource.id, payload: { is_locked: !resource.is_locked } })}>
          {resource.is_locked ? t("admin.resources.unlock") : t("admin.resources.lock")}
        </Button>
      ),
    },
    {
      key: "actions",
      header: t("admin.resources.actions"),
      cell: (resource) => (
        <div className="flex gap-2">
          <Button variant="secondary" disabled={pendingId === resource.id} onClick={() => onEdit(resource.id)}>{t("admin.edit")}</Button>
          <Button variant="danger" disabled={pendingId === resource.id} onClick={() => {
            if (window.confirm(t("admin.resources.confirmDelete", { title: resource.title }))) onDelete(resource.id);
          }}>{t("admin.delete")}</Button>
        </div>
      ),
    },
  ], [onDelete, onEdit, onState, pendingId, t]);

  return (
    <div className="admin-dark-table">
      <DataTable rows={resources} columns={columns} rowKey={(resource) => resource.id} caption={t("admin.resources.caption")} empty={{ title: t("admin.resources.empty") }} />
    </div>
  );
}

function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (page: number) => void }) {
  const { t } = useTranslation();
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <nav aria-label={t("admin.pagination.label")} className="flex flex-wrap items-center justify-end gap-3 text-sm text-ink-muted">
      <Button variant="secondary" disabled={page <= 1} onClick={() => onPage(page - 1)}>{t("admin.pagination.previous")}</Button>
      <span>{t("admin.pagination.status", { page, pages, total })}</span>
      <Button variant="secondary" disabled={page >= pages} onClick={() => onPage(page + 1)}>{t("admin.pagination.next")}</Button>
    </nav>
  );
}

function MutationError({ error }: { error: unknown }) {
  const { t } = useTranslation();
  return (
    <Alert tone="danger">
      {error instanceof ApiError && error.detail ? error.detail.message : t("admin.actionError")}
    </Alert>
  );
}
