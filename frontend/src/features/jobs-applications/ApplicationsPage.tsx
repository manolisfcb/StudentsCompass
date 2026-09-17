import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { PageScope } from "@/components/layout/PageScope";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { fetchApplicationsPage, selectInterviewSlot, type Application } from "@/features/jobs-applications/api";

/**
 * "My applications" (`jobs.js`'s "My Jobs" tab). The legacy screen fetched the
 * whole unbounded `GET /applications` list; this reads the cursor-paged
 * `GET /applications/page` instead — one page at a time, "Load more" walking
 * the same cursor the backend hands back (TASK-041).
 */
export function ApplicationsPage() {
  const { t } = useTranslation();
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const currentCursor = cursors[cursors.length - 1] ?? null;

  const query = useQuery({
    queryKey: ["applications", "page", currentCursor],
    queryFn: () => fetchApplicationsPage(currentCursor),
  });

  return (
    <PageScope name="jobs" className="container jobs-page">
      <DocumentMeta
        title={t("applications.seoTitle")}
        description={t("applications.seoDescription")}
        path="/jobs/applications"
      />
      <section className="jobs-shell">
        <div className="jobs-body">
          <section className="tab-panel active">
            <div className="section-head">
              <div>
                <h2>{t("applications.title")}</h2>
              </div>
              <Link to="/jobs" className="jobs-profile-link">
                {t("applications.backToJobs")}
              </Link>
            </div>

            <AsyncBoundary query={query}>
              {(page) =>
                page.items.length === 0 && cursors.length === 1 ? (
                  <div className="empty-state">
                    <h3>{t("applications.empty")}</h3>
                  </div>
                ) : (
                  <>
                    <div className="applications-grid">
                      {page.items.map((application) => (
                        <ApplicationCard key={application.id} application={application} />
                      ))}
                    </div>
                    {page.has_more && page.next_cursor ? (
                      <div className="job-card-actions">
                        <button
                          type="button"
                          className="secondary-link"
                          onClick={() => setCursors((prev) => [...prev, page.next_cursor ?? null])}
                        >
                          {t("applications.loadMore")}
                        </button>
                      </div>
                    ) : null}
                  </>
                )
              }
            </AsyncBoundary>
          </section>
        </div>
      </section>
    </PageScope>
  );
}

function ApplicationCard({ application }: { application: Application }) {
  const { t } = useTranslation();
  const [pickingSlot, setPickingSlot] = useState(false);

  const company = application.company_name ?? t("applications.unknownCompany");
  return (
    <article className="application-card">
      <div className="application-card-top">
        <div className="company-mark" aria-hidden="true">
          {company
            .split(/\s+/)
            .filter(Boolean)
            .slice(0, 2)
            .map((word) => word[0]?.toUpperCase() ?? "")
            .join("")}
        </div>
        <StatusPill status={application.status} />
      </div>
      <div>
        <p className="application-company">{company}</p>
        <h3 className="application-title">{application.job_title}</h3>
      </div>
      <div className="application-meta">
        <span>{t("applications.appliedOn", { date: new Date(application.application_date).toLocaleDateString() })}</span>
      </div>

      {application.selected_interview_slot ? (
        <div className="application-interview-banner">
          {t("applications.interviewConfirmed", {
            date: new Date(application.selected_interview_slot.starts_at).toLocaleString(),
          })}
        </div>
      ) : (application.available_interview_slots ?? []).length > 0 ? (
        pickingSlot ? (
          <InterviewSlotPicker application={application} onDone={() => setPickingSlot(false)} />
        ) : (
          <div className="application-actions">
            <button type="button" className="primary-link" onClick={() => setPickingSlot(true)}>
              {t("applications.viewSlots")}
            </button>
          </div>
        )
      ) : null}

      {application.notes ? <p className="application-notes">{application.notes}</p> : null}
    </article>
  );
}

/** `.status-pill` takes the raw status as a modifier, as `jobs.js` wrote it. */
function StatusPill({ status }: { status: string }) {
  return <span className={`status-pill ${status}`}>{status.replace(/_/g, " ")}</span>;
}

function InterviewSlotPicker({ application, onDone }: { application: Application; onDone: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (slotId: string) => selectInterviewSlot(application.id, slotId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["applications"] });
      onDone();
    },
  });

  return (
    <div className="application-slots">
      {mutation.isError ? (
        <p className="application-notes" role="alert">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("applications.slotError")}
        </p>
      ) : null}
      <ul>
        {(application.available_interview_slots ?? []).map((slot) => (
          <li key={slot.id}>
            <button
              type="button"
              className="primary-link"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate(slot.id)}
            >
              {new Date(slot.starts_at).toLocaleString()}
            </button>
          </li>
        ))}
      </ul>
      <div className="application-actions">
        <button type="button" className="secondary-link" onClick={onDone}>
          {t("applications.cancel")}
        </button>
      </div>
    </div>
  );
}
