import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
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
    <div className="mx-auto max-w-2xl">
      <DocumentMeta
        title={t("questionnaire.seoTitle")}
        description={t("questionnaire.seoDescription")}
        path="/questionnaire"
      />
      <AsyncBoundary query={query}>{(questionnaire) => <QuestionnaireFlow questionnaire={questionnaire} />}</AsyncBoundary>
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
    <div className="space-y-6">
      <div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-border">
          <div
            className="h-full bg-brand transition-all"
            style={{ width: `${((stepIndex + 1) / questionnaire.questions.length) * 100}%` }}
          />
        </div>
        <p className="mt-2 text-sm text-ink-muted">
          {t("questionnaire.stepOf", { current: stepIndex + 1, total: questionnaire.questions.length })}
        </p>
      </div>

      <div>
        <h1 className="text-xl font-semibold text-ink">{question.title}</h1>
        {question.subtitle ? <p className="mt-1 text-sm text-ink-soft">{question.subtitle}</p> : null}
      </div>

      <div role="radiogroup" aria-label={question.title} className="space-y-2">
        {question.options.map((option) => (
          <button
            key={option.id}
            type="button"
            role="radio"
            aria-checked={selected === option.id}
            onClick={() => setAnswers((prev) => ({ ...prev, [question.id]: option.id }))}
            className={`block w-full rounded-md border px-4 py-3 text-left text-sm transition-colors ${
              selected === option.id
                ? "border-brand bg-brand/10 font-medium text-brand"
                : "border-border bg-surface text-ink hover:bg-canvas"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {mutation.isError ? (
        <Alert tone="danger">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("questionnaire.error.submit")}
        </Alert>
      ) : null}

      <div className="flex justify-between">
        <Button variant="secondary" disabled={stepIndex === 0} onClick={() => setStepIndex((i) => i - 1)}>
          {t("questionnaire.previous")}
        </Button>
        {isLast ? (
          <Button disabled={!selected || mutation.isPending} onClick={() => mutation.mutate()}>
            {mutation.isPending ? t("questionnaire.submitting") : t("questionnaire.submit")}
          </Button>
        ) : (
          <Button disabled={!selected} onClick={() => setStepIndex((i) => i + 1)}>
            {t("questionnaire.next")}
          </Button>
        )}
      </div>
    </div>
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
    <div className="space-y-6 text-center">
      <h1 className="text-2xl font-bold text-ink">{t("questionnaire.results.title")}</h1>
      <div className="space-y-4 text-left">
        {result.top_careers.map((career) => (
          <div key={career.career}>
            <div className="flex justify-between text-sm font-medium text-ink">
              <span>{career.career}</span>
              <span>{career.score}</span>
            </div>
            <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-border">
              <div
                className="h-full bg-brand"
                style={{ width: `${Math.min(100, career.score * 10)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="flex justify-center gap-4">
        <Button variant="secondary" onClick={onRetake}>
          {t("questionnaire.results.retake")}
        </Button>
        <Link
          to="/dashboard"
          className="inline-flex items-center justify-center rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-strong"
        >
          {t("questionnaire.results.goToDashboard")}
        </Link>
      </div>
    </div>
  );
}
