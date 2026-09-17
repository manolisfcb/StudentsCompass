import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { Alert, Button, Card, Icon, ProgressBar } from "@/components/ui";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import {
  fetchQuestionnaire,
  submitQuestionnaire,
  type Questionnaire,
  type QuestionnaireResult,
} from "@/features/questionnaire/api";

/**
 * The career questionnaire (TASK-047), reproducing `questionnaire.html` /
 * `questionnaire.js`: one question at a time, answers held in memory until
 * the last question submits them all in one request, then the top three
 * careers with a score bar. Scoring is the backend's; this page never
 * recomputes a career score, only displays what `POST /questionnaire`
 * already decided.
 */
export function QuestionnairePage() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: queryKeys.questionnaire.current, queryFn: fetchQuestionnaire });

  return (
    <div className="flex justify-center">
      <DocumentMeta
        title={t("questionnaire.seoTitle")}
        description={t("questionnaire.seoDescription")}
        path="/questionnaire"
      />
      {/* This screen was already built on utilities rather than a sheet — but
          on a CDN Tailwind's default palette (`bg-gray-100`, `text-red-600`)
          and a `brand` token that no longer exists. Now it reads the same
          design tokens as the rest of the app. */}
      <Card padding="none" className="flex min-h-[36rem] w-full max-w-2xl flex-col overflow-hidden">
        <AsyncBoundary query={query}>
          {(questionnaire) => <QuestionnaireFlow questionnaire={questionnaire} />}
        </AsyncBoundary>
      </Card>
    </div>
  );
}

function QuestionnaireFlow({ questionnaire }: { questionnaire: Questionnaire }) {
  const { t } = useTranslation();
  const [stepIndex, setStepIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<QuestionnaireResult | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      submitQuestionnaire({
        answers: Object.entries(answers).map(([question_id, option_id]) => ({ question_id, option_id })),
      }),
    onSuccess: (data) => setResult(data),
  });

  if (result) return <QuestionnaireResults result={result} onRetake={() => { setResult(null); setAnswers({}); setStepIndex(0); }} />;

  const question = questionnaire.questions[stepIndex];
  if (!question) return null;
  const isLast = stepIndex === questionnaire.questions.length - 1;
  const selected = answers[question.id] ?? null;

  return (
    <>
      <div className="h-1 w-full bg-surface-hover">
        <div
          className="h-1 bg-primary transition-[width] duration-500 ease-out"
          style={{ width: `${((stepIndex + 1) / questionnaire.questions.length) * 100}%` }}
        />
      </div>

      <div className="flex items-end justify-between px-6 pt-5">
        <span className="text-overline text-primary uppercase">
          {t("questionnaire.stepOf", { current: stepIndex + 1, total: questionnaire.questions.length })}
        </span>
        <span className="text-caption text-ink-muted tabular-nums">
          {Math.round(((stepIndex + 1) / questionnaire.questions.length) * 100)}%
        </span>
      </div>

      <div className="flex flex-1 flex-col p-6">
        <div className="mb-5">
          <h2 className="text-section-title text-ink">{question.title}</h2>
          {question.subtitle ? <p className="mt-1 text-body-sm text-ink-soft">{question.subtitle}</p> : null}
        </div>

        <div role="radiogroup" aria-label={question.title} className="flex-1 space-y-2 overflow-y-auto pb-4 pr-1">
        {question.options.map((option) => (
          <button
            key={option.id}
            type="button"
            role="radio"
            aria-checked={selected === option.id}
            onClick={() => setAnswers((prev) => ({ ...prev, [question.id]: option.id }))}
            className={`block w-full rounded-md border px-4 py-3 text-left text-body-sm transition-colors ${
              selected === option.id
                ? "border-primary bg-primary-subtle font-medium text-primary"
                : "border-border-strong bg-surface text-ink hover:bg-surface-hover"
            }`}
          >
            {option.label}
          </button>
          ))}
        </div>

        {mutation.isError ? (
          <Alert tone="danger" className="mt-4">
            {mutation.error instanceof ApiError && mutation.error.detail
              ? mutation.error.detail.message
              : t("questionnaire.error.submit")}
          </Alert>
        ) : null}

        <div className="mt-auto flex items-center justify-between gap-3 border-t border-border pt-5">
          {/* Hidden rather than faded out on the first step: a control at zero
            * opacity is still focusable and still announced. */}
          {stepIndex === 0 ? (
            <span />
          ) : (
            <Button variant="ghost" onClick={() => setStepIndex((i) => i - 1)}>
              {t("questionnaire.previous")}
            </Button>
          )}

          {isLast ? (
            <Button size="lg" disabled={!selected} loading={mutation.isPending} onClick={() => mutation.mutate()}>
              {mutation.isPending ? t("questionnaire.submitting") : t("questionnaire.submit")}
            </Button>
          ) : (
            <Button size="lg" disabled={!selected} onClick={() => setStepIndex((i) => i + 1)}>
              {t("questionnaire.next")}
            </Button>
          )}
        </div>
      </div>
    </>
  );
}

function QuestionnaireResults({
  result,
  onRetake,
}: {
  result: QuestionnaireResult;
  onRetake: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-1 flex-col items-center justify-center p-8 text-center">
      <div
        aria-hidden="true"
        className="mb-5 flex size-16 items-center justify-center rounded-full bg-success-subtle text-success"
      >
        <Icon name="check-circle" size={32} variant="Bold" />
      </div>
      <h2 className="text-page-title text-ink">{t("questionnaire.results.title")}</h2>
      <p className="mx-auto mt-2 mb-8 max-w-md text-body text-ink-soft">{t("questionnaire.results.subtitle")}</p>

      <div className="w-full max-w-md space-y-3 text-left">
        {result.top_careers.map((career) => (
          <ProgressBar
            key={career.career}
            label={career.career}
            value={Math.min(100, career.score * 10)}
            showValue={false}
          />
        ))}
      </div>

      <div className="mt-10 flex w-full flex-wrap justify-center gap-3">
        <Button onClick={onRetake}>{t("questionnaire.results.retake")}</Button>
        <Link to="/dashboard">
          <Button variant="outline">{t("questionnaire.results.goToDashboard")}</Button>
        </Link>
      </div>
    </div>
  );
}
