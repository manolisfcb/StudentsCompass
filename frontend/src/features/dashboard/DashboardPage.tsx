import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { PageScope } from "@/components/layout/PageScope";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { fetchStudentDashboard, type StudentDashboard } from "@/features/dashboard/api";

/**
 * The student dashboard (`dashboard.html`/`dashboard.js`). Every number here
 * — `stats.*`, `progress.*`, `application_breakdown.*` — is exactly what
 * `GET /dashboard/student` answers; nothing is recomputed client-side
 * (F-15, plan 08 §13).
 *
 * The markup is the template's: `.stats-grid` of `.stat-card`s whose modifier
 * class picks the gradient rule under each tile, then `.main-content-grid` of
 * `.content-card`s, the `.quick-actions` row and the `.notification-card`.
 * `dashboard.css` styles all of it by those names.
 */
export function DashboardPage() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: queryKeys.dashboard.student, queryFn: fetchStudentDashboard });

  return (
    <PageScope name="dashboard">
      <DocumentMeta
        title={t("dashboard.seoTitle")}
        description={t("dashboard.seoDescription")}
        path="/dashboard"
      />
      <AsyncBoundary query={query}>{(dashboard) => <DashboardContent dashboard={dashboard} />}</AsyncBoundary>
    </PageScope>
  );
}

type ProgressKey = "resume" | "linkedin" | "interview_prep" | "portfolio";

function DashboardContent({ dashboard }: { dashboard: StudentDashboard }) {
  const { t } = useTranslation();
  const name = dashboard.user.first_name || dashboard.user.nickname || dashboard.user.email;

  // Literal keys, not a template built from `key`: `tools/check-i18n.mjs`
  // only resolves calls it can find written out in source (see HomePage).
  const progressItems: { key: ProgressKey; label: string }[] = [
    { key: "resume", label: t("dashboard.careerProgress.resume") },
    { key: "linkedin", label: t("dashboard.careerProgress.linkedin") },
    { key: "interview_prep", label: t("dashboard.careerProgress.interviewPrep") },
    { key: "portfolio", label: t("dashboard.careerProgress.portfolio") },
  ];

  return (
    <div className="dashboard-container">
      <div className="dashboard-header page-shell-header">
        <div className="page-shell-header-row">
          <div className="page-shell-header-copy">
            <h2>{t("dashboard.greeting", { name })}</h2>
            <p>{t("dashboard.subtitle")}</p>
          </div>
        </div>
      </div>

      <div className="stats-grid">
        <StatCard icon="📊" value={`${dashboard.stats.overall_progress}%`} label={t("dashboard.stats.overallProgress")} />
        <StatCard
          icon="📝"
          modifier="applications"
          value={dashboard.stats.total_applications}
          label={t("dashboard.stats.totalApplications")}
        />
        <StatCard
          icon="🎯"
          modifier="interviews"
          value={dashboard.stats.interviews_scheduled}
          label={t("dashboard.stats.interviewsScheduled")}
        />
        <StatCard
          icon="🎉"
          modifier="offers"
          value={dashboard.stats.offers_received}
          label={t("dashboard.stats.offersReceived")}
        />
      </div>

      <div className="main-content-grid">
        <div className="content-card career-progress-card">
          <div className="card-header">
            <div className="card-icon" aria-hidden="true">
              🚀
            </div>
            <h3>{t("dashboard.careerProgress.title")}</h3>
          </div>

          <div className="career-progress-list">
            {progressItems.map(({ key, label }) => (
              <Link
                key={key}
                to={dashboard.resource_navigation[key] ?? "/resources"}
                className="progress-item progress-item-link"
              >
                <div className="progress-label">
                  <strong>{label}</strong>
                  <span className="progress-percentage">{dashboard.progress[key]}%</span>
                </div>
                <div className="progress-bar">
                  <div className="progress" style={{ width: `${Math.min(100, dashboard.progress[key])}%` }} />
                </div>
              </Link>
            ))}
          </div>

          <Link to="/resources" className="card-link">
            {t("dashboard.careerProgress.viewResources")}
          </Link>
        </div>

        <div className="content-card">
          <div className="card-header">
            <div className="card-icon" aria-hidden="true">
              📋
            </div>
            <h3>{t("dashboard.applications.title")}</h3>
          </div>

          <ul className="status-list">
            <StatusItem label={t("dashboard.applications.applied")} value={dashboard.application_breakdown.applied} />
            <StatusItem label={t("dashboard.applications.inReview")} value={dashboard.application_breakdown.in_review} />
            <StatusItem
              label={t("dashboard.applications.interviews")}
              value={dashboard.application_breakdown.interviews}
            />
            <StatusItem label={t("dashboard.applications.offers")} value={dashboard.application_breakdown.offers} />
          </ul>

          <Link to="/jobs/applications" className="card-link">
            {t("dashboard.applications.viewAll")}
          </Link>
        </div>

        {dashboard.resources.length > 0 ? (
          <div className="content-card full-width-card">
            <div className="card-header">
              <div className="card-icon" aria-hidden="true">
                📚
              </div>
              <h3>{t("dashboard.recommended.title")}</h3>
            </div>

            <p className="resource-list-copy">{t("dashboard.recommended.subtitle")}</p>

            <ul className="resource-list">
              {dashboard.resources.map((resource) => (
                <li key={resource.title} className="resource-item">
                  <Link to="/resources">
                    <span aria-hidden="true">{resource.icon}</span> {resource.title}
                  </Link>
                </li>
              ))}
            </ul>

            <Link to="/resources" className="card-link">
              {t("dashboard.recommended.explore")}
            </Link>
          </div>
        ) : null}
      </div>

      <div className="quick-actions">
        <QuickAction to="/questionnaire" icon="📝" label={t("dashboard.quickActions.questionnaire")} />
        <QuickAction to="/community" icon="👥" label={t("dashboard.quickActions.community")} />
        <QuickAction to="/profile" icon="👤" label={t("dashboard.quickActions.profile")} />
        <QuickAction to="/resources" icon="📖" label={t("dashboard.quickActions.resources")} />
      </div>

      <div className="notification-card">
        <h4>{t("dashboard.proTip.title")}</h4>
        <p>{t("dashboard.proTip.body")}</p>
      </div>
    </div>
  );
}

function StatCard({
  icon,
  value,
  label,
  modifier,
}: {
  icon: string;
  value: string | number;
  label: string;
  /** Picks the accent bar under the tile (`.stat-card.applications::after`). */
  modifier?: "applications" | "interviews" | "offers";
}) {
  return (
    <div className={`stat-card${modifier ? ` ${modifier}` : ""}`}>
      <div className="stat-icon" aria-hidden="true">
        {icon}
      </div>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function StatusItem({ label, value }: { label: string; value: number }) {
  return (
    <li className="status-item">
      <strong>{label}</strong>
      <span className="status-value">{value}</span>
    </li>
  );
}

function QuickAction({ to, icon, label }: { to: string; icon: string; label: string }) {
  return (
    <Link to={to} className="action-btn">
      <span className="action-icon" aria-hidden="true">
        {icon}
      </span>
      <span>{label}</span>
    </Link>
  );
}
