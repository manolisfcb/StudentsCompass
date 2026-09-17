import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DataTable, type Column } from "@/components/patterns/DataTable";
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
    <div className="admin-content">
      <DocumentMeta title={t("admin.seoTitle")} description={t("admin.seoDescription")} path="/admin" />
      <div className="admin-section active">
        {section === "dashboard" ? <AdminDashboard /> : null}
        {section === "users" ? <UsersPanel title={sectionTitle} /> : null}
        {section === "resources" ? <ResourcesPanel title={sectionTitle} /> : null}
      </div>
    </div>
  );
}

function AdminDashboard() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: queryKeys.admin.stats, queryFn: fetchAdminStats });

  return (
    <AsyncBoundary query={query}>
      {(stats) => (
        <div className="admin-stats-grid">
          {(
            [
              ["users", "👥", stats.total_users, t("admin.stats.users")],
              ["resources", "📚", stats.total_resources, t("admin.stats.resources")],
              ["resumes", "📄", stats.total_resumes, t("admin.stats.resumes")],
              ["questionnaires", "📝", stats.total_questionnaires, t("admin.stats.questionnaires")],
            ] as const
          ).map(([tone, icon, value, label]) => (
            <article key={label} className="admin-stat-card">
              <div className="admin-stat-header">
                <span className={`admin-stat-icon ${tone}`} aria-hidden="true">
                  {icon}
                </span>
              </div>
              <div className="admin-stat-value">{value}</div>
              <div className="admin-stat-label">{label}</div>
            </article>
          ))}
        </div>
      )}
    </AsyncBoundary>
  );
}

function UsersPanel({ title }: { title: string }) {
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
    <section className="admin-panel">
      <div className="admin-panel-header">
        <div className="admin-panel-title">
          <span className="panel-icon" aria-hidden="true">
            👥
          </span>{" "}
          {title}
        </div>
        <div className="admin-panel-actions">
          <div className="admin-search">
            <span className="search-icon" aria-hidden="true">
              🔍
            </span>
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t("admin.users.search")}
              aria-label={t("admin.users.search")}
            />
          </div>
        </div>
      </div>
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
    { key: "email", header: t("admin.users.email"), cell: (user) => user.email },
    { key: "name", header: t("admin.users.name"), cell: (user) => `${user.first_name ?? ""} ${user.last_name ?? ""}`.trim() || "—" },
    { key: "verified", header: t("admin.users.verified"), cell: (user) => user.is_verified ? t("admin.yes") : t("admin.no") },
    {
      key: "status",
      header: t("admin.users.status"),
      cell: (user) => (
        <button
          type="button"
          className="admin-btn admin-btn-ghost"
          disabled={pendingId === user.id}
          onClick={() => onUpdate({ id: user.id, payload: { is_active: !user.is_active } })}
        >
          {user.is_active ? t("admin.users.deactivate") : t("admin.users.activate")}
        </button>
      ),
    },
    {
      key: "role",
      header: t("admin.users.role"),
      cell: (user) => (
        <button
          type="button"
          className="admin-btn admin-btn-ghost"
          disabled={pendingId === user.id}
          onClick={() => onUpdate({ id: user.id, payload: { is_superuser: !user.is_superuser } })}
        >
          {user.is_superuser ? t("admin.users.removeAdmin") : t("admin.users.makeAdmin")}
        </button>
      ),
    },
    {
      key: "delete",
      header: t("admin.users.actions"),
      cell: (user) => (
        <button
          type="button"
          className="admin-btn admin-btn-danger"
          disabled={pendingId === user.id}
          onClick={() => {
            if (window.confirm(t("admin.users.confirmDelete", { email: user.email }))) onDelete(user.id);
          }}
        >
          {t("admin.delete")}
        </button>
      ),
    },
  ];
  return (
    <DataTable
      variant="admin"
      rows={users}
      columns={columns}
      rowKey={(user) => user.id}
      caption={t("admin.users.title")}
      empty={{ title: t("admin.users.empty") }}
    />
  );
}

function ResourcesPanel({ title }: { title: string }) {
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
    <section className="admin-panel">
      <div className="admin-panel-header">
        <div className="admin-panel-title">
          <span className="panel-icon" aria-hidden="true">
            📚
          </span>{" "}
          {title}
        </div>
        <div className="admin-panel-actions">
          <button type="button" className="admin-btn admin-btn-primary" onClick={() => setEditor("new")}>
            {t("admin.resources.new")}
          </button>
          <div className="admin-search">
            <span className="search-icon" aria-hidden="true">
              🔍
            </span>
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t("admin.resources.search")}
              aria-label={t("admin.resources.search")}
            />
          </div>
        </div>
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
    { key: "title", header: t("admin.resources.title"), cell: (resource) => `${resource.icon ?? ""} ${resource.title}`.trim() },
    { key: "category", header: t("admin.resources.category"), cell: (resource) => resource.category },
    { key: "level", header: t("admin.resources.level"), cell: (resource) => resource.level ?? "—" },
    {
      key: "published",
      header: t("admin.resources.visibility"),
      cell: (resource) => (
        <button
          type="button"
          className="admin-btn admin-btn-ghost"
          disabled={pendingId === resource.id}
          onClick={() => onState({ id: resource.id, payload: { is_published: !resource.is_published } })}
        >
          {resource.is_published ? t("admin.resources.unpublish") : t("admin.resources.publish")}
        </button>
      ),
    },
    {
      key: "locked",
      header: t("admin.resources.access"),
      cell: (resource) => (
        <button
          type="button"
          className="admin-btn admin-btn-ghost"
          disabled={pendingId === resource.id}
          onClick={() => onState({ id: resource.id, payload: { is_locked: !resource.is_locked } })}
        >
          {resource.is_locked ? t("admin.resources.unlock") : t("admin.resources.lock")}
        </button>
      ),
    },
    {
      key: "actions",
      header: t("admin.resources.actions"),
      cell: (resource) => (
        <div className="admin-row-actions">
          <button
            type="button"
            className="admin-btn admin-btn-ghost"
            disabled={pendingId === resource.id}
            onClick={() => onEdit(resource.id)}
          >
            {t("admin.edit")}
          </button>
          <button
            type="button"
            className="admin-btn admin-btn-danger"
            disabled={pendingId === resource.id}
            onClick={() => {
              if (window.confirm(t("admin.resources.confirmDelete", { title: resource.title }))) onDelete(resource.id);
            }}
          >
            {t("admin.delete")}
          </button>
        </div>
      ),
    },
  ], [onDelete, onEdit, onState, pendingId, t]);

  return (
    <DataTable
      variant="admin"
      rows={resources}
      columns={columns}
      rowKey={(resource) => resource.id}
      caption={t("admin.resources.caption")}
      empty={{ title: t("admin.resources.empty") }}
    />
  );
}

function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (page: number) => void }) {
  const { t } = useTranslation();
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <nav aria-label={t("admin.pagination.label")} className="admin-pagination">
      <button type="button" className="admin-btn admin-btn-ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        {t("admin.pagination.previous")}
      </button>
      <span>{t("admin.pagination.status", { page, pages, total })}</span>
      <button
        type="button"
        className="admin-btn admin-btn-ghost"
        disabled={page >= pages}
        onClick={() => onPage(page + 1)}
      >
        {t("admin.pagination.next")}
      </button>
    </nav>
  );
}

function MutationError({ error }: { error: unknown }) {
  const { t } = useTranslation();
  return (
    <p className="admin-login-error visible" role="alert">
      {error instanceof ApiError && error.detail ? error.detail.message : t("admin.actionError")}
    </p>
  );
}
