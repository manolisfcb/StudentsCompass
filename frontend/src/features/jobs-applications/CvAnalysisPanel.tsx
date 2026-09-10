import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import {
  fetchCvAnalysisStatus,
  startCvAnalysis,
  type CvAnalysisStatus,
} from "@/features/jobs-applications/api";

const POLL_BASE_MS = 3000;
const POLL_MAX_MS = 15000;
/** ~60s of polling, the same bound the legacy 20×3s loop gave up at. */
const POLL_TIMEOUT_MS = 60000;

const TERMINAL_STATUSES = new Set(["completed", "failed"]);

/**
 * "Use my CV" (`jobs.js`'s `loadAutoKeywords`). The legacy version was a
 * hand-rolled `while` loop, fixed 3s interval, hard cap of 20 attempts. This
 * polls through TanStack Query's own `refetchInterval` instead — one place
 * that owns "is this still worth asking about" — with an increasing interval
 * (backoff, plan 08 §8: "no se convierte la SPA en un generador de tráfico")
 * and the same ~60s bound before giving up.
 */
export function CvAnalysisPanel({ onKeywords }: { onKeywords: (keywords: string) => void }) {
  const { t } = useTranslation();
  const [jobId, setJobId] = useState<string | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const startedAtRef = useRef<number>(0);
  const appliedKeywordsRef = useRef<string | null>(null);

  const startMutation = useMutation({
    mutationFn: () => startCvAnalysis(crypto.randomUUID()),
    onSuccess: (job) => {
      startedAtRef.current = Date.now();
      appliedKeywordsRef.current = null;
      setTimedOut(false);
      setJobId(job.job_id);
    },
  });

  const statusQuery = useQuery({
    queryKey: ["cv-analysis", jobId],
    queryFn: () => fetchCvAnalysisStatus(jobId as string),
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status || TERMINAL_STATUSES.has(status)) return false;
      if (Date.now() - startedAtRef.current > POLL_TIMEOUT_MS) return false;
      const attempts = query.state.dataUpdateCount;
      return Math.min(POLL_BASE_MS * 1.5 ** attempts, POLL_MAX_MS);
    },
  });

  const status = statusQuery.data;

  // A plain timer rather than a render-time `Date.now()` comparison: reading
  // the clock or a ref while rendering is impure (the React Compiler flags
  // both), so "did we pass the bound" has to live in an effect instead. Keyed
  // on `jobId` alone — not `status`, which changes on every poll and would
  // otherwise restart the clock each time.
  useEffect(() => {
    if (jobId === null) return undefined;
    const timer = window.setTimeout(() => setTimedOut(true), POLL_TIMEOUT_MS);
    return () => window.clearTimeout(timer);
  }, [jobId]);

  useEffect(() => {
    if (status?.status === "completed" && status.keywords && appliedKeywordsRef.current !== status.keywords) {
      appliedKeywordsRef.current = status.keywords;
      onKeywords(status.keywords);
    }
  }, [status, onKeywords]);

  return (
    <div className="space-y-2">
      <Button
        variant="secondary"
        disabled={startMutation.isPending || (jobId !== null && !isSettled(status))}
        onClick={() => startMutation.mutate()}
      >
        {jobId !== null && !isSettled(status) ? t("jobs.cvAnalysis.analyzing") : t("jobs.cvAnalysis.useMyCv")}
      </Button>

      {startMutation.isError ? (
        <Alert tone="danger">
          {startMutation.error instanceof ApiError && startMutation.error.detail
            ? startMutation.error.detail.message
            : t("jobs.cvAnalysis.error")}
        </Alert>
      ) : null}

      {status?.status === "completed" && status.keywords ? (
        <Alert tone="success">{t("jobs.cvAnalysis.completed", { keywords: status.keywords })}</Alert>
      ) : null}
      {status?.status === "failed" ? (
        <Alert tone="danger">{status.error_message ?? t("jobs.cvAnalysis.failed")}</Alert>
      ) : null}
      {timedOut && !isSettled(status) ? <Alert tone="warning">{t("jobs.cvAnalysis.timeout")}</Alert> : null}
    </div>
  );
}

function isSettled(status: CvAnalysisStatus | undefined): boolean {
  return status !== undefined && TERMINAL_STATUSES.has(status.status);
}
