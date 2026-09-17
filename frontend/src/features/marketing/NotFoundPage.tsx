import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router-dom";

import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { Button } from "@/components/ui";

/**
 * The catch-all screen (TASK-058 pre-flight, runbook §4 B1).
 *
 * What this replaces: the route table used to send every unmatched URL to
 * `/__smoke`, the proxy-diagnostics page TASK-046 shipped to make the
 * same-origin claim falsifiable in a browser. That was harmless while the
 * domain still pointed at the Jinja monolith and nobody reached this bundle.
 * The cutover is what makes it reach everyone: the six legacy screens that
 * changed address, every URL indexed under the old site, and the 39% of
 * inbound requests that are scanners probing for `/wp-admin` would all have
 * landed on a developer tool showing HTTP probe results.
 *
 * On the HTTP status, and it is a real limitation rather than an oversight:
 * this page is served with **200**, not 404. Nginx answers an unknown path
 * with the entry document long before React has a route table to consult, and
 * the alternative — listing every SPA route in `nginx.conf` so the proxy can
 * 404 the rest — puts the route table in two places that drift apart silently.
 * What nginx *can* decide without knowing the routes is that a path with a
 * file extension is never a screen, and it 404s those directly; that is where
 * the scanner traffic goes. For the rest, `noindex` is what keeps a crawler
 * from reading the 200 as a page. See runbook §9.
 */
export function NotFoundPage() {
  const { t } = useTranslation();
  const { pathname } = useLocation();

  return (
    <>
      <DocumentMeta
        title={t("notFound.seoTitle")}
        description={t("notFound.seoDescription")}
        path={pathname}
        noindex
      />
      <main className="mx-auto flex min-h-[60vh] max-w-2xl flex-col items-center justify-center px-4 py-16 text-center">
        <p className="text-body-sm font-semibold uppercase tracking-wide text-primary">
          {t("notFound.kicker")}
        </p>
        <h1 className="mt-3 text-page-title text-ink">{t("notFound.title")}</h1>
        <p className="mt-4 text-ink-soft">{t("notFound.body")}</p>
        {/* The path is echoed back because the most common way to land here
            after the cutover is an old bookmark, and knowing which URL failed
            is what makes it reportable. `pathname` only — never the query
            string, which can carry tokens. */}
        <p className="mt-2 break-all font-mono text-body-sm text-ink-soft">{pathname}</p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link to="/">
            <Button>{t("notFound.goHome")}</Button>
          </Link>
          <Link to="/dashboard">
            <Button variant="secondary">{t("notFound.goDashboard")}</Button>
          </Link>
        </div>
      </main>
    </>
  );
}
