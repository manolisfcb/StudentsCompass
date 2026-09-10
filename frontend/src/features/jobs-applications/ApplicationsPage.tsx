import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { EmptyState } from "@/components/patterns/EmptyState";
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
    <div className="space-y-6">
      <DocumentMeta
        title={t("applications.seoTitle")}
        description={t("applications.seoDescription")}
        path="/jobs/applications"
      />
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink">{t("applications.title")}</h1>
        <Link to="/jobs" className="text-sm font-medium text-brand hover:underline">
          {t("applications.backToJobs")}
        </Link>
      </div>
      <AsyncBoundary query={query}>
        {(page) =>
          page.items.length === 0 && cursors.length === 1 ? (
            <EmptyState title={t("applications.empty")} />
          ) : (
            <div className="space-y-4">
              {page.items.map((application) => (
                <ApplicationCard key={application.id} application={application} />
              ))}
              {page.has_more && page.next_cursor ? (
                <Button
                  variant="secondary"
                  onClick={() => setCursors((prev) => [...prev, page.next_cursor ?? null])}
                >
                  {t("applications.loadMore")}
                </Button>
              ) : null}
            </div>
          )
        }
      </AsyncBoundary>
    </div>
  );
}

function ApplicationCard({ application }: { application: Application }) {
  const { t } = useTranslation();
  const [pickingSlot, setPickingSlot] = useState(false);

  return (
    <article className="rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="font-semibold text-ink">{application.job_title}</h2>
          <p className="text-sm text-ink-soft">{application.company_name ?? t("applications.unknownCompany")}</p>
        </div>
        <StatusPill status={application.status} />
      </div>
      {application.notes ? <p className="mt-2 text-sm text-ink-soft">{application.notes}</p> : null}

      {application.selected_interview_slot ? (
        <Alert tone="success">
          {t("applications.interviewConfirmed", {
            date: new Date(application.selected_interview_slot.starts_at).toLocaleString(),
          })}
        </Alert>
      ) : (application.available_interview_slots ?? []).length > 0 ? (
        <div className="mt-3">
          {pickingSlot ? (
            <InterviewSlotPicker application={application} onDone={() => setPickingSlot(false)} />
          ) : (
            <Button variant="secondary" onClick={() => setPickingSlot(true)}>
              {t("applications.viewSlots")}
            </Button>
          )}
        </div>
      ) : null}
    </article>
  );
}

function StatusPill({ status }: { status: string }) {
  return (
    <span className="rounded-full bg-brand/10 px-3 py-1 text-xs font-medium capitalize text-brand">
      {status.replace(/_/g, " ")}
    </span>
  );
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
    <div className="space-y-2 rounded-md border border-border p-3">
      {mutation.isError ? (
        <Alert tone="danger">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("applications.slotError")}
        </Alert>
      ) : null}
      <ul className="space-y-1">
        {(application.available_interview_slots ?? []).map((slot) => (
          <li key={slot.id}>
            <Button
              variant="secondary"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate(slot.id)}
              className="w-full justify-start"
            >
              {new Date(slot.starts_at).toLocaleString()}
            </Button>
          </li>
        ))}
      </ul>
      <Button variant="ghost" onClick={onDone}>
        {t("applications.cancel")}
      </Button>
    </div>
  );
}
