import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { PageScope } from "@/components/layout/PageScope";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
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
    <PageScope name="company-dashboard" className="dashboard-container">
      <DocumentMeta
        title={t("company.dashboard.seoTitle")}
        description={t("company.dashboard.seoDescription")}
        path="/company"
      />
      <AsyncBoundary query={query}>{(dashboard) => <DashboardContent dashboard={dashboard} />}</AsyncBoundary>
    </PageScope>
  );
}

function DashboardContent({ dashboard }: { dashboard: CompanyDashboard }) {
  const { t } = useTranslation();
  const recruiterName =
    `${dashboard.current_recruiter.first_name ?? ""} ${dashboard.current_recruiter.last_name ?? ""}`.trim() ||
    dashboard.current_recruiter.email;

  return (
    <>
      <div className="dashboard-header company-dashboard-header">
        <h2>{dashboard.company.company_name}</h2>
        <p>
          {t("company.dashboard.signedInAs", { name: recruiterName, role: dashboard.current_recruiter.role })}
        </p>
      </div>

      <div className="stats-grid">
        <StatCard
          modifier="job-postings"
          icon="🏗️"
          kicker={t("company.dashboard.kicker.live")}
          label={t("company.dashboard.activePostings")}
          value={dashboard.stats.active_job_postings}
        />
        <StatCard
          modifier="applications"
          icon="📬"
          kicker={t("company.dashboard.kicker.pipeline")}
          label={t("company.dashboard.totalApplications")}
          value={dashboard.stats.total_applications}
        />
        <StatCard
          modifier="interviews"
          icon="🎙️"
          kicker={t("company.dashboard.kicker.inMotion")}
          label={t("company.dashboard.scheduledInterviews")}
          value={dashboard.stats.scheduled_interviews}
        />
        <StatCard
          modifier="shortlist"
          icon="⭐"
          kicker={t("company.dashboard.kicker.shortlist")}
          label={t("company.dashboard.shortlisted")}
          value={dashboard.stats.shortlisted}
        />
      </div>

      <div className="dashboard-content">
        <section className="section-card">
          <div className="section-card-head">
            <div>
              <h3>{t("company.dashboard.recentPostings")}</h3>
            </div>
            <Link to="/company/postings" className="btn btn-secondary">
              {t("company.dashboard.viewAll")}
            </Link>
          </div>

          {dashboard.recent_job_postings.length === 0 ? (
            <div className="empty-state">
              <p>{t("company.dashboard.noPostings")}</p>
            </div>
          ) : (
            <ul className="job-list">
              {dashboard.recent_job_postings.map((posting) => (
                <li key={posting.id} className="job-item">
                  <div>
                    <div className="job-title">{posting.title}</div>
                    <div className="job-info">{posting.location ?? t("company.dashboard.noLocation")}</div>
                  </div>
                  <div className="job-item-meta">
                    <span className="job-info">
                      {t("company.dashboard.applicationCount", { count: posting.application_count })}
                    </span>
                    <span className={`status-pill ${posting.status}`}>{posting.status_label}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}

/** `.stat-card` in `company-dashboard.css`: icon and kicker, then the number. */
function StatCard({
  modifier,
  icon,
  kicker,
  label,
  value,
}: {
  modifier: string;
  icon: string;
  kicker: string;
  label: string;
  value: number;
}) {
  return (
    <div className={`stat-card ${modifier}`}>
      <div className="stat-card-top">
        <div className="stat-icon" aria-hidden="true">
          {icon}
        </div>
        <div className="stat-kicker">{kicker}</div>
      </div>
      <h3>{label}</h3>
      <div className="number">{value}</div>
    </div>
  );
}
