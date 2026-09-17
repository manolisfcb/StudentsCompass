import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { PageScope } from "@/components/layout/PageScope";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { FormField } from "@/components/patterns/FormField";
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
    <PageScope name="company-team" className="team-shell">
      <DocumentMeta
        title={t("company.recruiters.seoTitle")}
        description={t("company.recruiters.seoDescription")}
        path="/company/recruiters"
      />
      <div className="page-hero">
        <div>
          <h2>{t("company.recruiters.title")}</h2>
          <p>{t("company.recruiters.subtitle")}</p>
        </div>
        <div className="owner-badge">{t("company.recruiters.ownerBadge")}</div>
      </div>

      <section className="section-card">
        <div className="section-header">
          <div>
            <h3>{t("company.recruiters.accessTitle")}</h3>
            <p>{t("company.recruiters.accessSubtitle")}</p>
          </div>
          <button type="button" className="btn btn-primary" onClick={() => setInviting((value) => !value)}>
            {inviting ? t("company.recruiters.cancel") : t("company.recruiters.invite")}
          </button>
        </div>

        {inviting ? <InviteForm onDone={() => setInviting(false)} /> : null}

        <AsyncBoundary query={query}>
          {(recruiters) => (
            <div className="recruiter-list">
              {recruiters.map((recruiter) => (
                <RecruiterRow key={recruiter.id} recruiter={recruiter} />
              ))}
            </div>
          )}
        </AsyncBoundary>
      </section>
    </PageScope>
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

  const name = `${recruiter.first_name ?? ""} ${recruiter.last_name ?? ""}`.trim() || recruiter.email;

  return (
    <article className="recruiter-item">
      <div className="recruiter-identity">
        <strong>{name}</strong>
        <span>{recruiter.email}</span>
        <span className={`status-pill ${recruiter.is_active ? "active" : "inactive"}`}>
          {recruiter.is_active ? t("company.recruiters.active") : t("company.recruiters.inactive")}
        </span>
      </div>
      <div className="recruiter-item-actions">
        <select
          value={recruiter.role}
          disabled={roleMutation.isPending}
          aria-label={t("company.recruiters.roleFor", { name })}
          onChange={(event) => roleMutation.mutate(event.target.value)}
        >
          {ROLES.map((role) => (
            <option key={role} value={role}>
              {role}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="btn btn-danger"
          disabled={deleteMutation.isPending}
          onClick={() => {
            if (window.confirm(t("company.recruiters.confirmRemove"))) deleteMutation.mutate();
          }}
        >
          {t("company.recruiters.remove")}
        </button>
      </div>
      {roleMutation.isError ? (
        <p className="feedback-message" role="alert">
          {errorMessage(roleMutation.error, "company.recruiters.roleError")}
        </p>
      ) : null}
      {deleteMutation.isError ? (
        <p className="feedback-message" role="alert">
          {errorMessage(deleteMutation.error, "company.recruiters.removeError")}
        </p>
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
    <form onSubmit={handleSubmit} className="recruiter-form">
      {mutation.isError ? (
        <p className="feedback-message" role="alert">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("company.recruiters.inviteError")}
        </p>
      ) : null}
      <div className="recruiter-form-grid">
        <FormField label={t("company.recruiters.form.firstName")}>
          <input value={firstName} onChange={(e) => setFirstName(e.target.value)} />
        </FormField>
        <FormField label={t("company.recruiters.form.lastName")}>
          <input value={lastName} onChange={(e) => setLastName(e.target.value)} />
        </FormField>
        <FormField label={t("company.recruiters.form.email")}>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </FormField>
        <FormField label={t("company.recruiters.form.role")}>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as (typeof ROLES)[number])}
          >
            {ROLES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </FormField>
        <FormField label={t("company.recruiters.form.password")}>
          <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </FormField>
      </div>
      <div className="recruiter-actions">
        <button type="submit" className="btn btn-primary" disabled={mutation.isPending}>
          {mutation.isPending ? t("company.recruiters.sending") : t("company.recruiters.sendInvite")}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onDone}>
          {t("company.recruiters.cancel")}
        </button>
      </div>
    </form>
  );
}
