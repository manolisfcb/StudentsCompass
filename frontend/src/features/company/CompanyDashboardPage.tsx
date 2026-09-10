import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { EmptyState } from "@/components/patterns/EmptyState";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { fetchCompanyDashboard, type CompanyDashboard } from "@/features/company/api";

/**
 * The recruiter dashboard (`company-dashboard.html`/`.js`). All four stat
 * tiles and the recent-postings list are exactly what `GET
 * /companies/me/dashboard` returns; nothing here recomputes a count that
 * `company-candidates.js` used to derive client-side by filtering the
 * applicant list (see TASK-050 completion notes).
 */
export function CompanyDashboardPage() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: ["company", "dashboard"], queryFn: fetchCompanyDashboard });

  return (
    <div className="space-y-8">
      <DocumentMeta
        title={t("company.dashboard.seoTitle")}
        description={t("company.dashboard.seoDescription")}
        path="/company"
      />
      <AsyncBoundary query={query}>{(dashboard) => <DashboardContent dashboard={dashboard} />}</AsyncBoundary>
    </div>
  );
}

function DashboardContent({ dashboard }: { dashboard: CompanyDashboard }) {
  const { t } = useTranslation();
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-ink">{dashboard.company.company_name}</h1>
        <p className="text-sm text-ink-soft">
          {t("company.dashboard.signedInAs", {
            name: `${dashboard.current_recruiter.first_name ?? ""} ${dashboard.current_recruiter.last_name ?? ""}`.trim() || dashboard.current_recruiter.email,
            role: dashboard.current_recruiter.role,
          })}
        </p>
      </div>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label={t("company.dashboard.activePostings")} value={dashboard.stats.active_job_postings} />
        <StatCard label={t("company.dashboard.totalApplications")} value={dashboard.stats.total_applications} />
        <StatCard label={t("company.dashboard.scheduledInterviews")} value={dashboard.stats.scheduled_interviews} />
        <StatCard label={t("company.dashboard.shortlisted")} value={dashboard.stats.shortlisted} />
      </section>

      <section className="rounded-lg border border-border bg-surface p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-ink">{t("company.dashboard.recentPostings")}</h2>
          <Link to="/company/postings" className="text-sm font-medium text-brand hover:underline">
            {t("company.dashboard.viewAll")}
          </Link>
        </div>
        {dashboard.recent_job_postings.length === 0 ? (
          <div className="mt-4">
            <EmptyState title={t("company.dashboard.noPostings")} />
          </div>
        ) : (
          <ul className="mt-4 divide-y divide-border">
            {dashboard.recent_job_postings.map((posting) => (
              <li key={posting.id} className="flex items-center justify-between py-3 text-sm">
                <div>
                  <p className="font-medium text-ink">{posting.title}</p>
                  <p className="text-ink-muted">{posting.location ?? t("company.dashboard.noLocation")}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-ink-muted">
                    {t("company.dashboard.applicationCount", { count: posting.application_count })}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      posting.status === "active" ? "bg-success/10 text-success" : "bg-border text-ink-muted"
                    }`}
                  >
                    {posting.status_label}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <span className="block text-2xl font-bold text-ink">{value}</span>
      <span className="text-sm text-ink-soft">{label}</span>
    </div>
  );
}
