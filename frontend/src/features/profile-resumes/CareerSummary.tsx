import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { queryKeys } from "@/api/queryKeys";
import { Button, Card, EmptyState, SectionHeader } from "@/components/ui";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
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
    <>
      <SectionHeader title={t("profile.careers.title")} className="mb-4" />
      <AsyncBoundary query={query}>
        {(profile) =>
          profile === null ? (
            <EmptyState
              title={t("profile.careers.empty")}
              icon="🧭"
              action={
                <Link to="/questionnaire">
                  <Button>{t("profile.careers.takeQuestionnaire")}</Button>
                </Link>
              }
            />
          ) : (
            <div className="grid gap-3 sm:grid-cols-3">
              {profile.results.slice(0, 3).map((career) => (
                <Card key={career.career} className="flex items-baseline justify-between gap-2">
                  <span className="min-w-0 truncate text-card-title text-ink">{career.career}</span>
                  <span className="shrink-0 text-section-title text-primary tabular-nums">{career.score}</span>
                </Card>
              ))}
            </div>
          )
        }
      </AsyncBoundary>
    </>
  );
}
