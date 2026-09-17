import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useLocation, useMatch, useSearchParams } from "react-router-dom";

import { useSession } from "@/app/useSession";
import { cn } from "@/lib/cn";
import { AppShell, StudentSidebar, type NavItem } from "@/components/layout/AppShell";
import { LogoutButton } from "@/features/auth/LogoutButton";
import { HomeHero } from "@/features/marketing/HomeHero";

/**
 * One shell per actor (plan 08 §7). They are layout routes: the router nests
 * the guarded screens under them, so a shell never decides who may see what —
 * `RequireActor` does the navigation part and the API does the authorization
 * part.
 *
 * The frames are the ported ones. A student screen sits in
 * `.dashboard-layout > .dashboard-sidebar + main.dashboard`, which is what
 * `dashboard.html`, `resources.html`, `roadmap.html` and the rest all render;
 * a company screen sits in a bare `<main>` like `company-dashboard.html`. The
 * page sheets were written against those frames, so the frames come first.
 */

/**
 * The student screens that ran without the rail. The community feed, a
 * resource's detail page and the job board each want the full width for their
 * own multi-column layout, and none of the three includes `sidebar.html`
 * (`community_feed.html`, `resource_detail.html`, `jobs.html`).
 */
function useStudentSidebarVisible() {
  const { pathname } = useLocation();
  const inCommunityFeed = Boolean(useMatch("/community/:communityId"));
  const inResourceDetail = Boolean(useMatch("/resources/:resourceId"));
  const inMessages = pathname.startsWith("/messages");
  const inJobs = pathname.startsWith("/jobs");
  return !(inCommunityFeed || inResourceDetail || inMessages || inJobs);
}

export function PublicShell() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  // `home.html` and `about.html` differ in one place only: the hero sits
  // inside the header on the homepage so a single gradient covers nav and hero
  // together. Everything else — nav, footer — is the same shell.
  const isHome = pathname === "/";
  const nav: NavItem[] = [
    { to: "/#for-students", label: t("layout.nav.forStudents") },
    { to: "/#for-companies", label: t("layout.nav.forCompanies") },
    { to: "/#how-it-works", label: t("layout.nav.howItWorks") },
    { to: "/about", label: t("layout.nav.about") },
  ];
  return (
    <div className="marketing-page flex min-h-screen flex-col bg-canvas">
      <AppShell
        variant="marketing"
        brandHref="/"
        nav={nav}
        actions={
          <>
            <li>
              <Link
                to="/login"
                className="flex items-center rounded-md bg-ink/20 px-3 py-2 text-body-sm font-medium text-white transition-colors hover:bg-ink/35 md:h-9 md:py-0"
              >
                {t("layout.nav.login")}
              </Link>
            </li>
            <li>
              <Link
                to="/register"
                className="flex items-center justify-center rounded-md bg-white px-4 py-2 text-body-sm font-semibold text-primary shadow-xs transition-colors hover:bg-white/90 md:h-9 md:py-0"
              >
                {t("layout.nav.getStarted")}
              </Link>
            </li>
          </>
        }
        headerExtra={isHome ? <HomeHero /> : null}
      >
        <main id="main" className="flex-1">
          <Outlet />
        </main>
      </AppShell>
    </div>
  );
}

export function StudentShell() {
  const { t } = useTranslation();
  const withSidebar = useStudentSidebarVisible();
  const nav: NavItem[] = [
    { to: "/dashboard", label: t("layout.nav.dashboard") },
    { to: "/roadmaps", label: t("layout.nav.roadmaps") },
    { to: "/resources", label: t("layout.nav.resources") },
    { to: "/community", label: t("layout.nav.community") },
    { to: "/jobs", label: t("layout.nav.jobs") },
  ];
  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <AppShell
        variant="student"
        brandHref="/dashboard"
        nav={nav}
        actions={
          <li>
            <LogoutButton actorKind="student" />
          </li>
        }
      >
        {/* `min-w-0` on the main column is what stops a wide table or a long
          * unbroken string inside a page from widening the flex row and
          * scrolling the whole document sideways. */}
        <div className="mx-auto flex w-full max-w-content flex-1 gap-6 px-4 py-6">
          {withSidebar ? <StudentSidebar /> : null}
          <main id="main" className="min-w-0 flex-1">
            <Outlet />
          </main>
        </div>
      </AppShell>
    </div>
  );
}

export function CompanyShell() {
  const { t } = useTranslation();
  const nav: NavItem[] = [
    { to: "/company", label: t("layout.nav.companyDashboard"), end: true },
    { to: "/company/postings", label: t("layout.nav.postings") },
    { to: "/company/applicants", label: t("layout.nav.applicants") },
    { to: "/company/recruiters", label: t("layout.nav.recruiters") },
  ];
  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <AppShell
        variant="company"
        brandHref="/company"
        nav={nav}
        actions={
          <li>
            <LogoutButton actorKind="company" />
          </li>
        }
      >
        <main id="main" className="mx-auto w-full max-w-content flex-1 px-4 py-6">
          <Outlet />
        </main>
      </AppShell>
    </div>
  );
}

/**
 * The admin console.
 *
 * It keeps its dark chrome — that is the signal you are in the internal panel
 * and not in the student product — but it is no longer a second design system.
 * `theme-dark` re-points the same semantic tokens (`surface`, `ink`, `border`,
 * `primary`) to their dark values, so every `ui/` component renders correctly
 * inside it without a single dark-specific class in the markup, and the twenty
 * eight `--admin-*` variables the old sheet declared are gone.
 */
export function AdminShell() {
  const { t } = useTranslation();
  const session = useSession();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [params] = useSearchParams();
  const section = params.get("section") ?? "dashboard";

  const actor = session.data?.actors.find((candidate) => candidate.actor_type === "student");
  const adminName = actor?.display_name || actor?.email || t("admin.shell.admin");
  const initial = adminName.charAt(0).toUpperCase();

  const sections = [
    { key: "dashboard", to: "/admin", icon: "📊", label: t("admin.section.dashboard") },
    { key: "users", to: "/admin?section=users", icon: "👥", label: t("admin.section.users") },
    { key: "resources", to: "/admin?section=resources", icon: "📚", label: t("admin.section.resources") },
  ];
  const headerTitle = sections.find((entry) => entry.key === section)?.label ?? t("admin.section.dashboard");

  const navItemClass = (active: boolean) =>
    cn(
      "flex h-9 items-center gap-2.5 rounded-md px-3 text-body-sm transition-colors",
      active ? "bg-primary-subtle font-medium text-primary" : "text-ink-soft hover:bg-surface-hover hover:text-ink",
    );

  return (
    <div className="theme-dark flex min-h-screen bg-canvas text-ink">
      <a href="#main" className="skip-link">
        {t("layout.skipToContent")}
      </a>

      {/* The scrim only exists while the drawer is open, so it cannot swallow
        * clicks on the page behind it the rest of the time. */}
      {sidebarOpen ? (
        <div
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      ) : null}

      <aside
        id="sidebar"
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-sidebar flex-col border-r border-border bg-surface transition-transform duration-200",
          "lg:sticky lg:top-0 lg:h-screen lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-14 items-center gap-2.5 border-b border-border px-4">
          <span aria-hidden="true" className="text-lg">
            🧭
          </span>
          <div className="min-w-0">
            <p className="truncate text-card-title text-ink">{t("app.name")}</p>
            <p className="text-overline text-ink-muted uppercase">{t("admin.shell.panel")}</p>
          </div>
        </div>

        <nav aria-label={t("admin.shell.navigation")} className="flex flex-1 flex-col gap-0.5 p-3">
          {sections.map((entry) => (
            <NavLink
              key={entry.key}
              to={entry.to}
              onClick={() => setSidebarOpen(false)}
              className={navItemClass(entry.key === section)}
            >
              <span aria-hidden="true">{entry.icon}</span>
              {entry.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-border p-3">
          <Link to="/" className={navItemClass(false)}>
            <span aria-hidden="true">🌐</span> {t("admin.backToSite")}
          </Link>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-surface px-4">
          <button
            type="button"
            aria-label={sidebarOpen ? t("admin.shell.closeMenu") : t("admin.shell.openMenu")}
            aria-expanded={sidebarOpen}
            aria-controls="sidebar"
            onClick={() => setSidebarOpen((open) => !open)}
            className="flex size-9 items-center justify-center rounded-md text-ink-soft transition-colors hover:bg-surface-hover hover:text-ink lg:hidden"
          >
            <span aria-hidden="true">☰</span>
          </button>

          <h2 className="truncate text-section-title text-ink">{headerTitle}</h2>

          <div className="ml-auto flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="text-label text-ink">{adminName}</p>
              <p className="text-overline text-ink-muted uppercase">{t("admin.shell.superAdmin")}</p>
            </div>
            <div
              aria-hidden="true"
              className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-body-sm font-semibold text-primary-fg"
            >
              {initial}
            </div>
            <LogoutButton actorKind="student" />
          </div>
        </header>

        <main id="main" className="min-w-0 flex-1 p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
