import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { Badge, Button, Card, CardHeader, EmptyState, PageHeader, StatCard } from "@/components/ui";
import { fetchCompanyDashboard, type CompanyDashboard } from "@/features/company/api";

/**
 * The recruiter dashboard. All four stat tiles and the recent-postings list
 * are exactly what `GET /companies/me/dashboard` returns; nothing here
 * recomputes a count that `company-candidates.js` used to derive client-side
 * by filtering the applicant list (see TASK-050 completion notes).
 */
export function CompanyDashboardPage() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: ["company", "dashboard"], queryFn: fetchCompanyDashboard });

  return (
    <>
      <DocumentMeta
        title={t("company.dashboard.seoTitle")}
        description={t("company.dashboard.seoDescription")}
        path="/company"
      />
      <AsyncBoundary query={query}>{(dashboard) => <DashboardContent dashboard={dashboard} />}</AsyncBoundary>
    </>
  );
}

function DashboardContent({ dashboard }: { dashboard: CompanyDashboard }) {
  const { t } = useTranslation();
  const recruiterName =
    `${dashboard.current_recruiter.first_name ?? ""} ${dashboard.current_recruiter.last_name ?? ""}`.trim() ||
    dashboard.current_recruiter.email;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={dashboard.company.company_name}
        description={t("company.dashboard.signedInAs", {
          name: recruiterName,
          role: dashboard.current_recruiter.role,
        })}
      />

      {/* The same tile component the student dashboard uses. `.stat-card` used
        * to mean two different things in two sheets, which is exactly why the
        * page scopes had to exist. */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          icon="🏗️"
          hint={t("company.dashboard.kicker.live")}
          label={t("company.dashboard.activePostings")}
          value={dashboard.stats.active_job_postings}
        />
        <StatCard
          icon="📬"
          hint={t("company.dashboard.kicker.pipeline")}
          label={t("company.dashboard.totalApplications")}
          value={dashboard.stats.total_applications}
        />
        <StatCard
          icon="🎙️"
          hint={t("company.dashboard.kicker.inMotion")}
          label={t("company.dashboard.scheduledInterviews")}
          value={dashboard.stats.scheduled_interviews}
        />
        <StatCard
          icon="⭐"
          hint={t("company.dashboard.kicker.shortlist")}
          label={t("company.dashboard.shortlisted")}
          value={dashboard.stats.shortlisted}
        />
      </div>

      <Card>
        <CardHeader
          title={t("company.dashboard.recentPostings")}
          action={
            <Link to="/company/postings">
              <Button variant="outline" size="sm">
                {t("company.dashboard.viewAll")}
              </Button>
            </Link>
          }
        />

        {dashboard.recent_job_postings.length === 0 ? (
          <EmptyState className="mt-4" title={t("company.dashboard.noPostings")} />
        ) : (
          <ul className="mt-4 divide-y divide-border-subtle">
            {dashboard.recent_job_postings.map((posting) => (
              <li key={posting.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <p className="truncate text-card-title text-ink">{posting.title}</p>
                  <p className="text-caption text-ink-muted">
                    {posting.location ?? t("company.dashboard.noLocation")}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <span className="text-caption text-ink-soft tabular-nums">
                    {t("company.dashboard.applicationCount", { count: posting.application_count })}
                  </span>
                  <Badge tone={posting.status === "active" ? "success" : "neutral"}>{posting.status_label}</Badge>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
