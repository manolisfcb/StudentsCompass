import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { Alert, Badge, Button, Card, CardHeader, PageHeader, ProgressBar } from "@/components/ui";
import type { BadgeTone } from "@/components/ui";
import { fetchJobTarget, type JobMatchAnalysis, type JobTarget } from "@/features/career-lab/api";
import { JobTargetRoadmapPanel } from "@/features/career-lab/JobTargetRoadmapPanel";
import { MatchBadge } from "@/features/career-lab/MatchBadge";

type ComponentName = keyof JobMatchAnalysis["components"];
type Strength = JobMatchAnalysis["strengths"][number];
type Gap = JobMatchAnalysis["gaps"][number];
type Level = NonNullable<JobMatchAnalysis["seniority"]["asked"]>;

const COMPONENT_ORDER: readonly ComponentName[] = ["skills", "context", "title", "seniority"];

// Literal keys, not template strings: the i18n check can only verify a key it
// can read, and a missing one should fail CI rather than reach a screen.
const COMPONENT_LABEL_KEYS: Record<ComponentName, string> = {
  skills: "careerLab.vacancy.breakdown.skills",
  context: "careerLab.vacancy.breakdown.context",
  title: "careerLab.vacancy.breakdown.title",
  seniority: "careerLab.vacancy.breakdown.seniority",
};

const WORKPLACE_LABEL_KEYS: Record<NonNullable<JobTarget["workplace_type"]>, string> = {
  onsite: "careerLab.vacancy.workplace.onsite",
  hybrid: "careerLab.vacancy.workplace.hybrid",
  remote: "careerLab.vacancy.workplace.remote",
};

const LEVEL_LABEL_KEYS: Record<Level, string> = {
  intern: "careerLab.vacancy.seniority.levels.intern",
  junior: "careerLab.vacancy.seniority.levels.junior",
  mid: "careerLab.vacancy.seniority.levels.mid",
  senior: "careerLab.vacancy.seniority.levels.senior",
  lead: "careerLab.vacancy.seniority.levels.lead",
};

const REQUIREMENT_LABEL_KEYS: Record<NonNullable<Strength["requirement"]>, string> = {
  required: "careerLab.vacancy.requirement.required",
  preferred: "careerLab.vacancy.requirement.preferred",
};

const MATCH_TYPE_LABEL_KEYS: Record<Strength["match_type"], string> = {
  exact: "careerLab.vacancy.strengths.exact",
  semantic: "careerLab.vacancy.strengths.semantic",
};

const GAP_KIND_LABEL_KEYS: Record<Gap["kind"], string> = {
  gap: "careerLab.vacancy.gaps.kind.gap",
  reinforce: "careerLab.vacancy.gaps.kind.reinforce",
};

/**
 * One analysed vacancy (TASK-081, plan 11 C1): does it fit, and why.
 *
 * Every number on this screen is the backend's stored analysis; nothing is
 * recomputed here (plan 08 §7), and reopening it costs nothing. The score is
 * never shown bare — band and per-component breakdown sit beside it — and a
 * component with no signal reads as "not available", not as 0.
 */
export function JobTargetDetailPage() {
  const { t } = useTranslation();
  const { targetId = "" } = useParams();
  const query = useQuery({
    queryKey: queryKeys.careerLab.jobTarget(targetId),
    queryFn: () => fetchJobTarget(targetId),
    enabled: targetId !== "",
  });

  return (
    <div className="flex flex-col gap-6">
      <DocumentMeta
        title={t("careerLab.vacancy.detail.seoTitle")}
        description={t("careerLab.vacancy.seoDescription")}
        path={`/career-lab/vacancies/${targetId}`}
      />
      <AsyncBoundary query={query}>{(target) => <JobTargetView target={target} onRefresh={() => void query.refetch()} />}</AsyncBoundary>
    </div>
  );
}

function JobTargetView({ target, onRefresh }: { target: JobTarget; onRefresh: () => void }) {
  const { t } = useTranslation();
  const analysis = target.analysis ?? null;
  const title = target.title ?? analysis?.title ?? t("careerLab.vacancy.untitled");
  const meta = [target.company, target.location].filter(Boolean).join(" · ");
  const workplace = target.workplace_type ?? analysis?.workplace_type ?? null;

  return (
    <>
      <PageHeader
        title={title}
        description={
          <span className="flex flex-wrap items-center gap-2">
            {meta ? <span>{meta}</span> : null}
            {workplace ? <Badge>{t(WORKPLACE_LABEL_KEYS[workplace])}</Badge> : null}
            <span className="text-caption text-ink-muted">
              {t("careerLab.vacancy.detail.analyzedOn", { date: new Date(target.created_at).toLocaleDateString() })}
            </span>
          </span>
        }
        breadcrumb={<Link to="/career-lab/vacancies">{t("careerLab.vacancy.detail.back")}</Link>}
        actions={
          <Link to="/career-lab/vacancies">
            <Button variant="outline">{t("careerLab.vacancy.detail.another")}</Button>
          </Link>
        }
      />

      {target.status === "failed" ? (
        <Alert tone="danger" title={t("careerLab.vacancy.detail.failedTitle")}>
          {target.error_message ?? t("careerLab.vacancy.form.error")}
        </Alert>
      ) : target.status !== "ready" || !analysis ? (
        <Alert
          tone="info"
          action={
            <Button variant="outline" size="sm" onClick={onRefresh}>
              {t("careerLab.vacancy.detail.refresh")}
            </Button>
          }
        >
          {t("careerLab.vacancy.detail.pending")}
        </Alert>
      ) : (
        <AnalysisPanels targetId={target.id} analysis={analysis} />
      )}

      <Card>
        <details>
          <summary className="cursor-pointer text-label text-ink">{t("careerLab.vacancy.detail.pastedText")}</summary>
          <p className="mt-3 max-h-96 overflow-y-auto text-body-sm whitespace-pre-wrap text-ink-soft">{target.raw_text}</p>
        </details>
      </Card>
    </>
  );
}

function AnalysisPanels({ targetId, analysis }: { targetId: string; analysis: JobMatchAnalysis }) {
  const { t } = useTranslation();
  const { requirements } = analysis;
  const gaps = [...analysis.gaps].sort((a, b) => a.priority_rank - b.priority_rank);

  return (
    <>
      <Card className="flex flex-col gap-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-overline text-ink-muted uppercase">{t("careerLab.vacancy.score.label")}</p>
            <p className="mt-1 text-page-title text-ink tabular-nums">
              {analysis.score === null ? "--" : `${Math.round(analysis.score * 100)}%`}
            </p>
          </div>
          <MatchBadge score={analysis.score} band={analysis.band} showScore={false} />
        </div>

        {analysis.score === null ? (
          <p className="text-body-sm text-ink-soft">{t("careerLab.vacancy.score.unscored")}</p>
        ) : null}

        <section aria-label={t("careerLab.vacancy.breakdown.label")} className="grid gap-4 sm:grid-cols-2">
          {COMPONENT_ORDER.map((name) => (
            <ComponentRow key={name} name={name} component={analysis.components[name]} />
          ))}
        </section>

        {analysis.gate.value < 1 ? (
          <Alert tone="warning" title={t("careerLab.vacancy.gate.title")}>
            {analysis.gate.reason}
          </Alert>
        ) : null}

        {requirements.evidence < 1 ? (
          <Alert tone="warning" title={t("careerLab.vacancy.evidence.title")}>
            {t("careerLab.vacancy.evidence.body", { count: requirements.required + requirements.preferred })}
          </Alert>
        ) : null}

        {!analysis.semantic_matching_ready ? (
          <Alert tone="info">{t("careerLab.vacancy.semanticUnavailable")}</Alert>
        ) : null}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="flex flex-col gap-3">
          <CardHeader title={t("careerLab.vacancy.requirements.title")} />
          <dl className="grid grid-cols-3 gap-3">
            {(
              [
                [t("careerLab.vacancy.requirements.required"), requirements.required],
                [t("careerLab.vacancy.requirements.covered"), requirements.required_covered],
                [t("careerLab.vacancy.requirements.preferred"), requirements.preferred],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="rounded-md bg-surface-subtle px-3 py-2">
                <dt className="text-overline text-ink-muted uppercase">{label}</dt>
                <dd className="text-card-title text-ink tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
          <SeniorityLine seniority={analysis.seniority} />
          {analysis.context.message ? <p className="text-body-sm text-ink-soft">{analysis.context.message}</p> : null}
        </Card>

        <Card className="flex flex-col gap-3">
          <CardHeader title={t("careerLab.vacancy.strengths.title")} />
          {analysis.strengths.length === 0 ? (
            <p className="py-3 text-center text-body-sm text-ink-muted">{t("careerLab.vacancy.strengths.empty")}</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {analysis.strengths.map((strength) => (
                <StrengthRow key={strength.skill_id} strength={strength} />
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card className="flex flex-col gap-3">
        <CardHeader title={t("careerLab.vacancy.gaps.title")} />
        {gaps.length === 0 ? (
          <p className="py-3 text-center text-body-sm text-ink-muted">{t("careerLab.vacancy.gaps.empty")}</p>
        ) : (
          <ol className="flex flex-col gap-2">
            {gaps.map((gap) => (
              <GapRow key={gap.skill_id} gap={gap} />
            ))}
          </ol>
        )}
      </Card>

      {gaps.length > 0 ? <JobTargetRoadmapPanel targetId={targetId} /> : null}
    </>
  );
}

function ComponentRow({ name, component }: { name: ComponentName; component: JobMatchAnalysis["components"][ComponentName] }) {
  const { t } = useTranslation();
  const label = t(COMPONENT_LABEL_KEYS[name]);
  const weight = t("careerLab.vacancy.breakdown.weight", { weight: Math.round(component.effective_weight * 100) });

  if (!component.available || component.value === null) {
    return (
      <div className="flex flex-col gap-1.5">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-body-sm text-ink-soft">{label}</span>
          <span className="text-label text-ink-muted">{t("careerLab.vacancy.breakdown.unavailable")}</span>
        </div>
        <p className="text-caption text-ink-muted">{t("careerLab.vacancy.breakdown.unavailableHint")}</p>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-1">
      <ProgressBar label={label} value={component.value * 100} />
      <p className="text-caption text-ink-muted">{weight}</p>
    </div>
  );
}

function SeniorityLine({ seniority }: { seniority: JobMatchAnalysis["seniority"] }) {
  const { t } = useTranslation();
  if (!seniority.asked && !seniority.cv && seniority.min_years === null) return null;
  const level = (value: Level | null | undefined) =>
    value ? t(LEVEL_LABEL_KEYS[value]) : t("careerLab.vacancy.seniority.notStated");
  return (
    <p className="text-body-sm text-ink-soft">
      {t("careerLab.vacancy.seniority.line", { asked: level(seniority.asked), cv: level(seniority.cv) })}
      {seniority.min_years !== null && seniority.min_years !== undefined
        ? ` ${t("careerLab.vacancy.seniority.years", { count: seniority.min_years })}`
        : ""}
    </p>
  );
}

function RequirementBadge({ requirement }: { requirement: Strength["requirement"] }) {
  const { t } = useTranslation();
  if (!requirement) return null;
  return (
    <Badge tone={requirement === "required" ? "neutral" : "info"} size="sm">
      {t(REQUIREMENT_LABEL_KEYS[requirement])}
    </Badge>
  );
}

function StrengthRow({ strength }: { strength: Strength }) {
  const { t } = useTranslation();
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-surface-subtle px-3 py-2">
      <div className="min-w-0">
        <p className="truncate text-body-sm text-ink">{strength.display_name}</p>
        {strength.match_type === "semantic" && strength.matched_with ? (
          <p className="text-caption text-ink-muted">
            {t("careerLab.vacancy.strengths.via", { skill: strength.matched_with })}
          </p>
        ) : null}
      </div>
      <div className="flex shrink-0 gap-1.5">
        <RequirementBadge requirement={strength.requirement} />
        <Badge tone="success" size="sm">
          {t(MATCH_TYPE_LABEL_KEYS[strength.match_type])}
        </Badge>
      </div>
    </li>
  );
}

const GAP_TONES: Record<Gap["kind"], BadgeTone> = { gap: "warning", reinforce: "info" };

function GapRow({ gap }: { gap: Gap }) {
  const { t } = useTranslation();
  return (
    <li className="flex gap-3 rounded-md border border-border p-3">
      <span
        aria-hidden="true"
        className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary-subtle text-caption font-semibold text-primary tabular-nums"
      >
        {gap.priority_rank}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-body-sm font-medium text-ink">
            <span className="sr-only">{t("careerLab.vacancy.gaps.priority", { rank: gap.priority_rank })} </span>
            {gap.display_name}
          </p>
          <div className="flex shrink-0 gap-1.5">
            <RequirementBadge requirement={gap.requirement} />
            <Badge tone={GAP_TONES[gap.kind]} size="sm">
              {t(GAP_KIND_LABEL_KEYS[gap.kind])}
            </Badge>
          </div>
        </div>
        {gap.kind === "reinforce" && gap.closest_skill ? (
          <p className="text-caption text-ink-muted">
            {t("careerLab.vacancy.gaps.closest", { skill: gap.closest_skill })}
          </p>
        ) : null}
        <p className="text-caption text-ink-soft">{gap.reason}</p>
      </div>
    </li>
  );
}
