import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { PageScope } from "@/components/layout/PageScope";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { FormField } from "@/components/patterns/FormField";
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
    <PageScope name="company-dashboard" className="dashboard-container">
      <DocumentMeta
        title={t("company.applicants.seoTitle")}
        description={t("company.applicants.seoDescription")}
        path="/company/applicants"
      />
      <section className="section-card pipeline-section-card">
        <div className="section-card-head">
          <div>
            <h3>{t("company.applicants.title")}</h3>
          </div>
        </div>

        <div className="pipeline-toolbar">
          <div>
            <label className="applicants-job-filter-label" htmlFor="applicant-status-filter">
              {t("company.applicants.filterByStatus")}
            </label>
            <select
              id="applicant-status-filter"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
            >
              <option value="">{t("company.applicants.allStatuses")}</option>
              {STATUSES.map((status) => (
                <option key={status} value={status}>
                  {status.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </div>
        </div>

        <AsyncBoundary query={query}>
          {(applicants) =>
            applicants.length === 0 ? (
              <div className="empty-state">
                <p>{t("company.applicants.empty")}</p>
              </div>
            ) : (
              <div className="applicants-list">
                {applicants.map((applicant) => (
                  <ApplicantCard key={applicant.application.id} applicant={applicant} />
                ))}
              </div>
            )
          }
        </AsyncBoundary>
      </section>
    </PageScope>
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
    <article className="applicant-card">
      <div className="applicant-head">
        <div>
          <p className="applicant-name">{applicant.candidate.full_name}</p>
          <div className="applicant-meta">{applicant.application.job_title}</div>
        </div>
        <div className="applicant-head-badges">
          <span className={`status-pill status-pill-${applicant.application.status}`}>
            {applicant.application.status.replace(/_/g, " ")}
          </span>
        </div>
      </div>

      <div className="applicant-contact">
        <span>
          <strong>{t("company.applicants.email")}</strong> {applicant.candidate.email}
        </span>
      </div>

      {statusMutation.isError ? (
        <div className="applicant-summary" role="alert">
          {statusMutation.error instanceof ApiError && statusMutation.error.detail
            ? statusMutation.error.detail.message
            : t("company.applicants.statusError")}
        </div>
      ) : null}

      {applicant.application.selected_interview_slot ? (
        <div className="applicant-summary">
          {t("company.applicants.interviewBooked", {
            date: new Date(applicant.application.selected_interview_slot.starts_at).toLocaleString(),
          })}
        </div>
      ) : (applicant.application.available_interview_slots ?? []).length > 0 ? (
        <div className="applicant-summary">{t("company.applicants.waitingOnCandidate")}</div>
      ) : null}

      <div className="applicant-actions">
        {applicant.resume ? (
          <>
            <a href={applicant.resume.preview_url} target="_blank" rel="noopener noreferrer" className="btn btn-secondary">
              {t("company.applicants.previewResume")}
            </a>
            <a href={applicant.resume.download_url} className="btn btn-secondary">
              {t("company.applicants.downloadResume")}
            </a>
          </>
        ) : null}
        <select
          value={applicant.application.status}
          disabled={statusMutation.isPending}
          aria-label={t("company.applicants.statusFor", { name: applicant.candidate.full_name })}
          onChange={(event) => statusMutation.mutate(event.target.value as ApplicantPipelineUpdate["status"])}
        >
          {STATUSES.map((status) => (
            <option key={status} value={status}>
              {status.replace(/_/g, " ")}
            </option>
          ))}
        </select>
        {schedulingInterview ? null : (
          <button type="button" className="btn btn-primary" onClick={() => setSchedulingInterview(true)}>
            {t("company.applicants.scheduleInterview")}
          </button>
        )}
      </div>

      {schedulingInterview ? (
        <InterviewScheduleForm applicationId={applicant.application.id} onDone={() => setSchedulingInterview(false)} />
      ) : null}
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
    <form onSubmit={handleSubmit} className="recruiter-form">
      {mutation.isError ? (
        <p className="feedback-message" role="alert">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("company.applicants.scheduleError")}
        </p>
      ) : null}
      {slots.map((slot, index) => (
        <div key={index} className="recruiter-form-grid">
          <FormField label={t("company.applicants.startsAt")}>
            <input
              type="datetime-local"
              required
              value={slot.starts_at}
              onChange={(event) =>
                setSlots((prev) => prev.map((s, i) => (i === index ? { ...s, starts_at: event.target.value } : s)))
              }
            />
          </FormField>
          <FormField label={t("company.applicants.endsAt")}>
            <input
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
      <div className="recruiter-actions">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => setSlots((prev) => [...prev, { starts_at: "", ends_at: "" }])}
        >
          {t("company.applicants.addSlot")}
        </button>
        <button type="submit" className="btn btn-primary" disabled={mutation.isPending}>
          {mutation.isPending ? t("company.applicants.publishing") : t("company.applicants.publish")}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onDone}>
          {t("company.applicants.cancel")}
        </button>
      </div>
    </form>
  );
}
