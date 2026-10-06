import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { Alert, Badge, Button, Card, CardHeader, FormField, Input } from "@/components/ui";
import { buildJobTargetRoadmap, type JobTargetRoadmap } from "@/features/career-lab/api";

type Step = JobTargetRoadmap["steps"][number];
type UncoveredGap = JobTargetRoadmap["uncovered_gaps"][number];

/** The bounds `JobTargetRoadmapRequest` enforces; the backend's 422 stays the authority. */
const MAX_DAYS = 365;
const MAX_HOURS_PER_DAY = 16;

/**
 * What to study first for this vacancy, before the interview (TASK-080).
 *
 * The student says how many days are left and how many hours a day they can
 * give; the backend turns that into the optimiser's hours limit and answers
 * with a day plan over this vacancy's gaps. Nothing is stored, so the plan is
 * asked for again on each visit — it depends on the days left anyway.
 */
export function JobTargetRoadmapPanel({ targetId }: { targetId: string }) {
  const { t } = useTranslation();
  const [days, setDays] = useState("14");
  const [hoursPerDay, setHoursPerDay] = useState("2");
  const [budget, setBudget] = useState("");
  const [submitted, setSubmitted] = useState(false);
  // One key per set of inputs, as in the vacancy form: a retry replays the
  // stored answer instead of solving again; changing an input is a new ask.
  const idempotencyKey = useRef<string | null>(null);

  const daysValue = Number(days);
  const hoursValue = Number(hoursPerDay);
  const budgetValue = budget.trim() === "" ? null : Number(budget);
  const daysInvalid = !Number.isInteger(daysValue) || daysValue < 1 || daysValue > MAX_DAYS;
  const hoursInvalid = !Number.isFinite(hoursValue) || hoursValue <= 0 || hoursValue > MAX_HOURS_PER_DAY;
  const budgetInvalid = budgetValue !== null && (!Number.isFinite(budgetValue) || budgetValue < 0);

  const mutation = useMutation({
    mutationFn: () => {
      idempotencyKey.current ??= crypto.randomUUID();
      return buildJobTargetRoadmap(
        targetId,
        { days_until_interview: daysValue, hours_per_day: hoursValue, budget: budgetValue },
        idempotencyKey.current,
      );
    },
  });

  function onInputChange(setter: (value: string) => void) {
    return (event: React.ChangeEvent<HTMLInputElement>) => {
      setter(event.target.value);
      idempotencyKey.current = null;
    };
  }

  return (
    <Card className="flex flex-col gap-4">
      <CardHeader title={t("careerLab.vacancy.roadmap.title")} />
      <p className="text-body-sm text-ink-soft">{t("careerLab.vacancy.roadmap.intro")}</p>

      <form
        className="grid gap-3 sm:grid-cols-[1fr_1fr_1fr_auto] sm:items-start"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          setSubmitted(true);
          if (daysInvalid || hoursInvalid || budgetInvalid) return;
          mutation.mutate();
        }}
      >
        <FormField
          label={t("careerLab.vacancy.roadmap.daysLabel")}
          {...(submitted && daysInvalid ? { error: t("careerLab.vacancy.roadmap.daysError", { max: MAX_DAYS }) } : {})}
        >
          <Input type="number" inputMode="numeric" min={1} max={MAX_DAYS} step={1} value={days} onChange={onInputChange(setDays)} />
        </FormField>
        <FormField
          label={t("careerLab.vacancy.roadmap.hoursLabel")}
          {...(submitted && hoursInvalid
            ? { error: t("careerLab.vacancy.roadmap.hoursError", { max: MAX_HOURS_PER_DAY }) }
            : {})}
        >
          <Input
            type="number"
            inputMode="decimal"
            min={0.5}
            max={MAX_HOURS_PER_DAY}
            step={0.5}
            value={hoursPerDay}
            onChange={onInputChange(setHoursPerDay)}
          />
        </FormField>
        <FormField
          label={t("careerLab.vacancy.roadmap.budgetLabel")}
          {...(submitted && budgetInvalid ? { error: t("careerLab.vacancy.roadmap.budgetError") } : {})}
        >
          <Input
            type="number"
            inputMode="decimal"
            min={0}
            placeholder={t("careerLab.vacancy.roadmap.budgetPlaceholder")}
            value={budget}
            onChange={onInputChange(setBudget)}
          />
        </FormField>
        {/* Label-height spacer so the button lines up with the inputs, not the labels. */}
        <div className="flex flex-col sm:pt-6">
          <Button type="submit" loading={mutation.isPending}>
            {mutation.isPending ? t("careerLab.vacancy.roadmap.building") : t("careerLab.vacancy.roadmap.submit")}
          </Button>
        </div>
      </form>

      {mutation.isError ? (
        <Alert tone="danger">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("careerLab.vacancy.roadmap.error")}
        </Alert>
      ) : null}

      {mutation.data ? <RoadmapResult roadmap={mutation.data} /> : null}
    </Card>
  );
}

function formatHours(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function RoadmapResult({ roadmap }: { roadmap: JobTargetRoadmap }) {
  const { t } = useTranslation();
  const noCourse = roadmap.uncovered_gaps.filter((gap) => gap.reason === "no_course");
  const outOfReach = roadmap.uncovered_gaps.filter((gap) => gap.reason === "out_of_reach");
  const { available_hours: availableHours, days_until_interview: daysLeft } = roadmap.constraints;

  return (
    <div className="flex flex-col gap-4 border-t border-border pt-4">
      {roadmap.gap_coverage === null ? (
        <p className="text-body-sm text-ink-soft">{t("careerLab.vacancy.roadmap.noGaps")}</p>
      ) : (
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {(
            [
              [t("careerLab.vacancy.roadmap.coverage"), `${Math.round(roadmap.gap_coverage * 100)}%`],
              [
                t("careerLab.vacancy.roadmap.hoursUsed"),
                t("careerLab.vacancy.roadmap.hoursOf", {
                  used: formatHours(roadmap.total_hours),
                  available: formatHours(availableHours),
                }),
              ],
              [
                t("careerLab.vacancy.roadmap.cost"),
                roadmap.total_cost > 0 ? `$${roadmap.total_cost.toFixed(0)}` : t("careerLab.vacancy.roadmap.free"),
              ],
            ] as const
          ).map(([label, value]) => (
            <div key={label} className="rounded-md bg-surface-subtle px-3 py-2">
              <dt className="text-overline text-ink-muted uppercase">{label}</dt>
              <dd className="text-card-title text-ink tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
      )}

      {roadmap.steps.length > 0 ? (
        <ol className="flex flex-col gap-2">
          {roadmap.steps.map((step) => (
            <RoadmapStep key={step.course_id} step={step} />
          ))}
          <li className="flex items-center gap-3 rounded-md bg-primary-subtle px-3 py-2 text-body-sm text-primary">
            <Badge tone="brand" size="sm">
              {t("careerLab.vacancy.roadmap.day", { day: daysLeft })}
            </Badge>
            {t("careerLab.vacancy.roadmap.interview")}
          </li>
        </ol>
      ) : outOfReach.length > 0 ? (
        // Only when time or budget is what kept them out: for gaps no course
        // teaches, more days would change nothing, and the group below says so.
        <Alert tone="warning">{t("careerLab.vacancy.roadmap.nothingFits")}</Alert>
      ) : null}

      {outOfReach.length > 0 ? (
        <UncoveredGroup
          title={t("careerLab.vacancy.roadmap.outOfReach.title")}
          hint={t("careerLab.vacancy.roadmap.outOfReach.hint")}
          gaps={outOfReach}
        />
      ) : null}
      {noCourse.length > 0 ? (
        <UncoveredGroup
          title={t("careerLab.vacancy.roadmap.noCourse.title")}
          hint={t("careerLab.vacancy.roadmap.noCourse.hint")}
          gaps={noCourse}
        />
      ) : null}
    </div>
  );
}

function RoadmapStep({ step }: { step: Step }) {
  const { t } = useTranslation();
  const days =
    step.start_day === step.end_day
      ? t("careerLab.vacancy.roadmap.day", { day: step.start_day })
      : t("careerLab.vacancy.roadmap.days", { start: step.start_day, end: step.end_day });
  const facts = [
    step.provider,
    step.duration_hours ? t("careerLab.vacancy.roadmap.courseHours", { hours: formatHours(step.duration_hours) }) : null,
    step.cost ? `$${step.cost.toFixed(0)}` : t("careerLab.vacancy.roadmap.free"),
  ].filter(Boolean);

  return (
    <li className="flex flex-col gap-2 rounded-md border border-border p-3 sm:flex-row sm:items-start sm:gap-3">
      <Badge tone="neutral" size="sm" className="shrink-0 self-start tabular-nums">
        {days}
      </Badge>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="text-body-sm font-medium text-ink">
          <span className="sr-only">{t("careerLab.route.step", { order: step.order })}: </span>
          {step.url ? (
            <a href={step.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
              {step.title}
            </a>
          ) : (
            step.title
          )}
        </p>
        <p className="text-caption text-ink-muted">{facts.join(" · ")}</p>
        {step.skills.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {step.skills.map((skill) => (
              <Badge key={skill.skill_id} tone="info" size="sm">
                {skill.display_name}
              </Badge>
            ))}
          </div>
        ) : null}
      </div>
    </li>
  );
}

function UncoveredGroup({ title, hint, gaps }: { title: string; hint: string; gaps: UncoveredGap[] }) {
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-label text-ink">{title}</p>
      <p className="text-caption text-ink-muted">{hint}</p>
      <div className="flex flex-wrap gap-1.5">
        {gaps.map((gap) => (
          <Badge key={gap.skill_id} tone="warning" size="sm">
            {gap.display_name}
          </Badge>
        ))}
      </div>
    </div>
  );
}
