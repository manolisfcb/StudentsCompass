import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  FormField,
  PageHeader,
  Select,
  Spinner,
  Textarea,
} from "@/components/ui";
import {
  createJobTarget,
  fetchJobTargetsPage,
  JOB_TEXT_MAX_CHARS,
  JOB_TEXT_MIN_CHARS,
  type JobTargetSummary,
} from "@/features/career-lab/api";
import { MatchBadge } from "@/features/career-lab/MatchBadge";
import { fetchResumes, type Resume } from "@/features/profile-resumes/api";

/**
 * Paste a vacancy, read it against a CV (TASK-081, plan 11 C1).
 *
 * The analysis is deterministic and comes back in the create response, so a
 * successful submit lands straight on the analysis with nothing to poll. The
 * list below is every vacancy the student analysed; reopening one is free.
 */
export function JobTargetsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const resumesQuery = useQuery({ queryKey: queryKeys.resumes.list, queryFn: fetchResumes });
  const resumes: Resume[] = resumesQuery.data ?? [];

  const [selectedResumeId, setSelectedResumeId] = useState("");
  const [text, setText] = useState("");
  const [submitted, setSubmitted] = useState(false);
  // One key per distinct paste: a retry after a lost response replays the
  // stored answer instead of filing the same vacancy twice. Editing the text
  // or switching CV is a new request and gets a new key.
  const idempotencyKey = useRef<string | null>(null);

  const resumeId = selectedResumeId !== "" ? selectedResumeId : (resumes[0]?.id ?? "");
  const length = text.trim().length;
  const tooShort = length < JOB_TEXT_MIN_CHARS;
  const tooLong = length > JOB_TEXT_MAX_CHARS;

  const createMutation = useMutation({
    mutationFn: () => {
      idempotencyKey.current ??= crypto.randomUUID();
      return createJobTarget({ text, resume_id: resumeId }, idempotencyKey.current);
    },
    onSuccess: (target) => {
      idempotencyKey.current = null;
      queryClient.setQueryData(queryKeys.careerLab.jobTarget(target.id), target);
      void queryClient.invalidateQueries({ queryKey: queryKeys.careerLab.jobTargets });
      void navigate(`/career-lab/vacancies/${target.id}`);
    },
  });

  function resetRequest() {
    idempotencyKey.current = null;
    if (createMutation.isError) createMutation.reset();
  }

  const textError = tooLong
    ? t("careerLab.vacancy.form.tooLong", { max: JOB_TEXT_MAX_CHARS.toLocaleString() })
    : submitted && tooShort
      ? t("careerLab.vacancy.form.tooShort", { min: JOB_TEXT_MIN_CHARS })
      : undefined;

  return (
    <div className="flex flex-col gap-6">
      <DocumentMeta
        title={t("careerLab.vacancy.seoTitle")}
        description={t("careerLab.vacancy.seoDescription")}
        path="/career-lab/vacancies"
      />

      <PageHeader
        title={t("careerLab.vacancy.title")}
        description={t("careerLab.vacancy.subtitle")}
        breadcrumb={<Link to="/career-lab">{t("careerLab.vacancy.backToLab")}</Link>}
      />

      {resumesQuery.isPending ? (
        <Card>
          <Spinner label={t("async.loading")} />
        </Card>
      ) : resumes.length === 0 ? (
        <EmptyState
          title={t("careerLab.noResume.title")}
          description={t("careerLab.vacancy.noResumeBody")}
          icon="document"
          action={
            <Link to="/profile">
              <Button>{t("careerLab.noResume.upload")}</Button>
            </Link>
          }
        />
      ) : (
        <Card>
          <form
            className="flex flex-col gap-4"
            noValidate
            onSubmit={(event) => {
              event.preventDefault();
              setSubmitted(true);
              if (tooShort || tooLong || resumeId === "") return;
              createMutation.mutate();
            }}
          >
            <FormField label={t("careerLab.resumeLabel")}>
              <Select
                value={resumeId}
                onChange={(event) => {
                  setSelectedResumeId(event.target.value);
                  resetRequest();
                }}
              >
                {resumes.map((resume) => (
                  <option key={resume.id} value={resume.id}>
                    {resume.original_filename}
                  </option>
                ))}
              </Select>
            </FormField>

            <FormField
              label={t("careerLab.vacancy.form.textLabel")}
              hint={t("careerLab.vacancy.form.textHint", {
                length: length.toLocaleString(),
                max: JOB_TEXT_MAX_CHARS.toLocaleString(),
              })}
              {...(textError ? { error: textError } : {})}
            >
              <Textarea
                rows={12}
                value={text}
                placeholder={t("careerLab.vacancy.form.textPlaceholder")}
                onChange={(event) => {
                  setText(event.target.value);
                  resetRequest();
                }}
              />
            </FormField>

            {createMutation.isError ? (
              <Alert tone="danger">{createErrorMessage(createMutation.error, t)}</Alert>
            ) : null}

            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-caption text-ink-muted">{t("careerLab.vacancy.form.noLlm")}</p>
              <Button type="submit" loading={createMutation.isPending} disabled={resumeId === ""}>
                {createMutation.isPending ? t("careerLab.analyzing") : t("careerLab.vacancy.form.submit")}
              </Button>
            </div>
          </form>
        </Card>
      )}

      <JobTargetHistory />
    </div>
  );
}

/**
 * The backend's message where it has a specific one (a CV that vanished, an
 * analysis already running), the generic line otherwise. A 422 here means the
 * client-side bound drifted from the server's, so the server's rule is shown.
 */
function createErrorMessage(error: unknown, t: (key: string) => string): string {
  if (error instanceof ApiError && error.detail) {
    if (error.status === 422) {
      const first = Array.isArray(error.detail.details) ? (error.detail.details[0] as { msg?: unknown }) : undefined;
      if (typeof first?.msg === "string") return first.msg.replace(/^Value error, /, "");
    }
    return error.detail.message;
  }
  return t("careerLab.vacancy.form.error");
}

function JobTargetHistory() {
  const { t } = useTranslation();
  const query = useInfiniteQuery({
    queryKey: queryKeys.careerLab.jobTargets,
    queryFn: ({ pageParam }) => fetchJobTargetsPage(pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => (lastPage.has_more ? (lastPage.next_cursor ?? undefined) : undefined),
  });
  const items = query.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <Card className="flex flex-col gap-4">
      <CardHeader title={t("careerLab.vacancy.history.title")} />
      {query.isPending ? (
        <Spinner label={t("async.loading")} />
      ) : query.isError ? (
        <Alert tone="danger" action={<Button variant="outline" size="sm" onClick={() => void query.refetch()}>{t("async.error.retry")}</Button>}>
          {t("careerLab.vacancy.history.error")}
        </Alert>
      ) : items.length === 0 ? (
        <p className="py-3 text-center text-body-sm text-ink-muted">{t("careerLab.vacancy.history.empty")}</p>
      ) : (
        <>
          <ul className="flex flex-col gap-2">
            {items.map((item) => (
              <li key={item.id}>
                <JobTargetRow item={item} />
              </li>
            ))}
          </ul>
          {query.hasNextPage ? (
            <Button
              variant="outline"
              className="self-center"
              loading={query.isFetchingNextPage}
              onClick={() => void query.fetchNextPage()}
            >
              {t("careerLab.vacancy.history.loadMore")}
            </Button>
          ) : null}
        </>
      )}
    </Card>
  );
}

function JobTargetRow({ item }: { item: JobTargetSummary }) {
  const { t } = useTranslation();
  const subtitle = [item.company, item.location].filter(Boolean).join(" · ");
  return (
    <Link
      to={`/career-lab/vacancies/${item.id}`}
      className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border p-3 transition-colors hover:bg-surface-hover"
    >
      <div className="min-w-0">
        <p className="truncate text-body-sm font-medium text-ink">{item.title ?? t("careerLab.vacancy.untitled")}</p>
        <p className="text-caption text-ink-muted">
          {subtitle ? `${subtitle} · ` : ""}
          {new Date(item.created_at).toLocaleDateString()}
        </p>
      </div>
      {item.status === "failed" ? (
        <Badge tone="danger">{t("careerLab.vacancy.status.failed")}</Badge>
      ) : item.status === "ready" ? (
        <MatchBadge score={item.score} band={item.band} />
      ) : (
        <Badge tone="info">{t("careerLab.vacancy.status.pending")}</Badge>
      )}
    </Link>
  );
}
