import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { Button } from "@/components/primitives/Button";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { EmptyState } from "@/components/patterns/EmptyState";
import { fetchQuestionnaireProfile } from "@/features/questionnaire/api";

/**
 * The top-3-careers card from `userProfile.html`. `null` (no questionnaire
 * completed yet) is a real, expected state — not an error — so it gets its
 * own `EmptyState` with a link to take it, the same way the page's original
 * "Complete the questionnaire" prompt worked.
 */
export function CareerSummary() {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: queryKeys.questionnaire.profile,
    queryFn: fetchQuestionnaireProfile,
  });

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-ink">{t("profile.careers.title")}</h2>
      <AsyncBoundary query={query}>
        {(profile) =>
          profile === null ? (
            <EmptyState
              title={t("profile.careers.empty")}
              action={
                <Link to="/questionnaire">
                  <Button>{t("profile.careers.takeQuestionnaire")}</Button>
                </Link>
              }
            />
          ) : (
            <div className="grid gap-3 sm:grid-cols-3">
              {profile.results.slice(0, 3).map((career) => (
                <div key={career.career} className="rounded-lg border border-border bg-surface p-4 text-center">
                  <strong className="block text-ink">{career.career}</strong>
                  <span className="text-sm text-ink-muted">{career.score}</span>
                </div>
              ))}
            </div>
          )
        }
      </AsyncBoundary>
    </div>
  );
}
