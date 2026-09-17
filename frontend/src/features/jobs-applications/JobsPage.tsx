import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { Alert, Badge, Button, Card, Checkbox, EmptyState, Input, PageHeader, SectionHeader, Select, Tabs } from "@/components/ui";
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
  const [tab, setTab] = useState<"home" | "cv">("home");

  const searchMutation = useMutation({
    mutationFn: () => searchJobs({ keywords, location, limit, remote: false }),
    onSuccess: setResults,
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    searchMutation.mutate();
  }

  const resultCount = results ? results.students_compass.length + results.linkedin.length : 0;

  return (
    <div className="flex flex-col gap-6">
      <DocumentMeta title={t("jobs.seoTitle")} description={t("jobs.seoDescription")} path="/jobs" />

      <PageHeader
        title={t("jobs.title")}
        description={t("jobs.hero.description")}
        actions={
          <Link to="/jobs/applications">
            <Button variant="outline">{t("jobs.myApplications")}</Button>
          </Link>
        }
      />

      {/* The search bar is the primary action on this screen, so it sits
        * directly under the title rather than inside a hero panel with its own
        * gradient and stat tile. */}
      <Card padding="sm">
        <form className="flex flex-col gap-2 sm:flex-row" onSubmit={handleSubmit}>
          <label className="relative flex-1">
            <span className="sr-only">{t("jobs.keywords")}</span>
            <span
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-muted"
            >
              <SearchIcon />
            </span>
            <Input
              type="search"
              value={keywords}
              onChange={(event) => setKeywords(event.target.value)}
              placeholder={t("jobs.keywordsPlaceholder")}
              className="pl-9"
            />
          </label>

          <label className="relative flex-1">
            <span className="sr-only">{t("jobs.location")}</span>
            <span
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-muted"
            >
              <PinIcon />
            </span>
            <Input
              type="search"
              value={location}
              onChange={(event) => setLocation(event.target.value)}
              placeholder={t("jobs.locationPlaceholder")}
              className="pl-9"
            />
          </label>

          <Select
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value) as (typeof LIMIT_OPTIONS)[number])}
            aria-label={t("jobs.perSearch")}
            className="w-auto"
          >
            {LIMIT_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </Select>

          <Button type="submit" loading={searchMutation.isPending}>
            {searchMutation.isPending ? t("jobs.searching") : t("jobs.search")}
          </Button>
        </form>
      </Card>

      <div aria-live="polite">
        {searchMutation.isError ? (
          <Alert tone="danger">
            {searchMutation.error instanceof ApiError && searchMutation.error.detail
              ? searchMutation.error.detail.message
              : t("jobs.searchError")}
          </Alert>
        ) : null}
      </div>

      <Tabs
        items={[
          { value: "home", label: t("jobs.tabs.home"), ...(results ? { count: resultCount } : {}) },
          { value: "cv", label: t("jobs.tabs.cv") },
        ]}
        value={tab}
        onChange={(value) => setTab(value as "home" | "cv")}
        label={t("jobs.tabs.label")}
        className="self-start"
      />

      {tab === "home" ? (
        <section className="flex flex-col gap-4">
          <SectionHeader
            title={t("jobs.topPicks.title")}
            description={t("jobs.topPicks.subtitle")}
            actions={
              <span className="text-caption text-ink-muted">
                {results ? t("jobs.countResults", { count: resultCount }) : t("jobs.noSearchYet")}
              </span>
            }
          />
          {results ? (
            <SearchResults results={results} />
          ) : (
            <AsyncBoundary query={boardQuery}>{(board) => <JobBoard postings={board} />}</AsyncBoundary>
          )}
        </section>
      ) : (
        <section className="flex flex-col gap-4">
          <SectionHeader title={t("jobs.tabs.cv")} description={t("jobs.cvPanel.subtitle")} />
          <Card className="flex flex-col gap-3">
            <Badge tone="brand" className="self-start">
              {t("jobs.cvPanel.badge")}
            </Badge>
            <h3 className="text-section-title text-ink">{t("jobs.cvPanel.title")}</h3>
            <p className="text-body-sm text-ink-soft">{t("jobs.cvPanel.copy")}</p>
            <CvAnalysisPanel
              onKeywords={(value) => {
                setKeywords(value);
                setTab("home");
                searchMutation.mutate();
              }}
            />
          </Card>
        </section>
      )}
    </div>
  );
}

function SearchIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true" className="size-4">
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.35-4.35" />
    </svg>
  );
}

function PinIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true" className="size-4">
      <path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}

function JobBoard({ postings }: { postings: JobBoardPosting[] }) {
  const { t } = useTranslation();
  if (postings.length === 0) {
    return (
      <EmptyState title={t("jobs.empty")} description={t("jobs.emptyHint")} icon="🔍" />
    );
  }
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-card-title text-ink">{t("jobs.studentsCompassResults")}</h3>
        <span className="text-caption text-ink-muted">{t("jobs.countResults", { count: postings.length })}</span>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        {postings.map((posting) => (
          <BoardCard key={posting.id} posting={posting} />
        ))}
      </div>
    </section>
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
  if (total === 0) {
    return (
      <EmptyState title={t("jobs.empty")} description={t("jobs.emptyHint")} icon="🔍" />
    );
  }
  return (
    <div className="flex flex-col gap-6">
      {results.students_compass.length > 0 ? (
        <section className="flex flex-col gap-3">
          <div className="flex items-baseline justify-between gap-2">
            <h3 className="text-card-title text-ink">{t("jobs.studentsCompassResults")}</h3>
            <span className="text-caption text-ink-muted">
              {t("jobs.countResults", { count: results.students_compass.length })}
            </span>
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
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
        </section>
      ) : null}
      {results.students_compass.length > 0 && results.linkedin.length > 0 ? (
        <div className="flex items-center gap-3 text-caption text-ink-muted">
          <span className="h-px flex-1 bg-border" />
          <span>{t("jobs.moreFromLinkedin")}</span>
          <span className="h-px flex-1 bg-border" />
        </div>
      ) : null}
      {results.linkedin.length > 0 ? (
        <section className="flex flex-col gap-3">
          <div className="flex items-baseline justify-between gap-2">
            <h3 className="text-card-title text-ink">{t("jobs.linkedinResults")}</h3>
            <span className="text-caption text-ink-muted">{t("jobs.countResults", { count: results.linkedin.length })}</span>
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
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
        </section>
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

  // `min-w-0`: a grid item's default `min-width: auto` lets it grow past its
  // track, and this card holds a `whitespace-nowrap` badge and a long job
  // title. Without it the card is wider than its column on a phone and the
  // whole document scrolls sideways.
  return (
    <Card className="flex min-w-0 flex-col gap-3">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="flex min-w-0 gap-3">
          {/* The initials mark stands in for a logo the job board does not
            * have. Monospaced digits keep the two-letter marks the same width
            * so the titles beside them line up down the column. */}
          <span
            aria-hidden="true"
            className="flex size-9 shrink-0 items-center justify-center rounded-md bg-primary-subtle text-label text-primary"
          >
            {companyInitials(company)}
          </span>
          <div className="min-w-0">
            {company ? <p className="truncate text-caption text-ink-soft">{company}</p> : null}
            <h3 className="truncate text-card-title text-ink">{title}</h3>
          </div>
        </div>
        <Badge tone={externalUrl ? "neutral" : "brand"} className="shrink-0">
          {externalUrl ? t("jobs.sourceLinkedin") : t("jobs.sourceInternal")}
        </Badge>
      </div>

      {location ? <Badge className="self-start">{location}</Badge> : null}

      <div className="mt-auto border-t border-border pt-3">
        {applyContext ? (
          applying ? (
            <QuickApplyForm
              jobTitle={title}
              companyId={applyContext.companyId}
              jobPostingId={applyContext.jobPostingId}
              onDone={() => setApplying(false)}
            />
          ) : (
            <Button size="sm" onClick={() => setApplying(true)}>
              {t("jobs.quickApply")}
            </Button>
          )
        ) : externalUrl ? (
          <a href={externalUrl} target="_blank" rel="noopener noreferrer">
            <Button variant="outline" size="sm">
              {t("jobs.viewOnLinkedin")}
            </Button>
          </a>
        ) : null}
      </div>
    </Card>
  );
}

/** `getCompanyInitials` from `jobs.js`: the mark shown where a logo would be. */
function companyInitials(company: string | undefined): string {
  if (!company) return "?";
  return company
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? "")
    .join("");
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
    <div className="flex flex-col gap-3">
      <AsyncBoundary query={resumesQuery}>
        {(resumes) =>
          resumes.length === 0 ? (
            <p className="text-caption text-ink-muted">{t("jobs.noEligibleResumes")}</p>
          ) : (
            <ResumePicker resumes={resumes} value={resumeId} onChange={setResumeId} />
          )
        }
      </AsyncBoundary>

      {mutation.isError ? (
        <p role="alert" className="text-caption text-danger">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("jobs.applyError")}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          disabled={!resumeId}
          loading={mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? t("jobs.applying") : t("jobs.submitApplication")}
        </Button>
        <Button variant="ghost" size="sm" onClick={onDone}>
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
    <fieldset className="flex flex-col gap-1.5">
      <legend className="mb-1 text-label text-ink">{t("jobs.chooseResume")}</legend>
      {resumes.map((resume) => (
        <label key={resume.id} className="flex cursor-pointer items-center gap-2 text-body-sm text-ink-soft">
          <Checkbox type="radio" name="resume" checked={value === resume.id} onChange={() => onChange(resume.id)} />
          <span className="truncate">
            {resume.original_filename} ({resume.overall_score}/10)
          </span>
        </label>
      ))}
    </fieldset>
  );
}
