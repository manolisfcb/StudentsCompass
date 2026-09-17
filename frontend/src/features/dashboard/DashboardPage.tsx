import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import {
  Alert,
  Arrow,
  Card,
  CardHeader,
  Icon,
  PageHeader,
  ProgressBar,
  StatCard,
  toIconName,
  type IconName,
} from "@/components/ui";
import { fetchStudentDashboard, type StudentDashboard } from "@/features/dashboard/api";

/**
 * The student dashboard. Every number here — `stats.*`, `progress.*`,
 * `application_breakdown.*` — is exactly what `GET /dashboard/student`
 * answers; nothing is recomputed client-side (F-15, plan 08 §13).
 */
export function DashboardPage() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: queryKeys.dashboard.student, queryFn: fetchStudentDashboard });

  return (
    <>
      <DocumentMeta title={t("dashboard.seoTitle")} description={t("dashboard.seoDescription")} path="/dashboard" />
      <AsyncBoundary query={query}>{(dashboard) => <DashboardContent dashboard={dashboard} />}</AsyncBoundary>
    </>
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

  const statuses = [
    { label: t("dashboard.applications.applied"), value: dashboard.application_breakdown.applied },
    { label: t("dashboard.applications.inReview"), value: dashboard.application_breakdown.in_review },
    { label: t("dashboard.applications.interviews"), value: dashboard.application_breakdown.interviews },
    { label: t("dashboard.applications.offers"), value: dashboard.application_breakdown.offers },
  ];

  const quickActions: { to: string; icon: IconName; label: string }[] = [
    { to: "/questionnaire", icon: "clipboard", label: t("dashboard.quickActions.questionnaire") },
    { to: "/community", icon: "users", label: t("dashboard.quickActions.community") },
    { to: "/profile", icon: "user", label: t("dashboard.quickActions.profile") },
    { to: "/resources", icon: "book", label: t("dashboard.quickActions.resources") },
  ];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("dashboard.greeting", { name })} description={t("dashboard.subtitle")} />

      {/* Two tiles per row on a phone rather than four stacked: the numbers are
        * short, and a column of four full-width tiles pushed the actual content
        * a full screen down. */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          icon="chart"
          value={`${dashboard.stats.overall_progress}%`}
          label={t("dashboard.stats.overallProgress")}
        />
        <StatCard
          icon="document"
          value={dashboard.stats.total_applications}
          label={t("dashboard.stats.totalApplications")}
        />
        <StatCard
          icon="schedule"
          value={dashboard.stats.interviews_scheduled}
          label={t("dashboard.stats.interviewsScheduled")}
        />
        <StatCard icon="trophy" value={dashboard.stats.offers_received} label={t("dashboard.stats.offersReceived")} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="flex flex-col">
          <CardHeader title={t("dashboard.careerProgress.title")} />
          <div className="mt-4 flex flex-1 flex-col gap-3">
            {progressItems.map(({ key, label }) => (
              <Link
                key={key}
                to={dashboard.resource_navigation[key] ?? "/resources"}
                className="-mx-2 rounded-md px-2 py-1.5 transition-colors hover:bg-surface-hover"
              >
                <ProgressBar label={label} value={dashboard.progress[key]} />
              </Link>
            ))}
          </div>
          <Link
            to="/resources"
            className="mt-4 text-body-sm font-medium text-primary transition-colors hover:text-primary-hover"
          >
            {t("dashboard.careerProgress.viewResources")} <Arrow direction="forward" />
          </Link>
        </Card>

        <Card className="flex flex-col">
          <CardHeader title={t("dashboard.applications.title")} />
          <ul className="mt-4 flex-1 divide-y divide-border-subtle">
            {statuses.map((status) => (
              <li key={status.label} className="flex items-center justify-between py-2.5">
                <span className="text-body-sm text-ink-soft">{status.label}</span>
                <span className="text-card-title text-ink tabular-nums">{status.value}</span>
              </li>
            ))}
          </ul>
          <Link
            to="/jobs/applications"
            className="mt-4 text-body-sm font-medium text-primary transition-colors hover:text-primary-hover"
          >
            {t("dashboard.applications.viewAll")} <Arrow direction="forward" />
          </Link>
        </Card>
      </div>

      {dashboard.resources.length > 0 ? (
        <Card>
          <CardHeader
            title={t("dashboard.recommended.title")}
            description={t("dashboard.recommended.subtitle")}
            action={
              <Link
                to="/resources"
                className="text-body-sm font-medium text-primary transition-colors hover:text-primary-hover"
              >
                {t("dashboard.recommended.explore")} <Arrow direction="forward" />
              </Link>
            }
          />
          <ul className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {dashboard.resources.map((resource) => (
              <li key={resource.title}>
                <Link
                  to="/resources"
                  className="flex items-center gap-2.5 rounded-md border border-border px-3 py-2.5 text-body-sm text-ink transition-colors hover:border-border-strong hover:bg-surface-hover"
                >
                  <Icon name={toIconName(resource.icon, "book")} size={18} className="text-primary" />
                  <span className="truncate">{resource.title}</span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {quickActions.map((action) => (
          <Link
            key={action.to}
            to={action.to}
            className="flex items-center gap-2.5 rounded-lg border border-border bg-surface px-4 py-3 text-body-sm font-medium text-ink shadow-xs transition-colors hover:border-border-strong hover:bg-surface-hover"
          >
            <Icon name={action.icon} size={18} className="text-primary" />
            <span className="truncate">{action.label}</span>
          </Link>
        ))}
      </div>

      <Alert tone="info" title={t("dashboard.proTip.title")}>
        {t("dashboard.proTip.body")}
      </Alert>
    </div>
  );
}
