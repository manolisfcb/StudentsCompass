import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  FormField,
  Input,
  PageHeader,
  Select,
  Spinner,
  StatCard,
} from "@/components/ui";
import type { BadgeTone } from "@/components/ui";
import { queryKeys } from "@/api/queryKeys";
import { ApiError } from "@/api/client";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { fetchResumes, type Resume } from "@/features/profile-resumes/api";
import {
  addManualResumeSkill,
  deleteResumeSkill,
  evaluateLearningRouteBaselines,
  fetchGapAnalysis,
  fetchLearningRouteRuns,
  fetchResumeSkillReview,
  fetchTargetRoles,
  optimizeLearningRoute,
  syncResumeSkills,
  updateResumeSkillStatus,
  type BaselineEvaluation,
  type GapAnalysis,
  type ReviewedSkill,
  type RouteOptimization,
  type RouteRun,
  type TargetRole,
} from "@/features/career-lab/api";

/**
 * Career Optimization Lab (`career_lab.html`/`career_lab.js`, TASK-052).
 *
 * Trimmed from the legacy single-page dashboard: no CV upload widget (the
 * profile screen already owns that), no radar chart, and the catalog-quality
 * and embedding-status diagnostics panels are left out as admin-facing
 * signal rather than part of the student workflow. Everything the student
 * actually acts on — skill review, gap analysis, route optimization, baseline
 * comparison, route history — is here, and every number is the backend's own.
 */
export function CareerLabPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const resumesQuery = useQuery({ queryKey: queryKeys.resumes.list, queryFn: fetchResumes });
  const rolesQuery = useQuery({ queryKey: queryKeys.careerLab.targetRoles, queryFn: fetchTargetRoles });
  const routeRunsQuery = useQuery({
    queryKey: queryKeys.careerLab.routeRuns,
    queryFn: () => fetchLearningRouteRuns(5),
  });

  const [selectedResumeId, setSelectedResumeId] = useState("");
  const [selectedTargetRole, setSelectedTargetRole] = useState("");
  const [gapAnalysis, setGapAnalysis] = useState<GapAnalysis | null>(null);
  const [route, setRoute] = useState<RouteOptimization | null>(null);
  const [baseline, setBaseline] = useState<BaselineEvaluation | null>(null);
  const [budget, setBudget] = useState(150);
  const [hours, setHours] = useState(40);
  const [maxCourses, setMaxCourses] = useState(4);
  const [manualSkillText, setManualSkillText] = useState("");

  const resumes: Resume[] = resumesQuery.data ?? [];
  const roles: TargetRole[] = rolesQuery.data ?? [];

  // Derived, not stored: an explicit selection wins, otherwise the first
  // fetched option. Deriving in render (rather than an effect that calls
  // setState once the lists arrive) avoids the extra render pass entirely.
  const resumeId = selectedResumeId !== "" ? selectedResumeId : (resumes[0]?.id ?? "");
  const targetRole = selectedTargetRole !== "" ? selectedTargetRole : (roles[0]?.target_role ?? "");

  const skillReviewQuery = useQuery({
    queryKey: queryKeys.careerLab.skillReview(resumeId),
    queryFn: () => fetchResumeSkillReview(resumeId),
    enabled: resumeId !== "",
  });

  const analyzeMutation = useMutation({
    mutationFn: async () => {
      await syncResumeSkills(resumeId);
      return fetchGapAnalysis(resumeId, targetRole);
    },
    onSuccess: (analysis) => {
      setGapAnalysis(analysis);
      void queryClient.invalidateQueries({ queryKey: queryKeys.careerLab.skillReview(resumeId) });
    },
  });

  const skillStatusMutation = useMutation({
    mutationFn: (variables: { resumeSkillId: string; status: "confirmed" | "rejected" }) =>
      updateResumeSkillStatus(resumeId, variables.resumeSkillId, variables.status),
    onSuccess: (review) => {
      queryClient.setQueryData(queryKeys.careerLab.skillReview(resumeId), review);
    },
  });

  const deleteSkillMutation = useMutation({
    mutationFn: (resumeSkillId: string) => deleteResumeSkill(resumeId, resumeSkillId),
    onSuccess: (review) => {
      queryClient.setQueryData(queryKeys.careerLab.skillReview(resumeId), review);
    },
  });

  const manualSkillMutation = useMutation({
    mutationFn: (normalizedName: string) => addManualResumeSkill(resumeId, normalizedName),
    onSuccess: (review) => {
      queryClient.setQueryData(queryKeys.careerLab.skillReview(resumeId), review);
      setManualSkillText("");
    },
  });

  const routeMutation = useMutation({
    mutationFn: async () => {
      const payload = { resume_id: resumeId, target_role: targetRole, budget, available_hours: hours, max_courses: maxCourses };
      const optimized = await optimizeLearningRoute(payload, crypto.randomUUID());
      const evaluated = await evaluateLearningRouteBaselines(payload, crypto.randomUUID());
      return { optimized, evaluated };
    },
    onSuccess: ({ optimized, evaluated }) => {
      setRoute(optimized);
      setBaseline(evaluated);
      void queryClient.invalidateQueries({ queryKey: queryKeys.careerLab.routeRuns });
    },
  });

  const hasResume = resumes.length > 0;

  return (
    <div className="flex flex-col gap-6">
      <DocumentMeta title={t("careerLab.seoTitle")} description={t("careerLab.seoDescription")} path="/career-lab" />

      <PageHeader
        title={t("careerLab.title")}
        description={t("careerLab.subtitle")}
        breadcrumb={<Badge tone="brand">{t("careerLab.kicker")}</Badge>}
      />

      {hasResume ? (
        <Card>
          <form
            className="flex flex-col gap-3 sm:flex-row sm:items-end"
            onSubmit={(event) => {
              event.preventDefault();
              analyzeMutation.mutate();
            }}
          >
            <FormField label={t("careerLab.resumeLabel")} className="sm:flex-1">
              <Select value={resumeId} onChange={(event) => setSelectedResumeId(event.target.value)}>
                {resumes.map((resume) => (
                  <option key={resume.id} value={resume.id}>
                    {resume.original_filename}
                  </option>
                ))}
              </Select>
            </FormField>

            <FormField label={t("careerLab.targetRoleLabel")} className="sm:flex-1">
              <Select value={targetRole} onChange={(event) => setSelectedTargetRole(event.target.value)}>
                {roles.map((role) => (
                  <option key={role.target_role} value={role.target_role}>
                    {role.target_role}
                  </option>
                ))}
              </Select>
            </FormField>

            <Button
              type="submit"
              disabled={resumeId === "" || targetRole === ""}
              loading={analyzeMutation.isPending}
            >
              {analyzeMutation.isPending ? t("careerLab.analyzing") : t("careerLab.analyzeButton")}
            </Button>
          </form>
        </Card>
      ) : null}

      {resumesQuery.isPending ? (
        <Card>
          <Spinner label={t("async.loading")} />
        </Card>
      ) : !hasResume ? (
        <EmptyState
          title={t("careerLab.noResume.title")}
          description={t("careerLab.noResume.body")}
          icon="document"
          action={
            <Link to="/profile">
              <Button>{t("careerLab.noResume.upload")}</Button>
            </Link>
          }
        />
      ) : (
        <>
          {analyzeMutation.isError ? (
            <Alert tone="danger">
              {analyzeMutation.error instanceof ApiError && analyzeMutation.error.detail
                ? analyzeMutation.error.detail.message
                : t("careerLab.status.error")}
            </Alert>
          ) : null}

          <SkillReviewPanel
            resumeId={resumeId}
            review={skillReviewQuery.data}
            isLoading={skillReviewQuery.isPending}
            manualSkillText={manualSkillText}
            onManualSkillTextChange={setManualSkillText}
            onConfirm={(id) => skillStatusMutation.mutate({ resumeSkillId: id, status: "confirmed" })}
            onReject={(id) => skillStatusMutation.mutate({ resumeSkillId: id, status: "rejected" })}
            onDelete={(id) => deleteSkillMutation.mutate(id)}
            onAddManual={() => {
              if (manualSkillText.trim() !== "") manualSkillMutation.mutate(manualSkillText.trim());
            }}
            addPending={manualSkillMutation.isPending}
          />

          {gapAnalysis ? <GapAnalysisPanels analysis={gapAnalysis} /> : null}

          <RouteOptimizationPanel
            budget={budget}
            hours={hours}
            maxCourses={maxCourses}
            onBudgetChange={setBudget}
            onHoursChange={setHours}
            onMaxCoursesChange={setMaxCourses}
            onGenerate={() => routeMutation.mutate()}
            disabled={resumeId === "" || targetRole === "" || routeMutation.isPending}
            isPending={routeMutation.isPending}
            isError={routeMutation.isError}
            route={route}
          />

          <BaselineComparisonPanel baseline={baseline} isPending={routeMutation.isPending} />

          <RouteHistoryPanel runs={routeRunsQuery.data ?? []} />
        </>
      )}
    </div>
  );
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "--";
  return `${Math.round(value * 100)}%`;
}

function formatMoney(value: number | null | undefined): string {
  if (value === null || value === undefined) return "--";
  return `$${value.toFixed(0)}`;
}

function formatHoursValue(value: number | null | undefined): string {
  if (value === null || value === undefined) return "--";
  return `${value.toFixed(0)}h`;
}

/** A skill's review state, coloured the way the rest of the app colours state. */
const SKILL_STATUS_TONES: Record<string, BadgeTone> = {
  confirmed: "success",
  rejected: "danger",
  manual: "brand",
  detected: "neutral",
};

function skillStatusLabel(status: string | null | undefined, t: (key: string) => string): string {
  switch (status) {
    case "confirmed":
      return t("careerLab.skillReview.status.confirmed");
    case "rejected":
      return t("careerLab.skillReview.status.rejected");
    case "manual":
      return t("careerLab.skillReview.status.manual");
    default:
      return t("careerLab.skillReview.status.detected");
  }
}

/** Insight severity mapped onto the shared status tones. */
const SEVERITY_TONES: Record<string, BadgeTone> = {
  positive: "success",
  high: "danger",
  medium: "warning",
  info: "info",
};

function severityLabel(severity: string, t: (key: string) => string): string {
  switch (severity) {
    case "positive":
      return t("careerLab.insights.severity.positive");
    case "high":
      return t("careerLab.insights.severity.high");
    case "medium":
      return t("careerLab.insights.severity.medium");
    default:
      return t("careerLab.insights.severity.info");
  }
}

function methodLabel(method: string, t: (key: string) => string): string {
  switch (method) {
    case "cp_sat_route_v1":
      return t("careerLab.baseline.methods.cpSat");
    case "heuristic_route_v1":
      return t("careerLab.baseline.methods.heuristic");
    case "similarity_only":
      return t("careerLab.baseline.methods.similarity");
    case "cheapest_feasible":
      return t("careerLab.baseline.methods.cheapest");
    case "highest_rated_feasible":
      return t("careerLab.baseline.methods.highestRated");
    case "random_feasible_seeded":
      return t("careerLab.baseline.methods.random");
    default:
      return method;
  }
}

function SkillReviewPanel({
  resumeId,
  review,
  isLoading,
  manualSkillText,
  onManualSkillTextChange,
  onConfirm,
  onReject,
  onDelete,
  onAddManual,
  addPending,
}: {
  resumeId: string;
  review: { skills: ReviewedSkill[] } | undefined;
  isLoading: boolean;
  manualSkillText: string;
  onManualSkillTextChange: (value: string) => void;
  onConfirm: (resumeSkillId: string) => void;
  onReject: (resumeSkillId: string) => void;
  onDelete: (resumeSkillId: string) => void;
  onAddManual: () => void;
  addPending: boolean;
}) {
  const { t } = useTranslation();
  const skills = review?.skills ?? [];
  const counts = skills.reduce<Record<string, number>>((acc, skill) => {
    const status = skill.status ?? "detected";
    acc[status] = (acc[status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <Card className="flex flex-col gap-4">
      <CardHeader
        title={t("careerLab.skillReview.title")}
        action={
          <div className="flex flex-wrap gap-1.5">
            <Badge>{t("careerLab.skillReview.counts.detected", { count: counts.detected ?? 0 })}</Badge>
            <Badge tone="success">
              {t("careerLab.skillReview.counts.confirmed", { count: counts.confirmed ?? 0 })}
            </Badge>
            <Badge tone="brand">{t("careerLab.skillReview.counts.manual", { count: counts.manual ?? 0 })}</Badge>
          </div>
        }
      />

      <form
        className="flex items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          onAddManual();
        }}
      >
        <FormField label={t("careerLab.skillReview.addLabel")} className="flex-1">
          <Input
            value={manualSkillText}
            onChange={(event) => onManualSkillTextChange(event.target.value)}
            placeholder={t("careerLab.skillReview.addPlaceholder")}
          />
        </FormField>
        <Button type="submit" disabled={resumeId === ""} loading={addPending}>
          {t("careerLab.skillReview.addButton")}
        </Button>
      </form>

      <div className="flex flex-col gap-2">
        {isLoading ? (
          <Spinner label={t("async.loading")} />
        ) : skills.length === 0 ? (
          <p className="py-4 text-center text-body-sm text-ink-muted">{t("careerLab.skillReview.empty")}</p>
        ) : (
          skills.map((skill) => (
            <div
              key={skill.resume_skill_id ?? skill.skill_id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-2.5"
            >
              <div className="flex min-w-0 items-center gap-2">
                <Badge tone={SKILL_STATUS_TONES[skill.status ?? "detected"] ?? "neutral"}>
                  {skillStatusLabel(skill.status, t)}
                </Badge>
                <p className="truncate text-body-sm text-ink">{skill.display_name}</p>
              </div>
              {skill.resume_skill_id ? (
                <div className="flex shrink-0 gap-1.5">
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={skill.status === "confirmed" || skill.status === "manual"}
                    onClick={() => onConfirm(skill.resume_skill_id as string)}
                  >
                    {t("careerLab.skillReview.confirm")}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={skill.status === "rejected" || skill.status === "manual"}
                    onClick={() => onReject(skill.resume_skill_id as string)}
                  >
                    {t("careerLab.skillReview.reject")}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => onDelete(skill.resume_skill_id as string)}>
                    {t("careerLab.skillReview.remove")}
                  </Button>
                </div>
              ) : null}
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

function GapAnalysisPanels({ analysis }: { analysis: GapAnalysis }) {
  const { t } = useTranslation();
  const matchedIds = new Set(analysis.matched_required_skills.map((skill) => skill.skill_id));
  const topRequired = [...analysis.required_skills]
    .sort((a, b) => (b.importance_score ?? 0) - (a.importance_score ?? 0))
    .slice(0, 10);
  const missing = analysis.priority_missing_skills.length > 0 ? analysis.priority_missing_skills : analysis.missing_skills;

  return (
    <>
      <section aria-label={t("careerLab.metrics.label")} className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label={t("careerLab.metrics.readiness")} value={formatPercent(analysis.overall_readiness_score)} />
        <StatCard label={t("careerLab.metrics.match")} value={formatPercent(analysis.match_score)} />
        <StatCard label={t("careerLab.metrics.context")} value={formatPercent(analysis.context_similarity_score)} />
        <StatCard label={t("careerLab.metrics.gaps")} value={String(missing.length)} />
      </section>

      <Card className="flex flex-col gap-4">
        <CardHeader title={t("careerLab.comparison.title")} />
        <div className="flex flex-col gap-2">
          {topRequired.length === 0 ? (
            <p className="py-3 text-center text-body-sm text-ink-muted">{t("careerLab.comparison.empty")}</p>
          ) : (
            topRequired.map((skill) => {
              const matched = matchedIds.has(skill.skill_id);
              return (
                <div
                  key={skill.skill_id}
                  className="flex items-center justify-between gap-3 rounded-md bg-surface-subtle px-3 py-2"
                >
                  <span className="min-w-0 truncate text-body-sm text-ink">{skill.display_name}</span>
                  <Badge tone={matched ? "success" : "warning"}>
                    {matched ? t("careerLab.comparison.matched") : t("careerLab.comparison.gap")}
                  </Badge>
                </div>
              );
            })
          )}
        </div>
      </Card>

      <Card className="flex flex-col gap-4">
        <CardHeader title={t("careerLab.insights.title")} />
        <div className="flex flex-col gap-2">
          {analysis.gap_insights.length === 0 ? (
            <p className="py-3 text-center text-body-sm text-ink-muted">{t("careerLab.insights.empty")}</p>
          ) : (
            analysis.gap_insights.map((insight, index) => (
              <div
                key={`${insight.insight_type}-${index}`}
                className="flex flex-wrap items-start gap-2 rounded-md bg-surface-subtle px-3 py-2"
              >
                <Badge tone={SEVERITY_TONES[insight.severity] ?? "info"}>
                  {severityLabel(insight.severity, t)}
                </Badge>
                <p className="min-w-0 flex-1 text-body-sm text-ink-soft">{insight.message}</p>
              </div>
            ))
          )}
        </div>
      </Card>

      <Card className="flex flex-col gap-4">
        <CardHeader title={t("careerLab.market.title")} />
        <div className="flex flex-col gap-2">
          {analysis.market_signals.skills.length === 0 ? (
            <p className="py-3 text-center text-body-sm text-ink-muted">{t("careerLab.market.empty")}</p>
          ) : (
            <>
              <p className="py-3 text-center text-body-sm text-ink-muted">
                {t("careerLab.market.syncedPostings", { count: analysis.market_signals.synced_job_postings_count })}
              </p>
              {analysis.market_signals.skills.slice(0, 5).map((skill) => (
                <div
                  key={skill.skill_id}
                  className="flex items-center justify-between gap-3 rounded-md bg-surface-subtle px-3 py-2"
                >
                  <span className="min-w-0 truncate text-body-sm text-ink">{skill.display_name}</span>
                  <span className="text-body-sm text-ink-soft tabular-nums">{formatPercent(skill.demand_score)}</span>
                </div>
              ))}
            </>
          )}
        </div>
      </Card>

      <Card className="flex flex-col gap-4">
        <CardHeader title={t("careerLab.courses.title")} />
        <div className="flex flex-col gap-2">
          {analysis.recommended_courses.length === 0 ? (
            <p className="py-3 text-center text-body-sm text-ink-muted">{t("careerLab.courses.empty")}</p>
          ) : (
            analysis.recommended_courses.slice(0, 5).map((course) => (
              <div
                key={course.course_id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-3"
              >
                <div className="min-w-0">
                  <p className="truncate text-body-sm font-medium text-ink">{course.title}</p>
                  <p className="text-caption text-ink-muted">{course.provider}</p>
                </div>
                {course.url ? (
                  <a href={course.url} target="_blank" rel="noopener noreferrer">
                    <Button variant="outline" size="sm">
                      {t("careerLab.courses.openResource")}
                    </Button>
                  </a>
                ) : null}
              </div>
            ))
          )}
        </div>
      </Card>
    </>
  );
}

function RouteOptimizationPanel({
  budget,
  hours,
  maxCourses,
  onBudgetChange,
  onHoursChange,
  onMaxCoursesChange,
  onGenerate,
  disabled,
  isPending,
  isError,
  route,
}: {
  budget: number;
  hours: number;
  maxCourses: number;
  onBudgetChange: (value: number) => void;
  onHoursChange: (value: number) => void;
  onMaxCoursesChange: (value: number) => void;
  onGenerate: () => void;
  disabled: boolean;
  isPending: boolean;
  isError: boolean;
  route: RouteOptimization | null;
}) {
  const { t } = useTranslation();

  return (
    <Card className="flex flex-col gap-4">
      <CardHeader title={t("careerLab.route.title")} />

      <form
        className="grid gap-3 sm:grid-cols-[1fr_1fr_1fr_auto] sm:items-end"
        onSubmit={(event) => {
          event.preventDefault();
          onGenerate();
        }}
      >
        <FormField label={t("careerLab.route.budgetLabel")}>
          <Input
            type="number"
            min={0}
            value={budget}
            onChange={(event) => onBudgetChange(Number(event.target.value))}
          />
        </FormField>
        <FormField label={t("careerLab.route.hoursLabel")}>
          <Input
            type="number"
            min={0}
            value={hours}
            onChange={(event) => onHoursChange(Number(event.target.value))}
          />
        </FormField>
        <FormField label={t("careerLab.route.maxCoursesLabel")}>
          <Input
            type="number"
            min={1}
            max={20}
            value={maxCourses}
            onChange={(event) => onMaxCoursesChange(Number(event.target.value))}
          />
        </FormField>
        <Button type="submit" disabled={disabled} loading={isPending}>
          {isPending ? t("careerLab.route.generating") : t("careerLab.route.generateButton")}
        </Button>
      </form>

      {isError ? <Alert tone="danger">{t("careerLab.route.error")}</Alert> : null}

      {route ? (
        <div className="flex flex-col gap-4 border-t border-border pt-4">
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {(
              [
                [t("careerLab.route.before"), formatPercent(route.match_score_before)],
                [t("careerLab.route.after"), formatPercent(route.projected_match_score_after)],
                [t("careerLab.route.cost"), formatMoney(route.total_cost)],
                [t("careerLab.route.hours"), formatHoursValue(route.total_hours)],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="rounded-md bg-surface-subtle px-3 py-2">
                <dt className="text-overline text-ink-muted uppercase">{label}</dt>
                <dd className="text-card-title text-ink tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>

          <p className="text-body-sm text-ink-soft">{route.route_summary}</p>

          {route.selected_courses.length === 0 ? (
            <p className="py-3 text-center text-body-sm text-ink-muted">{t("careerLab.route.empty")}</p>
          ) : (
            <ol className="flex flex-col gap-2">
              {[...route.selected_courses]
                .sort((a, b) => (a.sequence_order ?? 0) - (b.sequence_order ?? 0))
                .map((course, index) => (
                  <li key={course.course_id} className="flex gap-3 rounded-md border border-border p-3">
                    <span
                      aria-hidden="true"
                      className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary-subtle text-caption font-semibold text-primary tabular-nums"
                    >
                      {course.sequence_order ?? index + 1}
                    </span>
                    <div className="min-w-0">
                      <span className="sr-only">
                        {t("careerLab.route.step", { order: course.sequence_order ?? index + 1 })}
                      </span>
                      <p className="text-body-sm font-medium text-ink">{course.title}</p>
                      <p className="mt-0.5 text-caption text-ink-soft">{course.selection_reason}</p>
                    </div>
                  </li>
                ))}
            </ol>
          )}
        </div>
      ) : null}
    </Card>
  );
}

function BaselineComparisonPanel({ baseline, isPending }: { baseline: BaselineEvaluation | null; isPending: boolean }) {
  const { t } = useTranslation();

  return (
    <Card className="flex flex-col gap-4">
      <CardHeader title={t("careerLab.baseline.title")} />
      {isPending ? (
        <Spinner label={t("async.loading")} />
      ) : !baseline ? (
        <p className="py-3 text-center text-body-sm text-ink-muted">{t("careerLab.baseline.empty")}</p>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="rounded-md bg-primary-subtle px-3 py-2.5">
            <p className="text-label text-primary">
              {t("careerLab.baseline.winner")}: {methodLabel(baseline.winner_summary.best_method ?? "", t)}
            </p>
            <p className="mt-0.5 text-caption text-ink-soft">{baseline.winner_summary.summary}</p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {baseline.methods.map((method) => (
              <div key={method.method} className="rounded-md border border-border p-3">
                <p className="text-body-sm font-medium text-ink">{methodLabel(method.method, t)}</p>
                <div className="mt-2 flex flex-col gap-0.5 text-caption text-ink-soft tabular-nums">
                  <span>
                    {t("careerLab.baseline.coverage")}: {formatPercent(method.metrics.weighted_skill_coverage)}
                  </span>
                  <span>
                    {t("careerLab.baseline.critical")}: {formatPercent(method.metrics.critical_skill_coverage)}
                  </span>
                  <span>
                    {t("careerLab.baseline.cost")}: {formatMoney(method.metrics.total_cost)}
                  </span>
                  <span>
                    {t("careerLab.baseline.hours")}: {formatHoursValue(method.metrics.total_hours)}
                  </span>
                  <span>
                    {t("careerLab.baseline.courses")}: {method.metrics.selected_courses_count}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function RouteHistoryPanel({ runs }: { runs: RouteRun[] }) {
  const { t } = useTranslation();

  return (
    <Card className="flex flex-col gap-4">
      <CardHeader title={t("careerLab.history.title")} />
      <div className="flex flex-col gap-2">
        {runs.length === 0 ? (
          <p className="py-3 text-center text-body-sm text-ink-muted">{t("careerLab.history.empty")}</p>
        ) : (
          runs.map((run) => (
            <div
              key={run.optimization_run_id}
              className="flex items-center justify-between gap-3 rounded-md bg-surface-subtle px-3 py-2"
            >
              <span className="min-w-0 truncate text-body-sm text-ink">{run.target_role}</span>
              <span className="shrink-0 text-body-sm text-ink-soft tabular-nums">
                {formatPercent(run.match_score_before)} → {formatPercent(run.projected_match_score_after)}
              </span>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
