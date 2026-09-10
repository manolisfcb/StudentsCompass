import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import {
  type CourseAuditResult,
  fetchCourseAuditAttempts,
  uploadResumeForCourseAudit,
} from "@/features/profile-resumes/api";

const ALLOWED_EXTENSIONS = [".pdf", ".docx"];

/**
 * The CV course-audit widget, moved from the resource-lesson page
 * (`resource_detail.js`) into the profile/resume vertical that owns the
 * `/resume-course-audits` endpoint (TASK-047 Scope: "la auditoría de CV").
 * The lesson that used to host it belongs to TASK-048, which has not migrated
 * yet; the audit itself has no lesson dependency, so it stands on its own here
 * rather than waiting on that vertical.
 */
export function ResumeAuditWidget() {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: queryKeys.resumes.courseAuditAttempts,
    queryFn: fetchCourseAuditAttempts,
  });

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-ink">{t("profile.audit.title")}</h2>
      <p className="text-sm text-ink-soft">{t("profile.audit.intro")}</p>
      <AsyncBoundary query={query}>{(attempts) => <AuditUpload remaining={attempts.attempts_remaining} />}</AsyncBoundary>
    </div>
  );
}

function AuditUpload({ remaining }: { remaining: number }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());
  const [result, setResult] = useState<CourseAuditResult | null>(null);

  const mutation = useMutation({
    mutationFn: (file: File) => uploadResumeForCourseAudit(file, idempotencyKey),
    onSuccess: async (data) => {
      setResult(data);
      // A fresh key for the *next* upload; this one is done being replayable.
      setIdempotencyKey(crypto.randomUUID());
      await queryClient.invalidateQueries({ queryKey: queryKeys.resumes.courseAuditAttempts });
      if (inputRef.current) inputRef.current.value = "";
    },
  });

  if (remaining <= 0) {
    return <Alert tone="info">{t("profile.audit.limitReached")}</Alert>;
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    mutation.reset();
    setResult(null);
    mutation.mutate(file);
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-ink-muted">{t("profile.audit.attemptsRemaining", { count: remaining })}</p>
      <div className="rounded-lg border border-dashed border-border bg-surface p-4">
        <label className="flex cursor-pointer flex-col items-center gap-2 text-center text-sm text-ink-soft">
          <span className="font-medium text-ink">{t("profile.audit.uploadLabel")}</span>
          <input
            ref={inputRef}
            type="file"
            accept={ALLOWED_EXTENSIONS.join(",")}
            className="sr-only"
            onChange={handleChange}
            disabled={mutation.isPending}
          />
          <Button
            type="button"
            variant="secondary"
            disabled={mutation.isPending}
            onClick={() => inputRef.current?.click()}
          >
            {mutation.isPending ? t("profile.audit.analyzing") : t("profile.audit.chooseFile")}
          </Button>
        </label>
      </div>

      {mutation.isError ? (
        <Alert tone="danger">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("profile.audit.error")}
        </Alert>
      ) : null}

      {result ? <AuditResult result={result} /> : null}
    </div>
  );
}

function AuditResult({ result }: { result: CourseAuditResult }) {
  const { t } = useTranslation();
  return (
    <div className="space-y-3 rounded-lg border border-border bg-surface p-4">
      <Alert tone={result.pass_status ? "success" : "warning"}>
        {result.pass_status
          ? t("profile.audit.result.passed", { score: result.overall_score })
          : t("profile.audit.result.failed", { score: result.overall_score })}
      </Alert>
      <p className="text-sm text-ink-soft">{result.reason_for_score}</p>
      <p className="text-sm text-ink-soft">{result.report}</p>

      {result.main_weaknesses.length > 0 ? (
        <div>
          <h3 className="text-sm font-semibold text-ink">{t("profile.audit.result.weaknesses")}</h3>
          <ul className="mt-1 list-inside list-disc text-sm text-ink-soft">
            {result.main_weaknesses.map((weakness) => (
              <li key={weakness}>{weakness}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {result.improvements.length > 0 ? (
        <div>
          <h3 className="text-sm font-semibold text-ink">{t("profile.audit.result.improvements")}</h3>
          <ul className="mt-1 list-inside list-disc text-sm text-ink-soft">
            {result.improvements.map((improvement) => (
              <li key={improvement}>{improvement}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
