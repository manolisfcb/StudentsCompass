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
 */
export function AppShell({
  title,
  titleHref,
  nav,
  actions,
  children,
  skipLabel,
}: {
  title: string;
  /** When set, the brand in the header links here (the public shell's "/"). */
  titleHref?: string;
  nav?: readonly NavItem[];
  actions?: ReactNode;
  children: ReactNode;
  skipLabel: string;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-surface focus:px-4 focus:py-2"
      >
        {skipLabel}
      </a>

      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-4">
          {titleHref ? (
            <Link to={titleHref} className="text-lg font-semibold text-brand">
              {title}
            </Link>
          ) : (
            <span className="text-lg font-semibold text-brand">{title}</span>
          )}
          {nav && nav.length > 0 ? (
            <nav aria-label={title} className="flex flex-wrap gap-1">
              {nav.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `rounded-md px-3 py-1.5 text-sm ${
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
