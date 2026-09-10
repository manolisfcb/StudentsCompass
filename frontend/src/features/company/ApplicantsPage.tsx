import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { EmptyState } from "@/components/patterns/EmptyState";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import {
  fetchApplicants,
  publishInterviewAvailabilities,
  updateApplicantPipeline,
  type Applicant,
  type ApplicantPipelineUpdate,
} from "@/features/company/api";

const STATUSES: ApplicantPipelineUpdate["status"][] = [
  "applied",
  "in_review",
  "interview",
  "offer",
  "rejected",
  "withdrawn",
];

/**
 * The applicant pipeline (`company-candidates.html`/`.js`). Status changes
 * and interview scheduling only ever send the backend's own vocabulary back
 * to it — this screen does not decide who may move to which stage, or
 * recompute a stage count; `CompanyDashboardPage` already shows the
 * server-computed ones.
 */
export function ApplicantsPage() {
  const { t } = useTranslation();
  const [statusFilter, setStatusFilter] = useState<string>("");
  const query = useQuery({
    queryKey: ["company", "applicants", statusFilter],
    queryFn: () => fetchApplicants(statusFilter ? { statuses: [statusFilter] } : {}),
  });

  return (
    <div className="space-y-6">
      <DocumentMeta
        title={t("company.applicants.seoTitle")}
        description={t("company.applicants.seoDescription")}
        path="/company/applicants"
      />
      <h1 className="text-2xl font-bold text-ink">{t("company.applicants.title")}</h1>

      <label className="block max-w-xs space-y-1">
        <span className="text-sm font-medium text-ink">{t("company.applicants.filterByStatus")}</span>
        <select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink"
        >
          <option value="">{t("company.applicants.allStatuses")}</option>
          {STATUSES.map((status) => (
            <option key={status} value={status}>
              {status.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </label>

      <AsyncBoundary query={query}>
        {(applicants) =>
          applicants.length === 0 ? (
            <EmptyState title={t("company.applicants.empty")} />
          ) : (
            <div className="space-y-4">
              {applicants.map((applicant) => (
                <ApplicantCard key={applicant.application.id} applicant={applicant} />
              ))}
            </div>
          )
        }
      </AsyncBoundary>
    </div>
  );
}

function ApplicantCard({ applicant }: { applicant: Applicant }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [schedulingInterview, setSchedulingInterview] = useState(false);

  const statusMutation = useMutation({
    mutationFn: (status: ApplicantPipelineUpdate["status"]) =>
      updateApplicantPipeline(applicant.application.id, { status }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["company", "applicants"] }),
  });

  return (
    <article className="rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-ink">{applicant.candidate.full_name}</p>
          <p className="text-sm text-ink-soft">{applicant.application.job_title}</p>
          <p className="text-xs text-ink-muted">{applicant.candidate.email}</p>
        </div>
        <select
          value={applicant.application.status}
          disabled={statusMutation.isPending}
          onChange={(event) => statusMutation.mutate(event.target.value as ApplicantPipelineUpdate["status"])}
          className="rounded-md border border-border bg-surface px-2 py-1 text-xs text-ink"
        >
          {STATUSES.map((status) => (
            <option key={status} value={status}>
              {status.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </div>

      {applicant.resume ? (
        <div className="mt-3 flex gap-3 text-sm">
          <a href={applicant.resume.preview_url} target="_blank" rel="noopener noreferrer" className="text-brand hover:underline">
            {t("company.applicants.previewResume")}
          </a>
          <a href={applicant.resume.download_url} className="text-brand hover:underline">
            {t("company.applicants.downloadResume")}
          </a>
        </div>
      ) : null}

      {statusMutation.isError ? (
        <Alert tone="danger">
          {statusMutation.error instanceof ApiError && statusMutation.error.detail
            ? statusMutation.error.detail.message
            : t("company.applicants.statusError")}
        </Alert>
      ) : null}

      {applicant.application.selected_interview_slot ? (
        <Alert tone="success">
          {t("company.applicants.interviewBooked", {
            date: new Date(applicant.application.selected_interview_slot.starts_at).toLocaleString(),
          })}
        </Alert>
      ) : (applicant.application.available_interview_slots ?? []).length > 0 ? (
        <Alert tone="info">{t("company.applicants.waitingOnCandidate")}</Alert>
      ) : null}

      <div className="mt-3">
        {schedulingInterview ? (
          <InterviewScheduleForm applicationId={applicant.application.id} onDone={() => setSchedulingInterview(false)} />
        ) : (
          <Button variant="secondary" onClick={() => setSchedulingInterview(true)}>
            {t("company.applicants.scheduleInterview")}
          </Button>
        )}
      </div>
    </article>
  );
}

function InterviewScheduleForm({ applicationId, onDone }: { applicationId: string; onDone: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [slots, setSlots] = useState([{ starts_at: "", ends_at: "" }]);

  const mutation = useMutation({
    mutationFn: () =>
      publishInterviewAvailabilities(applicationId, {
        slots: slots
          .filter((slot) => slot.starts_at && slot.ends_at)
          .map((slot) => ({
            starts_at: new Date(slot.starts_at).toISOString(),
            ends_at: new Date(slot.ends_at).toISOString(),
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          })),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["company", "applicants"] });
      onDone();
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-2 rounded-md border border-border p-3">
      {mutation.isError ? (
        <Alert tone="danger">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("company.applicants.scheduleError")}
        </Alert>
      ) : null}
      {slots.map((slot, index) => (
        <div key={index} className="grid gap-2 sm:grid-cols-2">
          <label className="space-y-1 text-xs">
            <span className="block font-medium text-ink">{t("company.applicants.startsAt")}</span>
            <input
              type="datetime-local"
              required
              value={slot.starts_at}
              onChange={(event) =>
                setSlots((prev) => prev.map((s, i) => (i === index ? { ...s, starts_at: event.target.value } : s)))
              }
              className="w-full rounded-md border border-border bg-surface px-2 py-1 text-xs text-ink"
            />
          </label>
          <label className="space-y-1 text-xs">
            <span className="block font-medium text-ink">{t("company.applicants.endsAt")}</span>
            <input
              type="datetime-local"
              required
              value={slot.ends_at}
              onChange={(event) =>
                setSlots((prev) => prev.map((s, i) => (i === index ? { ...s, ends_at: event.target.value } : s)))
              }
              className="w-full rounded-md border border-border bg-surface px-2 py-1 text-xs text-ink"
            />
          </label>
        </div>
      ))}
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="secondary"
          onClick={() => setSlots((prev) => [...prev, { starts_at: "", ends_at: "" }])}
        >
          {t("company.applicants.addSlot")}
        </Button>
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? t("company.applicants.publishing") : t("company.applicants.publish")}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          {t("company.applicants.cancel")}
        </Button>
      </div>
    </form>
  );
}
