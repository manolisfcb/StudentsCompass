import { useTranslation } from "react-i18next";
import { Link, Outlet } from "react-router-dom";

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
    { to: "/community", label: t("layout.nav.community") },
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
  const { app, skip } = useShellStrings();
  const nav: NavItem[] = [{ to: "/admin", label: t("layout.nav.admin") }];
  return (
    // There is no admin actor in the session contract (guards.tsx): the admin
    // surface rides the student cookie, so it is what logout must clear too.
    <AppShell title={app} nav={nav} skipLabel={skip} actions={<LogoutButton actorKind="student" />}>
      <Outlet />
    </AppShell>
  );
}
