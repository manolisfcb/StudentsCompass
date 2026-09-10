import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { fetchStudentDashboard, type StudentDashboard } from "@/features/dashboard/api";

/**
 * The student dashboard (`dashboard.html`/`dashboard.js`). Every number here
 * — `stats.*`, `progress.*`, `application_breakdown.*` — is exactly what
 * `GET /dashboard/student` answers; nothing is recomputed client-side
 * (F-15, plan 08 §13).
 */
export function DashboardPage() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: queryKeys.dashboard.student, queryFn: fetchStudentDashboard });

  return (
    <div className="space-y-8">
      <DocumentMeta
        title={t("dashboard.seoTitle")}
        description={t("dashboard.seoDescription")}
        path="/dashboard"
      />
      <AsyncBoundary query={query}>{(dashboard) => <DashboardContent dashboard={dashboard} />}</AsyncBoundary>
    </div>
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
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-ink">{t("dashboard.greeting", { name })}</h1>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label={t("dashboard.stats.overallProgress")} value={`${dashboard.stats.overall_progress}%`} />
        <StatCard label={t("dashboard.stats.totalApplications")} value={dashboard.stats.total_applications} />
        <StatCard label={t("dashboard.stats.interviewsScheduled")} value={dashboard.stats.interviews_scheduled} />
        <StatCard label={t("dashboard.stats.offersReceived")} value={dashboard.stats.offers_received} />
      </section>

      <section className="rounded-lg border border-border bg-surface p-6">
        <h2 className="text-lg font-semibold text-ink">{t("dashboard.careerProgress.title")}</h2>
        <div className="mt-4 space-y-4">
          {progressItems.map(({ key, label }) => (
            <Link key={key} to={dashboard.resource_navigation[key] ?? "/resources"} className="block group">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-ink group-hover:text-brand">{label}</span>
                <span className="text-ink-muted">{dashboard.progress[key]}%</span>
              </div>
              <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-border">
                <div className="h-full bg-brand" style={{ width: `${Math.min(100, dashboard.progress[key])}%` }} />
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-border bg-surface p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-ink">{t("dashboard.applications.title")}</h2>
          <Link to="/jobs" className="text-sm font-medium text-brand hover:underline">
            {t("dashboard.applications.viewAll")}
          </Link>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <BreakdownStat label={t("dashboard.applications.applied")} value={dashboard.application_breakdown.applied} />
          <BreakdownStat label={t("dashboard.applications.inReview")} value={dashboard.application_breakdown.in_review} />
          <BreakdownStat label={t("dashboard.applications.interviews")} value={dashboard.application_breakdown.interviews} />
          <BreakdownStat label={t("dashboard.applications.offers")} value={dashboard.application_breakdown.offers} />
        </div>
      </section>

      {dashboard.resources.length > 0 ? (
        <section className="rounded-lg border border-border bg-surface p-6">
          <h2 className="text-lg font-semibold text-ink">{t("dashboard.recommended.title")}</h2>
          <ul className="mt-4 grid gap-3 sm:grid-cols-2">
            {dashboard.resources.map((resource) => (
              <li key={resource.title} className="flex items-center gap-3 rounded-md border border-border p-3">
                <span aria-hidden="true" className="text-xl">
                  {resource.icon}
                </span>
                <span className="text-sm text-ink">{resource.title}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="grid gap-3 sm:grid-cols-4">
        <QuickAction to="/questionnaire" label={t("dashboard.quickActions.questionnaire")} />
        <QuickAction to="/community" label={t("dashboard.quickActions.community")} />
        <QuickAction to="/profile" label={t("dashboard.quickActions.profile")} />
        <QuickAction to="/resources" label={t("dashboard.quickActions.resources")} />
      </section>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <span className="block text-2xl font-bold text-ink">{value}</span>
      <span className="text-sm text-ink-soft">{label}</span>
    </div>
  );
}

function BreakdownStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-center">
      <span className="block text-xl font-semibold text-ink">{value}</span>
      <span className="text-xs text-ink-muted">{label}</span>
    </div>
  );
}

function QuickAction({ to, label }: { to: string; label: string }) {
  return (
    <Link
      to={to}
      className="rounded-md border border-border bg-surface p-4 text-center text-sm font-medium text-ink hover:border-brand hover:text-brand"
    >
      {label}
    </Link>
  );
}
