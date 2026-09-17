import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { Alert, Badge } from "@/components/ui";
import { FilePicker } from "@/features/profile-resumes/FilePicker";
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
    <>
      <h3>{t("profile.audit.title")}</h3>
      <p>{t("profile.audit.intro")}</p>
      <AsyncBoundary query={query}>{(attempts) => <AuditUpload remaining={attempts.attempts_remaining} />}</AsyncBoundary>
    </>
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
    return <Alert tone="warning">{t("profile.audit.limitReached")}</Alert>;
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    mutation.reset();
    setResult(null);
    mutation.mutate(file);
  }

  return (
    <div className="flex flex-col gap-3">
      <FilePicker
        title={t("profile.audit.uploadLabel")}
        hint={t("profile.audit.attemptsRemaining", { count: remaining })}
        buttonLabel={mutation.isPending ? t("profile.audit.analyzing") : t("profile.audit.chooseFile")}
        accept={ALLOWED_EXTENSIONS.join(",")}
        inputRef={inputRef}
        busy={mutation.isPending}
        onChange={handleChange}
      />

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
    <div className="flex flex-col gap-4 rounded-lg border border-border bg-surface-subtle p-4">
      {/* The verdict is a badge, not coloured body text: the score is the one
        * thing you look for here, so it gets the strongest treatment on the
        * panel and its tone carries pass/fail without relying on colour alone. */}
      <Badge tone={result.pass_status ? "success" : "danger"} size="md" className="self-start">
        {result.pass_status
          ? t("profile.audit.result.passed", { score: result.overall_score })
          : t("profile.audit.result.failed", { score: result.overall_score })}
      </Badge>
      <p className="text-body-sm text-ink-soft">{result.reason_for_score}</p>
      <p className="text-body-sm text-ink-soft">{result.report}</p>

      {result.main_weaknesses.length > 0 ? (
        <div>
          <h4 className="text-card-title text-ink">{t("profile.audit.result.weaknesses")}</h4>
          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-body-sm text-ink-soft">
            {result.main_weaknesses.map((weakness) => (
              <li key={weakness}>{weakness}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {result.improvements.length > 0 ? (
        <div>
          <h4 className="text-card-title text-ink">{t("profile.audit.result.improvements")}</h4>
          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-body-sm text-ink-soft">
            {result.improvements.map((improvement) => (
              <li key={improvement}>{improvement}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
