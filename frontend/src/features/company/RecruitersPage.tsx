import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { Alert, Badge, Button, Card, CardHeader, FormField, Input, PageHeader, Select } from "@/components/ui";
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
    <div className="flex flex-col gap-6">
      <DocumentMeta
        title={t("company.recruiters.seoTitle")}
        description={t("company.recruiters.seoDescription")}
        path="/company/recruiters"
      />

      <PageHeader
        title={t("company.recruiters.title")}
        description={t("company.recruiters.subtitle")}
        actions={<Badge tone="brand" size="md">{t("company.recruiters.ownerBadge")}</Badge>}
      />

      <Card>
        <CardHeader
          title={t("company.recruiters.accessTitle")}
          description={t("company.recruiters.accessSubtitle")}
          action={
            <Button variant={inviting ? "outline" : "primary"} size="sm" onClick={() => setInviting((value) => !value)}>
              {inviting ? t("company.recruiters.cancel") : t("company.recruiters.invite")}
            </Button>
          }
        />

        {inviting ? (
          <div className="mt-4 rounded-lg border border-border bg-surface-subtle p-4">
            <InviteForm onDone={() => setInviting(false)} />
          </div>
        ) : null}

        <AsyncBoundary query={query}>
          {(recruiters) => (
            <ul className="mt-4 divide-y divide-border-subtle">
              {recruiters.map((recruiter) => (
                <RecruiterRow key={recruiter.id} recruiter={recruiter} />
              ))}
            </ul>
          )}
        </AsyncBoundary>
      </Card>
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

  const name = `${recruiter.first_name ?? ""} ${recruiter.last_name ?? ""}`.trim() || recruiter.email;

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 py-3">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate text-card-title text-ink">{name}</p>
          <Badge tone={recruiter.is_active ? "success" : "neutral"}>
            {recruiter.is_active ? t("company.recruiters.active") : t("company.recruiters.inactive")}
          </Badge>
        </div>
        <p className="truncate text-caption text-ink-muted">{recruiter.email}</p>

        {roleMutation.isError ? (
          <p role="alert" className="mt-1 text-caption text-danger">
            {errorMessage(roleMutation.error, "company.recruiters.roleError")}
          </p>
        ) : null}
        {deleteMutation.isError ? (
          <p role="alert" className="mt-1 text-caption text-danger">
            {errorMessage(deleteMutation.error, "company.recruiters.removeError")}
          </p>
        ) : null}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <Select
          value={recruiter.role}
          disabled={roleMutation.isPending}
          aria-label={t("company.recruiters.roleFor", { name })}
          onChange={(event) => roleMutation.mutate(event.target.value)}
          className="w-auto"
        >
          {ROLES.map((role) => (
            <option key={role} value={role}>
              {role}
            </option>
          ))}
        </Select>
        <Button
          variant="danger"
          size="sm"
          loading={deleteMutation.isPending}
          onClick={() => {
            if (window.confirm(t("company.recruiters.confirmRemove"))) deleteMutation.mutate();
          }}
        >
          {t("company.recruiters.remove")}
        </Button>
      </div>
    </li>
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
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      {mutation.isError ? (
        <Alert tone="danger">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("company.recruiters.inviteError")}
        </Alert>
      ) : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={t("company.recruiters.form.firstName")}>
          <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} />
        </FormField>
        <FormField label={t("company.recruiters.form.lastName")}>
          <Input value={lastName} onChange={(e) => setLastName(e.target.value)} />
        </FormField>
        <FormField label={t("company.recruiters.form.email")} required>
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </FormField>
        <FormField label={t("company.recruiters.form.role")}>
          <Select value={role} onChange={(e) => setRole(e.target.value as (typeof ROLES)[number])}>
            {ROLES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField label={t("company.recruiters.form.password")} required>
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </FormField>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" loading={mutation.isPending}>
          {mutation.isPending ? t("company.recruiters.sending") : t("company.recruiters.sendInvite")}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          {t("company.recruiters.cancel")}
        </Button>
      </div>
    </form>
  );
}
