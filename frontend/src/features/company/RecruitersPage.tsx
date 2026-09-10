import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { FormField, INPUT_CLASS } from "@/components/patterns/FormField";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import {
  createRecruiter,
  deleteRecruiter,
  fetchRecruiters,
  updateRecruiter,
  type Recruiter,
} from "@/features/company/api";

const QUERY_KEY = ["company", "recruiters"];
const ROLES = ["owner", "admin", "recruiter", "viewer"] as const;

/**
 * Recruiter management (`company-team.html`/`.js`). Owner-only on the
 * backend (`current_company_owner_recruiter`): a non-owner who reaches this
 * screen gets the same 403 on `GET /companies/me/recruiters` that
 * `AsyncBoundary`'s error state already renders — there is nothing extra to
 * gate here.
 */
export function RecruitersPage() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: QUERY_KEY, queryFn: fetchRecruiters });
  const [inviting, setInviting] = useState(false);

  return (
    <div className="space-y-6">
      <DocumentMeta
        title={t("company.recruiters.seoTitle")}
        description={t("company.recruiters.seoDescription")}
        path="/company/recruiters"
      />
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink">{t("company.recruiters.title")}</h1>
        <Button onClick={() => setInviting((value) => !value)}>
          {inviting ? t("company.recruiters.cancel") : t("company.recruiters.invite")}
        </Button>
      </div>

      {inviting ? <InviteForm onDone={() => setInviting(false)} /> : null}

      <AsyncBoundary query={query}>
        {(recruiters) => (
          <div className="space-y-3">
            {recruiters.map((recruiter) => (
              <RecruiterRow key={recruiter.id} recruiter={recruiter} />
            ))}
          </div>
        )}
      </AsyncBoundary>
    </div>
  );
}

function RecruiterRow({ recruiter }: { recruiter: Recruiter }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const roleMutation = useMutation({
    mutationFn: (role: string) => updateRecruiter(recruiter.id, { role }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteRecruiter(recruiter.id),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  });

  const errorMessage = (error: unknown, fallbackKey: string): string | null => {
    if (!error) return null;
    return error instanceof ApiError && error.detail ? error.detail.message : t(fallbackKey);
  };

  return (
    <article className="space-y-2 rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-semibold text-ink">
            {`${recruiter.first_name ?? ""} ${recruiter.last_name ?? ""}`.trim() || recruiter.email}
          </p>
          <p className="text-sm text-ink-soft">{recruiter.email}</p>
          <span className="text-xs text-ink-muted">
            {recruiter.is_active ? t("company.recruiters.active") : t("company.recruiters.inactive")}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={recruiter.role}
            disabled={roleMutation.isPending}
            onChange={(event) => roleMutation.mutate(event.target.value)}
            className="rounded-md border border-border bg-surface px-2 py-1 text-xs text-ink"
          >
            {ROLES.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
          <Button
            variant="danger"
            disabled={deleteMutation.isPending}
            onClick={() => {
              if (window.confirm(t("company.recruiters.confirmRemove"))) deleteMutation.mutate();
            }}
          >
            {t("company.recruiters.remove")}
          </Button>
        </div>
      </div>
      {roleMutation.isError ? (
        <Alert tone="danger">{errorMessage(roleMutation.error, "company.recruiters.roleError")}</Alert>
      ) : null}
      {deleteMutation.isError ? (
        <Alert tone="danger">{errorMessage(deleteMutation.error, "company.recruiters.removeError")}</Alert>
      ) : null}
    </article>
  );
}

function InviteForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [role, setRole] = useState<(typeof ROLES)[number]>("recruiter");
  const [password, setPassword] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      createRecruiter({ email, password, first_name: firstName || null, last_name: lastName || null, role }),
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
            : t("company.recruiters.inviteError")}
        </Alert>
      ) : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={t("company.recruiters.form.firstName")}>
          <input value={firstName} onChange={(e) => setFirstName(e.target.value)} className={INPUT_CLASS} />
        </FormField>
        <FormField label={t("company.recruiters.form.lastName")}>
          <input value={lastName} onChange={(e) => setLastName(e.target.value)} className={INPUT_CLASS} />
        </FormField>
      </div>
      <FormField label={t("company.recruiters.form.email")}>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className={INPUT_CLASS}
        />
      </FormField>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={t("company.recruiters.form.role")}>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as (typeof ROLES)[number])}
            className={INPUT_CLASS}
          >
            {ROLES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </FormField>
        <FormField label={t("company.recruiters.form.password")}>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={INPUT_CLASS}
          />
        </FormField>
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? t("company.recruiters.sending") : t("company.recruiters.sendInvite")}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          {t("company.recruiters.cancel")}
        </Button>
      </div>
    </form>
  );
}
