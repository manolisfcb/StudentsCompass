import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { Alert, Badge, Button, Card, EmptyState, FormField, Input, PageHeader, Select } from "@/components/ui";
import type { BadgeTone } from "@/components/ui";
import {
  fetchApplicants,
  publishInterviewAvailabilities,
  updateApplicantPipeline,
  type Applicant,
  type ApplicantPipelineUpdate,
} from "@/features/company/api";

/** A stage's colour is its meaning: an offer is good news, a rejection is not. */
const STATUS_TONES: Record<string, BadgeTone> = {
  applied: "neutral",
  in_review: "info",
  interview: "brand",
  offer: "success",
  rejected: "danger",
  withdrawn: "neutral",
};

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
    <div className="flex flex-col gap-6">
      <DocumentMeta
        title={t("company.applicants.seoTitle")}
        description={t("company.applicants.seoDescription")}
        path="/company/applicants"
      />

      <PageHeader
        title={t("company.applicants.title")}
        actions={
          <div className="flex items-center gap-2">
            <label htmlFor="applicant-status-filter" className="text-label text-ink-soft">
              {t("company.applicants.filterByStatus")}
            </label>
            <Select
              id="applicant-status-filter"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              className="w-auto"
            >
              <option value="">{t("company.applicants.allStatuses")}</option>
              {STATUSES.map((status) => (
                <option key={status} value={status}>
                  {status.replace(/_/g, " ")}
                </option>
              ))}
            </Select>
          </div>
        }
      />

      <AsyncBoundary query={query}>
        {(applicants) =>
          applicants.length === 0 ? (
            <EmptyState title={t("company.applicants.empty")} icon="inbox" />
          ) : (
            <div className="flex flex-col gap-3">
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
    <Card className="flex flex-col gap-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-card-title text-ink">{applicant.candidate.full_name}</p>
          <p className="text-caption text-ink-soft">{applicant.application.job_title}</p>
          <p className="truncate text-caption text-ink-muted">{applicant.candidate.email}</p>
        </div>
        <Badge tone={STATUS_TONES[applicant.application.status] ?? "neutral"} size="md">
          {applicant.application.status.replace(/_/g, " ")}
        </Badge>
      </div>

      {statusMutation.isError ? (
        <Alert tone="danger">
          {statusMutation.error instanceof ApiError && statusMutation.error.detail
            ? statusMutation.error.detail.message
            : t("company.applicants.statusError")}
        </Alert>
      ) : null}

      {applicant.application.selected_interview_slot ? (
        <p className="rounded-md bg-success-subtle px-3 py-2 text-caption text-success">
          {t("company.applicants.interviewBooked", {
            date: new Date(applicant.application.selected_interview_slot.starts_at).toLocaleString(),
          })}
        </p>
      ) : (applicant.application.available_interview_slots ?? []).length > 0 ? (
        <p className="rounded-md bg-surface-subtle px-3 py-2 text-caption text-ink-soft">
          {t("company.applicants.waitingOnCandidate")}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
        {applicant.resume ? (
          <>
            <a href={applicant.resume.preview_url} target="_blank" rel="noopener noreferrer">
              <Button variant="outline" size="sm">
                {t("company.applicants.previewResume")}
              </Button>
            </a>
            <a href={applicant.resume.download_url}>
              <Button variant="outline" size="sm">
                {t("company.applicants.downloadResume")}
              </Button>
            </a>
          </>
        ) : null}

        <Select
          value={applicant.application.status}
          disabled={statusMutation.isPending}
          aria-label={t("company.applicants.statusFor", { name: applicant.candidate.full_name })}
          onChange={(event) => statusMutation.mutate(event.target.value as ApplicantPipelineUpdate["status"])}
          className="h-8 w-auto text-caption"
        >
          {STATUSES.map((status) => (
            <option key={status} value={status}>
              {status.replace(/_/g, " ")}
            </option>
          ))}
        </Select>

        {schedulingInterview ? null : (
          <Button size="sm" className="ml-auto" onClick={() => setSchedulingInterview(true)}>
            {t("company.applicants.scheduleInterview")}
          </Button>
        )}
      </div>

      {schedulingInterview ? (
        <div className="rounded-lg border border-border bg-surface-subtle p-4">
          <InterviewScheduleForm
            applicationId={applicant.application.id}
            onDone={() => setSchedulingInterview(false)}
          />
        </div>
      ) : null}
    </Card>
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
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      {mutation.isError ? (
        <Alert tone="danger">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("company.applicants.scheduleError")}
        </Alert>
      ) : null}
      {slots.map((slot, index) => (
        <div key={index} className="grid gap-4 sm:grid-cols-2">
          <FormField label={t("company.applicants.startsAt")}>
            <Input
              type="datetime-local"
              required
              value={slot.starts_at}
              onChange={(event) =>
                setSlots((prev) => prev.map((s, i) => (i === index ? { ...s, starts_at: event.target.value } : s)))
              }
            />
          </FormField>
          <FormField label={t("company.applicants.endsAt")}>
            <Input
              type="datetime-local"
              required
              value={slot.ends_at}
              onChange={(event) =>
                setSlots((prev) => prev.map((s, i) => (i === index ? { ...s, ends_at: event.target.value } : s)))
              }
            />
          </FormField>
        </div>
      ))}
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => setSlots((prev) => [...prev, { starts_at: "", ends_at: "" }])}
        >
          {t("company.applicants.addSlot")}
        </Button>
        <Button type="submit" loading={mutation.isPending}>
          {mutation.isPending ? t("company.applicants.publishing") : t("company.applicants.publish")}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          {t("company.applicants.cancel")}
        </Button>
      </div>
    </form>
  );
}
