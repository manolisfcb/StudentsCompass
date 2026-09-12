import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";

export interface NavItem {
  to: string;
  label: string;
}

/**
 * The frame every shell shares: skip link, header, nav, main, footer.
 *
 * The four shells differ in their nav and their chrome, not in their
 * structure, so the structure lives here once. `<main id="main">` and the skip
 * link exist because keyboard navigation through a repeated nav on every page
 * is otherwise the only way in.
 *
 * `variant="marketing"` is the public shell's header (TASK-046): the brand
 * gradient and pill nav that `.marketing-header`/`.marketing-nav` render in
 * the legacy templates. It only changes this header's classes — student,
 * company and admin shells keep passing no variant and render exactly as
 * before.
 */
export function AppShell({
  title,
  titleHref,
  nav,
  actions,
  children,
  skipLabel,
  logoSrc,
  variant = "default",
}: {
  title: string;
  /** When set, the brand in the header links here (the public shell's "/"). */
  titleHref?: string;
  nav?: readonly NavItem[];
  actions?: ReactNode;
  children: ReactNode;
  skipLabel: string;
  /** Brand mark shown next to the title, matching `.brand-logo--nav`. */
  logoSrc?: string;
  variant?: "default" | "marketing";
}) {
  const isMarketing = variant === "marketing";
  const brand = (
    <span className={`flex items-center gap-2 text-lg font-semibold ${isMarketing ? "text-white" : "text-brand"}`}>
      {logoSrc ? <img src={logoSrc} alt="" className="h-8 w-auto" /> : null}
      {title}
    </span>
  );

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-surface focus:px-4 focus:py-2"
      >
        {skipLabel}
      </a>

      <header className={isMarketing ? "hero-gradient px-3 pb-3 pt-3 sm:px-4" : "border-b border-border bg-surface"}>
        <div
          className={
            isMarketing
              ? "mx-auto flex max-w-6xl flex-wrap items-center gap-4 rounded-[28px] border border-white/20 bg-ink/10 px-4 py-3 shadow-[0_24px_60px_rgba(15,23,42,0.16)] backdrop-blur-md sm:px-5"
              : "mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-4"
          }
        >
          {titleHref ? (
            <Link to={titleHref}>{brand}</Link>
          ) : (
            brand
          )}
          {nav && nav.length > 0 ? (
            <nav aria-label={title} className="flex flex-wrap gap-1">
              {nav.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    isMarketing
                      ? `rounded-full px-4 py-2 text-sm font-bold text-white transition ${
                          isActive ? "border border-white/30 bg-white/15" : "border border-transparent hover:border-white/25 hover:bg-white/15"
                        }`
                      : `rounded-md px-3 py-1.5 text-sm ${
                          isActive ? "bg-brand/10 font-medium text-brand" : "text-ink-soft hover:bg-canvas"
                        }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          ) : null}
          {actions ? <div className="ml-auto flex items-center gap-2">{actions}</div> : null}
        </div>
      </header>

      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        {children}
      </main>

      <footer className="border-t border-border bg-surface px-4 py-6 text-center text-xs text-ink-muted">
        {title}
      </footer>
    </div>
  );
}
