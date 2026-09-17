import type { ReactNode } from "react";

/**
 * The wrapper a route renders so its ported stylesheet applies.
 *
 * Every legacy page sheet is emitted under a `.pg-<name>` prefix
 * (`src/styles/legacy/README.md`) because the same class name means different
 * things in two of them — `.stat-card` is a student stat tile in
 * `dashboard.css` and a company KPI in `company-dashboard.css`. The multipage
 * build kept them apart by loading one sheet per document; the SPA bundles all
 * of them, so the separation moves here.
 *
 * `name` is the legacy sheet's name, lower-cased with `_` folded to `-`, which
 * is exactly what `tools/port-legacy-css.py` writes.
 */
export type PageScopeName =
  | "about"
  | "admin"
  | "admin-page"
  | "career-lab"
  | "community"
  | "community-feed"
  | "company-dashboard"
  | "company-team"
  | "dashboard"
  | "jobs"
  | "questionnaire"
  | "resources"
  | "roadmap"
  | "roadmaps"
  | "userprofile";

export function PageScope({
  name,
  className = "",
  children,
}: {
  name: PageScopeName | readonly PageScopeName[];
  className?: string;
  children: ReactNode;
}) {
  const scopes = (Array.isArray(name) ? name : [name]) as readonly PageScopeName[];
  return <div className={[...scopes.map((s) => `pg-${s}`), className].filter(Boolean).join(" ")}>{children}</div>;
}
