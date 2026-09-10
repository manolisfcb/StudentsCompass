import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { EmptyState } from "@/components/patterns/EmptyState";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { CvAnalysisPanel } from "@/features/jobs-applications/CvAnalysisPanel";
import {
  createApplication,
  fetchEligibleResumes,
  fetchJobBoard,
  searchJobs,
  type EligibleResume,
  type JobBoardPosting,
  type JobSearchResults,
} from "@/features/jobs-applications/api";

const LIMIT_OPTIONS = [10, 25, 50] as const;

/**
 * The job board (`jobs.html`/`jobs.js`). A search replaces the board view
 * with its results — the legacy page never paginates either list, it loads a
 * single bounded batch, which is what `GET /jobs/board` and
 * `POST /job-searches` both still answer with.
 */
export function JobsPage() {
  const { t } = useTranslation();
  const boardQuery = useQuery({ queryKey: ["jobs", "board"], queryFn: fetchJobBoard });

  const [keywords, setKeywords] = useState("");
  const [location, setLocation] = useState("");
  const [limit, setLimit] = useState<(typeof LIMIT_OPTIONS)[number]>(25);
  const [results, setResults] = useState<JobSearchResults | null>(null);

  const searchMutation = useMutation({
    mutationFn: () => searchJobs({ keywords, location, limit, remote: false }),
    onSuccess: setResults,
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    searchMutation.mutate();
  }

  return (
    <div className="space-y-6">
      <DocumentMeta title={t("jobs.seoTitle")} description={t("jobs.seoDescription")} path="/jobs" />
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink">{t("jobs.title")}</h1>
        <Link to="/jobs/applications" className="text-sm font-medium text-brand hover:underline">
          {t("jobs.myApplications")}
        </Link>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
        <label className="space-y-1">
          <span className="block text-sm font-medium text-ink">{t("jobs.keywords")}</span>
          <input
            value={keywords}
            onChange={(event) => setKeywords(event.target.value)}
            className="rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink"
          />
        </label>
        <label className="space-y-1">
          <span className="block text-sm font-medium text-ink">{t("jobs.location")}</span>
          <input
            value={location}
            onChange={(event) => setLocation(event.target.value)}
            className="rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink"
          />
        </label>
        <label className="space-y-1">
          <span className="block text-sm font-medium text-ink">{t("jobs.perSearch")}</span>
          <select
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value) as (typeof LIMIT_OPTIONS)[number])}
            className="rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink"
          >
            {LIMIT_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <Button type="submit" disabled={searchMutation.isPending}>
          {searchMutation.isPending ? t("jobs.searching") : t("jobs.search")}
        </Button>
      </form>

      <CvAnalysisPanel
        onKeywords={(value) => {
          setKeywords(value);
          searchMutation.mutate();
        }}
      />

      {searchMutation.isError ? (
        <Alert tone="danger">
          {searchMutation.error instanceof ApiError && searchMutation.error.detail
            ? searchMutation.error.detail.message
            : t("jobs.searchError")}
        </Alert>
      ) : null}

      {results ? (
        <SearchResults results={results} />
      ) : (
        <AsyncBoundary query={boardQuery}>{(board) => <JobBoard postings={board} />}</AsyncBoundary>
      )}
    </div>
  );
}

function JobBoard({ postings }: { postings: JobBoardPosting[] }) {
  const { t } = useTranslation();
  if (postings.length === 0) return <EmptyState title={t("jobs.empty")} />;
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {postings.map((posting) => (
        <BoardCard key={posting.id} posting={posting} />
      ))}
    </div>
  );
}

function BoardCard({ posting }: { posting: JobBoardPosting }) {
  return (
    <JobCard
      title={posting.title}
      company={posting.company_name ?? undefined}
      location={posting.location ?? undefined}
      applyContext={{ source: "students_compass", jobPostingId: posting.id, companyId: posting.company_id }}
    />
  );
}

function SearchResults({ results }: { results: JobSearchResults }) {
  const { t } = useTranslation();
  const total = results.students_compass.length + results.linkedin.length;
  if (total === 0) return <EmptyState title={t("jobs.empty")} />;
  return (
    <div className="space-y-6">
      {results.students_compass.length > 0 ? (
        <div>
          <h2 className="mb-3 text-lg font-semibold text-ink">{t("jobs.studentsCompassResults")}</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {results.students_compass.map((job) => (
              <JobCard
                key={job.id ?? job.title}
                title={job.title}
                company={job.company}
                location={job.location}
                applyContext={
                  job.id && job.company_id
                    ? { source: "students_compass", jobPostingId: job.id, companyId: job.company_id }
                    : null
                }
              />
            ))}
          </div>
        </div>
      ) : null}
      {results.linkedin.length > 0 ? (
        <div>
          <h2 className="mb-3 text-lg font-semibold text-ink">{t("jobs.linkedinResults")}</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {results.linkedin.map((job) => (
              <JobCard
                key={job.url ?? job.title}
                title={job.title}
                company={job.company}
                location={job.location}
                externalUrl={job.url ?? undefined}
                applyContext={null}
              />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

interface ApplyContext {
  source: "students_compass";
  jobPostingId: string;
  companyId: string;
}

function JobCard({
  title,
  company,
  location,
  externalUrl,
  applyContext,
}: {
  title: string;
  company?: string | undefined;
  location?: string | undefined;
  externalUrl?: string | undefined;
  applyContext: ApplyContext | null;
}) {
  const { t } = useTranslation();
  const [applying, setApplying] = useState(false);

  return (
    <article className="rounded-lg border border-border bg-surface p-4">
      <h3 className="font-semibold text-ink">{title}</h3>
      {company ? <p className="text-sm text-ink-soft">{company}</p> : null}
      {location ? <p className="text-xs text-ink-muted">{location}</p> : null}
      <div className="mt-3">
        {applyContext ? (
          applying ? (
            <QuickApplyForm
              jobTitle={title}
              companyId={applyContext.companyId}
              jobPostingId={applyContext.jobPostingId}
              onDone={() => setApplying(false)}
            />
          ) : (
            <Button variant="secondary" onClick={() => setApplying(true)}>
              {t("jobs.quickApply")}
            </Button>
          )
        ) : externalUrl ? (
          <a
            href={externalUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-brand hover:underline"
          >
            {t("jobs.viewOnLinkedin")}
          </a>
        ) : null}
      </div>
    </article>
  );
}

function QuickApplyForm({
  jobTitle,
  companyId,
  jobPostingId,
  onDone,
}: {
  jobTitle: string;
  companyId: string;
  jobPostingId: string;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [resumeId, setResumeId] = useState<string | null>(null);
  const resumesQuery = useQuery({ queryKey: ["applications", "eligible-resumes"], queryFn: fetchEligibleResumes });

  const mutation = useMutation({
    mutationFn: () =>
      createApplication(
        { job_title: jobTitle, company_id: companyId, job_posting_id: jobPostingId, resume_id: resumeId },
        crypto.randomUUID(),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["applications"] });
      onDone();
    },
  });

  return (
    <div className="space-y-2 rounded-md border border-border p-3">
      <AsyncBoundary query={resumesQuery}>
        {(resumes) =>
          resumes.length === 0 ? (
            <p className="text-xs text-ink-muted">{t("jobs.noEligibleResumes")}</p>
          ) : (
            <ResumePicker resumes={resumes} value={resumeId} onChange={setResumeId} />
          )
        }
      </AsyncBoundary>
      {mutation.isError ? (
        <Alert tone="danger">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("jobs.applyError")}
        </Alert>
      ) : null}
      <div className="flex gap-2">
        <Button disabled={!resumeId || mutation.isPending} onClick={() => mutation.mutate()}>
          {mutation.isPending ? t("jobs.applying") : t("jobs.submitApplication")}
        </Button>
        <Button variant="ghost" onClick={onDone}>
          {t("jobs.cancel")}
        </Button>
      </div>
    </div>
  );
}

function ResumePicker({
  resumes,
  value,
  onChange,
}: {
  resumes: EligibleResume[];
  value: string | null;
  onChange: (resumeId: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <fieldset className="space-y-1">
      <legend className="text-xs font-medium text-ink">{t("jobs.chooseResume")}</legend>
      {resumes.map((resume) => (
        <label key={resume.id} className="flex items-center gap-2 text-xs text-ink-soft">
          <input
            type="radio"
            name="resume"
            checked={value === resume.id}
            onChange={() => onChange(resume.id)}
          />
          {resume.original_filename} ({resume.overall_score}/10)
        </label>
      ))}
    </fieldset>
  );
}
