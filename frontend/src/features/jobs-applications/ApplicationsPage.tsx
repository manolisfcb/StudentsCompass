import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { Alert, Badge, Button, Card, EmptyState, PageHeader } from "@/components/ui";
import type { BadgeTone } from "@/components/ui";
import { fetchApplicationsPage, selectInterviewSlot, type Application } from "@/features/jobs-applications/api";

/** An application's stage, coloured by what it means rather than all alike. */
const STATUS_TONES: Record<string, BadgeTone> = {
  applied: "neutral",
  in_review: "info",
  interview: "brand",
  offer: "success",
  rejected: "danger",
  withdrawn: "neutral",
};

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
    <div className="flex flex-col gap-6">
      <DocumentMeta
        title={t("applications.seoTitle")}
        description={t("applications.seoDescription")}
        path="/jobs/applications"
      />

      <PageHeader
        title={t("applications.title")}
        actions={
          <Link to="/jobs">
            <Button variant="outline">{t("applications.backToJobs")}</Button>
          </Link>
        }
      />

      <AsyncBoundary query={query}>
        {(page) =>
          page.items.length === 0 && cursors.length === 1 ? (
            <EmptyState title={t("applications.empty")} icon="📝" />
          ) : (
            <div className="flex flex-col gap-4">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {page.items.map((application) => (
                  <ApplicationCard key={application.id} application={application} />
                ))}
              </div>
              {page.has_more && page.next_cursor ? (
                <Button
                  variant="outline"
                  className="self-center"
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

  const company = application.company_name ?? t("applications.unknownCompany");
  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <span
          aria-hidden="true"
          className="flex size-9 shrink-0 items-center justify-center rounded-md bg-primary-subtle text-label text-primary"
        >
          {company
            .split(/\s+/)
            .filter(Boolean)
            .slice(0, 2)
            .map((word) => word[0]?.toUpperCase() ?? "")
            .join("")}
        </span>
        <Badge tone={STATUS_TONES[application.status] ?? "neutral"}>{application.status.replace(/_/g, " ")}</Badge>
      </div>

      <div className="min-w-0">
        <p className="truncate text-caption text-ink-soft">{company}</p>
        <h3 className="truncate text-card-title text-ink">{application.job_title}</h3>
        <p className="mt-1 text-caption text-ink-muted">
          {t("applications.appliedOn", { date: new Date(application.application_date).toLocaleDateString() })}
        </p>
      </div>

      {application.selected_interview_slot ? (
        <p className="rounded-md bg-success-subtle px-3 py-2 text-caption text-success">
          {t("applications.interviewConfirmed", {
            date: new Date(application.selected_interview_slot.starts_at).toLocaleString(),
          })}
        </p>
      ) : (application.available_interview_slots ?? []).length > 0 ? (
        pickingSlot ? (
          <InterviewSlotPicker application={application} onDone={() => setPickingSlot(false)} />
        ) : (
          <Button size="sm" className="self-start" onClick={() => setPickingSlot(true)}>
            {t("applications.viewSlots")}
          </Button>
        )
      ) : null}

      {application.notes ? <p className="text-caption text-ink-soft">{application.notes}</p> : null}
    </Card>
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
    <div className="flex flex-col gap-2 rounded-md border border-border bg-surface-subtle p-3">
      {mutation.isError ? (
        <Alert tone="danger">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("applications.slotError")}
        </Alert>
      ) : null}

      <ul className="flex flex-col gap-1.5">
        {(application.available_interview_slots ?? []).map((slot) => (
          <li key={slot.id}>
            <Button variant="outline" size="sm" block disabled={mutation.isPending} onClick={() => mutation.mutate(slot.id)}>
              {new Date(slot.starts_at).toLocaleString()}
            </Button>
          </li>
        ))}
      </ul>

      <Button variant="ghost" size="sm" onClick={onDone}>
        {t("applications.cancel")}
      </Button>
    </div>
  );
}
