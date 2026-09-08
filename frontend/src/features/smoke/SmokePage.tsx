import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { apiProbe } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";

/**
 * The only screen this task ships (the real ones arrive per vertical,
 * TASK-046 onwards). Its job is to make the same-origin claim falsifiable in a
 * browser instead of by reading configuration files.
 *
 * The probes are chosen so that a *correct* system produces a known status:
 *   - `/api/v1/users/me` answers 401 to an anonymous caller. A 401 proves the
 *     request reached FastAPI. A network error or an opaque CORS failure means
 *     the proxy is not in the path.
 *   - `/healthz` and `/readyz` are proxied already but do not exist in the
 *     backend yet; TASK-045 adds them. Until then 404 is the honest expected
 *     answer, and it still proves the prefix is forwarded rather than being
 *     swallowed by the SPA's history fallback — which would return 200 HTML.
 */
interface Probe {
  path: string;
  expected: string;
}

const PROBES: readonly Probe[] = [
  { path: "/api/v1/users/me", expected: "401 (no session)" },
  { path: "/healthz", expected: "404 until TASK-045" },
  { path: "/readyz", expected: "404 until TASK-045" },
];

export function SmokePage() {
  const { t } = useTranslation();

  const probes = useQuery({
    queryKey: queryKeys.smoke.origin,
    queryFn: async () =>
      await Promise.all(
        PROBES.map(async (probe) => ({
          ...probe,
          ...(await apiProbe(probe.path)),
        })),
      ),
    retry: false,
  });

  return (
    <main className="mx-auto max-w-2xl p-8 font-sans text-ink">
      <h1 className="text-2xl font-semibold text-brand">{t("smoke.title")}</h1>
      <p className="mt-3 text-ink-soft">{t("smoke.intro")}</p>
      <p className="mt-2 text-sm text-ink-muted">
        {t("smoke.origin", { origin: window.location.origin })}
      </p>

      <table className="mt-6 w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="py-2 pr-4 font-medium">{t("smoke.probe.path")}</th>
            <th className="py-2 pr-4 font-medium">
              {t("smoke.probe.expected")}
            </th>
            <th className="py-2 font-medium">{t("smoke.probe.actual")}</th>
          </tr>
        </thead>
        <tbody>
          {PROBES.map((probe, index) => {
            const result = probes.data?.[index];
            return (
              <tr key={probe.path} className="border-b border-border">
                <td className="py-2 pr-4 font-mono">{probe.path}</td>
                <td className="py-2 pr-4 text-ink-soft">{probe.expected}</td>
                <td className="py-2">
                  {probes.isPending
                    ? t("smoke.probe.pending")
                    : result
                      ? String(result.status)
                      : t("smoke.probe.failed")}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <button
        type="button"
        className="mt-6 rounded bg-brand px-4 py-2 text-surface hover:bg-brand-strong"
        onClick={() => void probes.refetch()}
      >
        {t("smoke.rerun")}
      </button>
    </main>
  );
}
