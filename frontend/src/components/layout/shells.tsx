import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useLocation, useMatch, useSearchParams } from "react-router-dom";

import { useSession } from "@/app/useSession";
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
  // `home.html` and `about.html` differ in two places only: the hero sits
  // inside the header on the homepage, and `<main>` carries the page's own
  // class. Everything else — nav, gradient, footer — is the same shell.
  const isHome = pathname === "/";
  const mainClass = pathname === "/about" ? "about-page" : "marketing-main";
  const nav: NavItem[] = [
    { to: "/#for-students", label: t("layout.nav.forStudents") },
    { to: "/#for-companies", label: t("layout.nav.forCompanies") },
    { to: "/#how-it-works", label: t("layout.nav.howItWorks") },
    { to: "/about", label: t("layout.nav.about") },
  ];
  return (
    <div className="marketing-page">
      <AppShell
        variant="marketing"
        brandHref="/"
        nav={nav}
        actions={
          <>
            <li>
              <Link to="/login" className="marketing-nav-login">
                {t("layout.nav.login")}
              </Link>
            </li>
            <li>
              <Link to="/register" className="marketing-nav-cta">
                {t("layout.nav.getStarted")}
              </Link>
            </li>
          </>
        }
        headerExtra={isHome ? <HomeHero /> : null}
      >
        <main id="main" className={mainClass}>
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
      <div className="dashboard-layout">
        {withSidebar ? <StudentSidebar /> : null}
        <main id="main" className="dashboard">
          <Outlet />
        </main>
      </div>
    </AppShell>
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
      <main id="main">
        <Outlet />
      </main>
    </AppShell>
  );
}

/**
 * `admin.html`, which is the one screen that opts out of the site shell
 * (`include_app_shell = false`) and brings its own dark chrome. The scope class
 * carries both admin sheets because `admin_page.css` was an `@import` on top of
 * `admin.css`.
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

  return (
    <div className="pg-admin pg-admin-page admin-body">
      <a href="#main" className="skip-link">
        {t("layout.skipToContent")}
      </a>

      <div
        className={`admin-sidebar-overlay${sidebarOpen ? " active" : ""}`}
        onClick={() => setSidebarOpen(false)}
        aria-hidden="true"
      />

      <div className="admin-layout">
        <aside className={`admin-sidebar${sidebarOpen ? " active" : ""}`} id="sidebar">
          <div className="admin-sidebar-brand">
            <div className="brand-icon" aria-hidden="true">
              🧭
            </div>
            <div className="brand-text">
              <span className="brand-title">{t("app.name")}</span>
              <span className="brand-subtitle">{t("admin.shell.panel")}</span>
            </div>
          </div>

          <nav className="admin-sidebar-nav" aria-label={t("admin.shell.navigation")}>
            <div className="admin-nav-section">
              {sections.map((entry) => (
                <NavLink
                  key={entry.key}
                  to={entry.to}
                  onClick={() => setSidebarOpen(false)}
                  className={`admin-nav-item${entry.key === section ? " active" : ""}`}
                >
                  <span className="nav-icon" aria-hidden="true">
                    {entry.icon}
                  </span>
                  {entry.label}
                </NavLink>
              ))}
            </div>
          </nav>

          <div className="admin-sidebar-footer">
            <Link to="/">
              <span aria-hidden="true">🌐</span> {t("admin.backToSite")}
            </Link>
          </div>
        </aside>

        <main className="admin-main" id="main">
          <header className="admin-header">
            <div className="admin-header-left">
              <button
                type="button"
                className="admin-menu-toggle"
                aria-label={sidebarOpen ? t("admin.shell.closeMenu") : t("admin.shell.openMenu")}
                aria-expanded={sidebarOpen}
                aria-controls="sidebar"
                onClick={() => setSidebarOpen((open) => !open)}
              >
                ☰
              </button>
              <h2 className="admin-header-title">{headerTitle}</h2>
            </div>
            <div className="admin-header-right">
              <div className="admin-header-user">
                <div className="admin-header-user-info">
                  <div className="admin-header-user-name">{adminName}</div>
                  <div className="admin-header-user-role">{t("admin.shell.superAdmin")}</div>
                </div>
                <div className="admin-header-avatar">{initial}</div>
              </div>
              <LogoutButton actorKind="student" className="admin-btn admin-btn-ghost" />
            </div>
          </header>

          <Outlet />
        </main>
      </div>
    </div>
  );
}
