import { useTranslation } from "react-i18next";

import { Badge, type BadgeTone } from "@/components/ui";
import type { MatchBand } from "@/features/career-lab/api";

const BAND_TONES: Record<MatchBand, BadgeTone> = {
  strong_match: "success",
  match: "brand",
  weak_match: "warning",
};

const BAND_LABEL_KEYS: Record<MatchBand, string> = {
  strong_match: "careerLab.vacancy.band.strong",
  match: "careerLab.vacancy.band.match",
  weak_match: "careerLab.vacancy.band.weak",
};

/**
 * A vacancy's score, always with its band (plan 11 §4.1): with one vacancy
 * the percentage is an absolute claim rather than a ranking, so it never
 * appears on its own. No band means no component had a signal to score on,
 * and that is said rather than shown as 0%.
 */
export function MatchBadge({
  score,
  band,
  showScore = true,
}: {
  score: number | null | undefined;
  band: MatchBand | null | undefined;
  /** Off where the number already sits beside the badge in large type. */
  showScore?: boolean;
}) {
  const { t } = useTranslation();
  if (score === null || score === undefined || !band) {
    return <Badge>{t("careerLab.vacancy.band.unscored")}</Badge>;
  }
  return (
    <Badge tone={BAND_TONES[band]} className="tabular-nums">
      {showScore ? `${Math.round(score * 100)}% · ${t(BAND_LABEL_KEYS[band])}` : t(BAND_LABEL_KEYS[band])}
    </Badge>
  );
}
