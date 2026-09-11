import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, Outlet } from "react-router-dom";

import { useSession } from "@/app/useSession";
import { AppShell, type NavItem } from "@/components/layout/AppShell";
import { LogoutButton } from "@/features/auth/LogoutButton";

/**
 * One shell per actor (plan 08 §7). They are layout routes: the router nests
 * the guarded screens under them, so a shell never decides who may see what —
 * `RequireActor` does the navigation part and the API does the authorization
 * part.
 *
 * The nav entries name routes the verticals of §9 will register. Listing them
 * here rather than in each vertical is what keeps one menu instead of eight.
 */

function useShellStrings() {
  const { t } = useTranslation();
  return { app: t("app.name"), skip: t("layout.skipToContent") };
}

export function PublicShell() {
  const { t } = useTranslation();
  const { app, skip } = useShellStrings();
  const nav: NavItem[] = [{ to: "/about", label: t("layout.nav.about") }];
  return (
    <AppShell
      title={app}
      titleHref="/"
      nav={nav}
      skipLabel={skip}
      actions={
        <div className="flex items-center gap-3">
          <Link to="/login" className="text-sm font-medium text-ink-soft hover:text-brand">
            {t("layout.nav.login")}
          </Link>
          <Link
            to="/register"
            className="rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-strong"
          >
            {t("layout.nav.getStarted")}
          </Link>
        </div>
      }
    >
      <Outlet />
    </AppShell>
  );
}

export function StudentShell() {
  const { t } = useTranslation();
  const { app, skip } = useShellStrings();
  const nav: NavItem[] = [
    { to: "/dashboard", label: t("layout.nav.dashboard") },
    { to: "/resources", label: t("layout.nav.resources") },
    { to: "/roadmaps", label: t("layout.nav.roadmaps") },
    { to: "/jobs", label: t("layout.nav.jobs") },
    { to: "/career-lab", label: t("layout.nav.careerLab") },
    { to: "/community", label: t("layout.nav.community") },
    { to: "/messages", label: t("layout.nav.messages") },
    { to: "/profile", label: t("layout.nav.profile") },
  ];
  return (
    <AppShell title={app} nav={nav} skipLabel={skip} actions={<LogoutButton actorKind="student" />}>
      <Outlet />
    </AppShell>
  );
}

export function CompanyShell() {
  const { t } = useTranslation();
  const { app, skip } = useShellStrings();
  const nav: NavItem[] = [
    { to: "/company", label: t("layout.nav.companyDashboard") },
    { to: "/company/postings", label: t("layout.nav.postings") },
    { to: "/company/applicants", label: t("layout.nav.applicants") },
    { to: "/company/recruiters", label: t("layout.nav.recruiters") },
  ];
  return (
    <AppShell title={app} nav={nav} skipLabel={skip} actions={<LogoutButton actorKind="company" />}>
      <Outlet />
    </AppShell>
  );
}

export function AdminShell() {
  const { t } = useTranslation();
  const session = useSession();
  const [menuOpen, setMenuOpen] = useState(false);
  const actor = session.data?.actors.find((candidate) => candidate.actor_type === "student");
  const adminName = actor?.display_name || actor?.email || t("admin.shell.admin");
  const initial = adminName.charAt(0).toUpperCase();
  const nav = [
    { to: "/admin", icon: "📊", label: t("admin.section.dashboard") },
    { to: "/admin?section=users", icon: "👥", label: t("admin.section.users") },
    { to: "/admin?section=resources", icon: "📚", label: t("admin.section.resources") },
  ];
  return (
    <div className="admin-console min-h-screen bg-ink text-white">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-white focus:p-3 focus:text-ink">
        {t("layout.skipToContent")}
      </a>
      <aside id="admin-navigation" className={`fixed inset-y-0 left-0 z-40 w-64 border-r border-white/10 bg-ink p-5 transition-transform lg:translate-x-0 ${menuOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <Link to="/admin" className="flex items-center gap-3" onClick={() => setMenuOpen(false)}>
          <span className="rounded-lg bg-brand p-2 text-xl" aria-hidden="true">🧭</span>
          <span>
            <strong className="block text-sm">{t("app.name")}</strong>
            <small className="block text-xs uppercase tracking-widest text-brand-soft">{t("admin.shell.panel")}</small>
          </span>
        </Link>
        <nav aria-label={t("admin.shell.navigation")} className="mt-10 space-y-2">
          {nav.map((item) => (
            <Link key={item.to} to={item.to} onClick={() => setMenuOpen(false)} className="flex items-center gap-3 rounded-lg px-3 py-3 text-sm text-ink-muted hover:bg-white/10 hover:text-white">
              <span aria-hidden="true">{item.icon}</span>{item.label}
            </Link>
          ))}
        </nav>
        <Link to="/" className="absolute bottom-6 left-5 text-sm text-ink-muted hover:text-white">🌐 {t("admin.backToSite")}</Link>
      </aside>
      {menuOpen ? <button type="button" aria-label={t("admin.shell.closeMenu")} className="fixed inset-0 z-30 bg-ink/70 lg:hidden" onClick={() => setMenuOpen(false)} /> : null}
      <div className="lg:pl-64">
        <header className="flex min-h-16 items-center border-b border-white/10 px-4 sm:px-8">
          <button
            type="button"
            className="mr-4 rounded p-2 text-xl lg:hidden"
            aria-label={menuOpen ? t("admin.shell.closeMenu") : t("admin.shell.openMenu")}
            aria-expanded={menuOpen}
            aria-controls="admin-navigation"
            onClick={() => setMenuOpen((open) => !open)}
          >
            ☰
          </button>
          <div className="ml-auto flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <strong className="block text-sm">{adminName}</strong>
              <span className="block text-xs text-brand-soft">{t("admin.shell.superAdmin")}</span>
            </div>
            <span className="flex size-9 items-center justify-center rounded-full bg-brand text-sm font-bold">{initial}</span>
            <LogoutButton actorKind="student" className="text-white hover:bg-white/10" />
          </div>
        </header>
        <main id="main" className="min-h-[calc(100vh-4rem)] px-4 py-6 sm:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
