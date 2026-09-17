import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { PageScope } from "@/components/layout/PageScope";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
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
    <PageScope name="jobs" className="container jobs-page">
      <DocumentMeta title={t("jobs.seoTitle")} description={t("jobs.seoDescription")} path="/jobs" />

      <section className="jobs-shell">
        <header className="jobs-topbar">
          <form className="jobs-searchbar" onSubmit={handleSubmit}>
            <label className="search-field">
              <SearchIcon />
              <span className="sr-only">{t("jobs.keywords")}</span>
              <input
                type="search"
                value={keywords}
                onChange={(event) => setKeywords(event.target.value)}
                placeholder={t("jobs.keywordsPlaceholder")}
              />
            </label>
            <label className="search-field">
              <PinIcon />
              <span className="sr-only">{t("jobs.location")}</span>
              <input
                type="search"
                value={location}
                onChange={(event) => setLocation(event.target.value)}
                placeholder={t("jobs.locationPlaceholder")}
              />
            </label>
            <button type="submit" className="search-action" disabled={searchMutation.isPending}>
              {searchMutation.isPending ? t("jobs.searching") : t("jobs.search")}
            </button>
          </form>

          <div className="jobs-utilitybar">
            <nav className="jobs-tabs" aria-label={t("jobs.tabs.label")}>
              <button
                type="button"
                className={`jobs-tab${tab === "home" ? " active" : ""}`}
                onClick={() => setTab("home")}
              >
                {t("jobs.tabs.home")}
              </button>
              <button type="button" className={`jobs-tab${tab === "cv" ? " active" : ""}`} onClick={() => setTab("cv")}>
                {t("jobs.tabs.cv")}
              </button>
              <Link className="jobs-profile-link" to="/jobs/applications">
                {t("jobs.myApplications")}
              </Link>
            </nav>

            <div className="toolbar-meta">
              <label className="toolbar-select">
                <span className="toolbar-label">{t("jobs.perSearch")}</span>
                <select
                  value={limit}
                  onChange={(event) => setLimit(Number(event.target.value) as (typeof LIMIT_OPTIONS)[number])}
                >
                  {LIMIT_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <div className="toolbar-status" aria-live="polite">
                {searchMutation.isError
                  ? searchMutation.error instanceof ApiError && searchMutation.error.detail
                    ? searchMutation.error.detail.message
                    : t("jobs.searchError")
                  : null}
              </div>
            </div>
          </div>
        </header>

        <div className="jobs-body">
          {tab === "home" ? (
            <section className="tab-panel active">
              <div className="hero-panel">
                <div className="hero-copy">
                  <span className="hero-eyebrow">{t("jobs.hero.eyebrow")}</span>
                  <h1 className="hero-title">{t("jobs.title")}</h1>
                  <p className="hero-description">{t("jobs.hero.description")}</p>
                </div>
                <div className="hero-stats">
                  <div className="hero-stat">
                    <span className="hero-stat-label">{t("jobs.hero.lastResults")}</span>
                    <span className="hero-stat-value">{resultCount}</span>
                    <div className="hero-stat-copy">{t("jobs.hero.lastResultsCopy")}</div>
                  </div>
                </div>
              </div>

              <section>
                <div className="section-head">
                  <div>
                    <h2>{t("jobs.topPicks.title")}</h2>
                    <p>{t("jobs.topPicks.subtitle")}</p>
                  </div>
                  <span className="jobs-count">
                    {results ? t("jobs.countResults", { count: resultCount }) : t("jobs.noSearchYet")}
                  </span>
                </div>

                <div className="board-layout">
                  <div className="results-stack">
                    {results ? (
                      <SearchResults results={results} />
                    ) : (
                      <AsyncBoundary query={boardQuery}>{(board) => <JobBoard postings={board} />}</AsyncBoundary>
                    )}
                  </div>
                </div>
              </section>
            </section>
          ) : (
            <section className="tab-panel active">
              <div className="section-head">
                <div>
                  <h2>{t("jobs.tabs.cv")}</h2>
                  <p>{t("jobs.cvPanel.subtitle")}</p>
                </div>
              </div>
              <div className="highlights-grid">
                <article className="feature-card ai-card">
                  <span className="feature-badge">{t("jobs.cvPanel.badge")}</span>
                  <h2 className="feature-title">{t("jobs.cvPanel.title")}</h2>
                  <p className="feature-copy">{t("jobs.cvPanel.copy")}</p>
                  <div className="feature-actions">
                    <CvAnalysisPanel
                      onKeywords={(value) => {
                        setKeywords(value);
                        setTab("home");
                        searchMutation.mutate();
                      }}
                    />
                  </div>
                </article>
              </div>
            </section>
          )}
        </div>
      </section>
    </PageScope>
  );
}

function SearchIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.35-4.35" />
    </svg>
  );
}

function PinIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
      <path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}

function JobBoard({ postings }: { postings: JobBoardPosting[] }) {
  const { t } = useTranslation();
  if (postings.length === 0) {
    return (
      <div className="empty-state">
        <h3>{t("jobs.empty")}</h3>
        <p>{t("jobs.emptyHint")}</p>
      </div>
    );
  }
  return (
    <section className="result-group">
      <div className="result-group-header">
        <h3 className="result-group-title">{t("jobs.studentsCompassResults")}</h3>
        <span className="result-group-meta">{t("jobs.countResults", { count: postings.length })}</span>
      </div>
      <div className="job-results-grid">
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
      <div className="empty-state">
        <h3>{t("jobs.empty")}</h3>
        <p>{t("jobs.emptyHint")}</p>
      </div>
    );
  }
  return (
    <>
      {results.students_compass.length > 0 ? (
        <section className="result-group">
          <div className="result-group-header">
            <h3 className="result-group-title">{t("jobs.studentsCompassResults")}</h3>
            <span className="result-group-meta">
              {t("jobs.countResults", { count: results.students_compass.length })}
            </span>
          </div>
          <div className="job-results-grid">
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
        <div className="jobs-source-divider">
          <span>{t("jobs.moreFromLinkedin")}</span>
        </div>
      ) : null}
      {results.linkedin.length > 0 ? (
        <section className="result-group">
          <div className="result-group-header">
            <h3 className="result-group-title">{t("jobs.linkedinResults")}</h3>
            <span className="result-group-meta">{t("jobs.countResults", { count: results.linkedin.length })}</span>
          </div>
          <div className="job-results-grid">
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
    </>
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
    <article className="job-result-card">
      <div className="job-result-head">
        <div className="job-detail-company">
          <div className="company-mark" aria-hidden="true">
            {companyInitials(company)}
          </div>
          <div className="job-result-main">
            {company ? <p className="job-result-company">{company}</p> : null}
            <h3 className="job-result-title">{title}</h3>
          </div>
        </div>
        <span className="bookmark-pill">{externalUrl ? t("jobs.sourceLinkedin") : t("jobs.sourceInternal")}</span>
      </div>
      {location ? (
        <div className="job-meta">
          <span className="meta-pill">{location}</span>
        </div>
      ) : null}
      <div className="job-card-actions">
        {applyContext ? (
          applying ? (
            <QuickApplyForm
              jobTitle={title}
              companyId={applyContext.companyId}
              jobPostingId={applyContext.jobPostingId}
              onDone={() => setApplying(false)}
            />
          ) : (
            <button type="button" className="primary-link" onClick={() => setApplying(true)}>
              {t("jobs.quickApply")}
            </button>
          )
        ) : externalUrl ? (
          <a href={externalUrl} target="_blank" rel="noopener noreferrer" className="primary-link">
            {t("jobs.viewOnLinkedin")}
          </a>
        ) : null}
      </div>
    </article>
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
    <div className="quick-apply">
      <AsyncBoundary query={resumesQuery}>
        {(resumes) =>
          resumes.length === 0 ? (
            <p className="job-result-snippet">{t("jobs.noEligibleResumes")}</p>
          ) : (
            <ResumePicker resumes={resumes} value={resumeId} onChange={setResumeId} />
          )
        }
      </AsyncBoundary>
      {mutation.isError ? (
        <p className="job-result-snippet" role="alert">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("jobs.applyError")}
        </p>
      ) : null}
      <div className="job-card-actions">
        <button
          type="button"
          className="primary-link"
          disabled={!resumeId || mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? t("jobs.applying") : t("jobs.submitApplication")}
        </button>
        <button type="button" className="secondary-link" onClick={onDone}>
          {t("jobs.cancel")}
        </button>
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
    <fieldset className="resume-picker">
      <legend>{t("jobs.chooseResume")}</legend>
      {resumes.map((resume) => (
        <label key={resume.id}>
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
