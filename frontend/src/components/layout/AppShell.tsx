import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink } from "react-router-dom";

import { Icon } from "@/components/ui/Icon";
import type { IconName } from "@/components/ui/icons";
import { cn } from "@/lib/cn";

export interface NavItem {
  to: string;
  label: string;
  /** Legacy nav marked a tab active for a whole subtree (`/resources/*`). */
  end?: boolean;
}

export type ShellVariant = "student" | "company" | "marketing";

/**
 * The display logo: 316×160, 23 kB.
 *
 * The nav used to point at `Logo_Ready_to_Use.png` — 2168×1100 and 595 kB —
 * to draw a 32px-tall mark. On a phone that single image was 73% of the bytes
 * the homepage downloaded, roughly four times all of the JavaScript. The
 * original is still what `index.html` hands to `og:image`, where a large
 * image is the point; nothing on a page load fetches it any more.
 */
const LOGO = "/images/logo.png";
const LOGO_SIZE = { width: 316, height: 160 };

/**
 * The site header.
 *
 * The ported version was a floating, blur-backed, 28px-radius bar of white
 * pill buttons sitting on a three-stop gradient, held together by fourteen
 * `!important`s. This is the same header — same brand, same teal, same items —
 * as one solid bar: sticky, 56px, tokens only.
 *
 * Each actor keeps its own bar colour because that is the fastest way to know
 * which product you are in, but the structure and spacing are shared.
 */
const CHROME: Record<ShellVariant, string> = {
  student: "bg-primary text-white",
  // Slate rather than the old blue gradient: it reads as the business-facing
  // side without introducing a third brand colour.
  company: "bg-ink text-white",
  marketing: "bg-transparent text-white",
};

export function AppShell({
  variant,
  brandHref,
  nav,
  actions,
  headerExtra,
  children,
}: {
  variant: ShellVariant;
  brandHref: string;
  nav?: readonly NavItem[];
  /** The logout control, or the marketing shell's login/register pair. */
  actions?: ReactNode;
  /**
   * Content rendered inside `<header>`, below the nav — the homepage hero,
   * which shares the header's gradient so there is no seam between them.
   */
  headerExtra?: ReactNode;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const isMarketing = variant === "marketing";
  const isCompany = variant === "company";

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    cn(
      "flex items-center rounded-md px-3 py-2 text-body-sm font-medium transition-colors md:h-9 md:py-0",
      // The marketing bar sits on a gradient that runs from dark teal to pale
      // mint, so white-on-transparent disappears by the right-hand end of the
      // nav. A dark translucent chip gives every item the same backing
      // regardless of what the gradient is doing underneath it.
      isMarketing
        ? isActive
          ? "bg-ink/35 text-white"
          : "bg-ink/20 text-white hover:bg-ink/35"
        : isActive
          ? "bg-white/18 text-white"
          : "text-white/75 hover:bg-white/10 hover:text-white",
    );

  return (
    <>
      <a href="#main" className="skip-link">
        {t("layout.skipToContent")}
      </a>

      <header className={cn(isMarketing ? "relative" : "sticky top-0 z-40", CHROME[variant])}>
        <nav aria-label={t("app.name")} className={cn(!isMarketing && "border-b border-white/10")}>
          <div className="mx-auto flex h-14 max-w-content items-center gap-3 px-4">
            <Link
              to={brandHref}
              aria-label={t("app.name")}
              className="flex shrink-0 items-center gap-2.5 rounded-md py-1"
            >
              <img
                src={LOGO}
                alt={t("layout.logoAlt")}
                // Intrinsic size, so the bar does not reflow when the image
                // lands — the `h-8 w-auto` still decides how it renders.
                width={LOGO_SIZE.width}
                height={LOGO_SIZE.height}
                className="h-8 w-auto"
              />
              {isMarketing ? null : (
                <span className="hidden rounded-full border border-white/25 bg-white/10 px-2 py-0.5 text-overline text-white uppercase sm:inline-flex">
                  {isCompany ? t("layout.badge.company") : t("layout.badge.students")}
                </span>
              )}
            </Link>

            {/* The desktop nav sits right of the brand and left of the actions,
             * so a long item list eats the middle rather than pushing the
             * logout button off the bar. */}
            <ul className="ml-auto hidden items-center gap-1 md:flex">
              {nav?.map((item) => (
                <li key={item.to}>
                  <NavLink to={item.to} end={item.end ?? false} className={navLinkClass}>
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>

            <ul className="hidden items-center gap-2 md:flex">{actions}</ul>

            <button
              type="button"
              aria-label={t("layout.toggleNavigation")}
              aria-expanded={menuOpen}
              aria-controls="mobile-menu"
              onClick={() => setMenuOpen((open) => !open)}
              className="ml-auto flex size-9 items-center justify-center rounded-md text-white transition-colors hover:bg-white/10 md:hidden"
            >
              <Icon name={menuOpen ? "close" : "menu"} size={22} />
            </button>
          </div>

          {/* Rendered only when open rather than hidden with a class: an
           * off-screen panel left in the DOM stays in the tab order, which is
           * how the ported menu trapped keyboard users behind an invisible
           * list of links.
           *
           * It closes on any click inside itself — every control in here either
           * navigates or signs out — rather than from an effect keyed on the
           * route, which would call setState on each render pass. */}
          {menuOpen ? (
            <div
              id="mobile-menu"
              onClick={() => setMenuOpen(false)}
              className="border-t border-white/10 px-4 py-3 md:hidden"
            >
              <ul className="flex flex-col gap-1">
                {nav?.map((item) => (
                  <li key={item.to}>
                    <NavLink to={item.to} end={item.end ?? false} className={navLinkClass}>
                      {item.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
              <ul className="mt-3 flex flex-col gap-2 border-t border-white/10 pt-3">{actions}</ul>
            </div>
          ) : null}
        </nav>

        {headerExtra}
      </header>

      {children}

      <SiteFooter variant={variant} />
    </>
  );
}

/**
 * One footer for every shell. The ported app had two that differed only in
 * whether they listed a contact link.
 */
export function SiteFooter({ variant = "student" }: { variant?: ShellVariant }) {
  const { t } = useTranslation();
  const links = [
    { href: "#privacy", label: t("layout.footer.privacy") },
    { href: "#terms", label: t("layout.footer.terms") },
    ...(variant === "marketing" ? [] : [{ href: "#contact", label: t("layout.footer.contact") }]),
  ];

  return (
    <footer className="mt-auto border-t border-border bg-surface">
      <div className="mx-auto flex max-w-content flex-col items-center justify-between gap-3 px-4 py-5 text-caption text-ink-muted sm:flex-row">
        <p>{t("layout.footer.copyright", { year: new Date().getFullYear() })}</p>
        <ul className="flex flex-wrap items-center gap-4">
          {links.map((link) => (
            <li key={link.href}>
              <a href={link.href} className="rounded-xs transition-colors hover:text-ink">
                {link.label}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </footer>
  );
}

/** Kept for the marketing shell, which imports it by name. */
export const PublicFooter = () => <SiteFooter variant="marketing" />;

/**
 * The student rail.
 *
 * Narrower and flatter than the ported one, which was a 260px blurred gradient
 * card with a 30px radius and a 48px-blur shadow holding eight pill-shaped
 * rows. Rows are 36px here, so the whole menu is visible without the sidebar
 * competing with the page beside it.
 */
export function StudentSidebar() {
  const { t } = useTranslation();
  const items: { to: string; label: string; icon: IconName; end?: boolean }[] = [
    { to: "/dashboard", label: t("layout.nav.dashboard"), icon: "overview", end: true },
    { to: "/profile", label: t("layout.nav.profile"), icon: "user" },
    { to: "/career-lab", label: t("layout.nav.careerLab"), icon: "chart" },
    { to: "/resources", label: t("layout.nav.resources"), icon: "book" },
    { to: "/roadmaps", label: t("layout.nav.roadmaps"), icon: "route" },
    { to: "/community", label: t("layout.nav.community"), icon: "users" },
    { to: "/messages", label: t("layout.nav.messages"), icon: "messages" },
    { to: "/jobs", label: t("layout.nav.jobs"), icon: "briefcase" },
  ];

  return (
    // Hidden below `lg` rather than stacked: the same links are already in the
    // header's mobile menu, and showing both put eight rows between the top of
    // a phone screen and the page content.
    <aside className="hidden w-sidebar shrink-0 lg:block">
      <nav aria-label={t("layout.sidebar.explore")} className="sticky top-20">
        <p className="px-3 pb-2 text-overline text-ink-muted uppercase">{t("layout.sidebar.explore")}</p>
        <ul className="flex flex-col gap-0.5">
          {items.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.end ?? false}
                className={({ isActive }) =>
                  cn(
                    "flex h-9 items-center gap-2.5 rounded-md px-3 text-body-sm transition-colors",
                    isActive
                      ? "bg-primary-subtle font-medium text-primary"
                      : "text-ink-soft hover:bg-surface-hover hover:text-ink",
                  )
                }
              >
                <Icon name={item.icon} size={18} />
                <span>{item.label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
}
