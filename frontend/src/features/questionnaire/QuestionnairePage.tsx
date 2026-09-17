import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { PageScope } from "@/components/layout/PageScope";
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
    <PageScope name="questionnaire" className="flex justify-center p-4">
      <DocumentMeta
        title={t("questionnaire.seoTitle")}
        description={t("questionnaire.seoDescription")}
        path="/questionnaire"
      />
      {/* `questionnaire.html` is the one screen the Jinja app built on utility
          classes rather than a sheet of its own (it loaded Tailwind from a CDN
          and `questionnaire.css` only tunes it responsively), so the port keeps
          the utilities — they are the original, not a rewrite of it. */}
      <div className="relative flex min-h-[600px] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white shadow-xl">
        <AsyncBoundary query={query}>
          {(questionnaire) => <QuestionnaireFlow questionnaire={questionnaire} />}
        </AsyncBoundary>
      </div>
    </PageScope>
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
      <div className="h-1.5 w-full bg-gray-100">
        <div
          className="questionnaire-progress-bar h-1.5 bg-brand transition-all duration-500 ease-out"
          style={{ width: `${((stepIndex + 1) / questionnaire.questions.length) * 100}%` }}
        />
      </div>
      <div className="flex items-end justify-between px-8 pt-6">
        <span className="text-xs font-bold uppercase tracking-wider text-brand">
          {t("questionnaire.stepOf", { current: stepIndex + 1, total: questionnaire.questions.length })}
        </span>
        <span className="text-xs text-gray-400">
          {Math.round(((stepIndex + 1) / questionnaire.questions.length) * 100)}%
        </span>
      </div>

      <div className="flex flex-1 flex-col p-8">
        <div className="fade-in mb-6">
          <h2 className="mb-2 text-2xl font-bold leading-tight text-gray-900">{question.title}</h2>
          {question.subtitle ? <p className="text-sm text-gray-500">{question.subtitle}</p> : null}
        </div>

        <div role="radiogroup" aria-label={question.title} className="fade-in flex-1 space-y-3 overflow-y-auto pb-4 pr-1">
        {question.options.map((option) => (
          <button
            key={option.id}
            type="button"
            role="radio"
            aria-checked={selected === option.id}
            onClick={() => setAnswers((prev) => ({ ...prev, [question.id]: option.id }))}
            className={`block w-full rounded-lg border px-4 py-3 text-left text-sm transition-colors ${
              selected === option.id
                ? "border-brand bg-brand/10 font-medium text-brand"
                : "border-gray-200 bg-white text-gray-800 hover:bg-gray-50"
            }`}
          >
            {option.label}
          </button>
          ))}
        </div>

        {mutation.isError ? (
          <p className="mt-4 text-sm text-red-600" role="alert">
            {mutation.error instanceof ApiError && mutation.error.detail
              ? mutation.error.detail.message
              : t("questionnaire.error.submit")}
          </p>
        ) : null}

        <div className="mt-auto flex items-center justify-between border-t border-gray-100 pt-6">
          <button
            type="button"
            className="rounded-lg px-4 py-2 font-medium text-gray-400 transition-colors hover:text-gray-600 disabled:opacity-0"
            disabled={stepIndex === 0}
            onClick={() => setStepIndex((i) => i - 1)}
          >
            {t("questionnaire.previous")}
          </button>
          {isLast ? (
            <button
              type="button"
              className="rounded-lg bg-brand px-8 py-2.5 font-medium text-white shadow-lg transition-all hover:bg-brand-strong disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none"
              disabled={!selected || mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending ? t("questionnaire.submitting") : t("questionnaire.submit")}
            </button>
          ) : (
            <button
              type="button"
              className="rounded-lg bg-brand px-8 py-2.5 font-medium text-white shadow-lg transition-all hover:bg-brand-strong disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none"
              disabled={!selected}
              onClick={() => setStepIndex((i) => i + 1)}
            >
              {t("questionnaire.next")}
            </button>
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
    <div className="fade-in flex flex-1 flex-col items-center justify-center p-10 text-center">
      <div className="mb-6 flex size-20 items-center justify-center rounded-full bg-green-100 text-3xl text-green-600 shadow-sm">
        ✓
      </div>
      <h2 className="mb-2 text-3xl font-bold text-gray-900">{t("questionnaire.results.title")}</h2>
      <p className="mx-auto mb-8 max-w-md text-gray-500">{t("questionnaire.results.subtitle")}</p>
      <div className="w-full max-w-md space-y-4 text-left">
        {result.top_careers.map((career) => (
          <div key={career.career}>
            <div className="flex justify-between text-sm font-medium text-gray-900">
              <span>{career.career}</span>
              <span>{career.score}</span>
            </div>
            <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-gray-100">
              <div className="h-full bg-brand" style={{ width: `${Math.min(100, career.score * 10)}%` }} />
            </div>
          </div>
        ))}
      </div>
      <div className="mt-10 flex w-full justify-center gap-4">
        <button
          type="button"
          className="rounded-lg bg-brand px-6 py-2.5 font-medium text-white shadow-lg transition-all hover:bg-brand-strong"
          onClick={onRetake}
        >
          {t("questionnaire.results.retake")}
        </button>
        <Link
          to="/dashboard"
          className="rounded-lg bg-gray-200 px-6 py-2.5 font-medium text-gray-800 transition-all hover:bg-gray-300"
        >
          {t("questionnaire.results.goToDashboard")}
        </Link>
      </div>
    </div>
  );
}
