/* eslint-disable react-refresh/only-export-components --
 * This file is a route table, not a component module. It declares one lazy
 * component per screen and exports the router object, which is exactly the
 * shape the fast-refresh rule warns about — and exactly what a route table
 * is. Splitting the `lazy()` calls into a second file to satisfy the rule
 * would put the routes and the screens they point at in two places. */
import { lazy, Suspense, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { RequireActor, RequireAdmin, RequireAnonymous } from "@/app/guards";
import { AdminShell, CompanyShell, PublicShell, StudentShell } from "@/components/layout/shells";
import { LoadingState } from "@/components/ui";

/**
 * Every screen is code-split.
 *
 * The app shipped as one 688 kB bundle, which meant a visitor landing on the
 * marketing page downloaded the admin console, the recruiter pipeline and the
 * career lab's optimiser before anything rendered. Each route now arrives
 * when it is asked for, and the shells — which every route needs — stay in the
 * entry chunk so navigation between screens does not flash.
 *
 * Named exports, so each import picks the component out of its module.
 */

const AdminLoginPage = lazy(() => import("@/features/admin/AdminLoginPage").then((m) => ({ default: m.AdminLoginPage })));
const AdminPage = lazy(() => import("@/features/admin/AdminPage").then((m) => ({ default: m.AdminPage })));
const LoginPage = lazy(() => import("@/features/auth/LoginPage").then((m) => ({ default: m.LoginPage })));
const RegisterPage = lazy(() => import("@/features/auth/RegisterPage").then((m) => ({ default: m.RegisterPage })));
const CareerLabPage = lazy(() => import("@/features/career-lab/CareerLabPage").then((m) => ({ default: m.CareerLabPage })));
const ApplicantsPage = lazy(() => import("@/features/company/ApplicantsPage").then((m) => ({ default: m.ApplicantsPage })));
const CompanyDashboardPage = lazy(() => import("@/features/company/CompanyDashboardPage").then((m) => ({ default: m.CompanyDashboardPage })));
const JobPostingsPage = lazy(() => import("@/features/company/JobPostingsPage").then((m) => ({ default: m.JobPostingsPage })));
const RecruitersPage = lazy(() => import("@/features/company/RecruitersPage").then((m) => ({ default: m.RecruitersPage })));
const CommunitiesListPage = lazy(() => import("@/features/community-messages/CommunitiesListPage").then((m) => ({ default: m.CommunitiesListPage })));
const CommunityFeedPage = lazy(() => import("@/features/community-messages/CommunityFeedPage").then((m) => ({ default: m.CommunityFeedPage })));
const MessagesPage = lazy(() => import("@/features/community-messages/MessagesPage").then((m) => ({ default: m.MessagesPage })));
const DashboardPage = lazy(() => import("@/features/dashboard/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const ApplicationsPage = lazy(() => import("@/features/jobs-applications/ApplicationsPage").then((m) => ({ default: m.ApplicationsPage })));
const JobsPage = lazy(() => import("@/features/jobs-applications/JobsPage").then((m) => ({ default: m.JobsPage })));
const AboutPage = lazy(() => import("@/features/marketing/AboutPage").then((m) => ({ default: m.AboutPage })));
const HomePage = lazy(() => import("@/features/marketing/HomePage").then((m) => ({ default: m.HomePage })));
const NotFoundPage = lazy(() => import("@/features/marketing/NotFoundPage").then((m) => ({ default: m.NotFoundPage })));
const ProfilePage = lazy(() => import("@/features/profile-resumes/ProfilePage").then((m) => ({ default: m.ProfilePage })));
const QuestionnairePage = lazy(() => import("@/features/questionnaire/QuestionnairePage").then((m) => ({ default: m.QuestionnairePage })));
const ResourceDetailPage = lazy(() => import("@/features/resources-roadmaps/ResourceDetailPage").then((m) => ({ default: m.ResourceDetailPage })));
const ResourcesListPage = lazy(() => import("@/features/resources-roadmaps/ResourcesListPage").then((m) => ({ default: m.ResourcesListPage })));
const RoadmapDetailPage = lazy(() => import("@/features/resources-roadmaps/RoadmapDetailPage").then((m) => ({ default: m.RoadmapDetailPage })));
const RoadmapsListPage = lazy(() => import("@/features/resources-roadmaps/RoadmapsListPage").then((m) => ({ default: m.RoadmapsListPage })));
const SmokePage = lazy(() => import("@/features/smoke/SmokePage").then((m) => ({ default: m.SmokePage })));

/**
 * The route skeleton the eight verticals of plan 08 §9 fill in.
 *
 * Shells are layout routes and guards wrap them, so a screen added under
 * `/dashboard` is guarded by construction rather than by remembering to wrap
 * it. The verticals add children here; they do not add new shells or new
 * guards.
 *
 * There is no `admin` actor type in the session contract
 * (`backend/app/schemas/sessionSchema.py` has `student | recruiter`), so the
 * admin branch is guarded as a student and the API refuses a non-admin with a
 * 403. That is the intended division: the guard chooses navigation, the
 * backend decides authorization. TASK-053 builds the screens behind it.
 */

/**
 * The fallback shown while a route's chunk is in flight.
 *
 * It is the same skeleton `AsyncBoundary` shows while a query is loading, so
 * a chunk fetch and a slow request look identical to the person waiting —
 * neither is a blank screen. A component rather than a bare element because
 * the label is translated.
 */
function RouteFallback() {
  const { t } = useTranslation();
  return <LoadingState label={t("async.loading")} className="m-4" />;
}

/** Wraps a lazily-loaded screen in its own boundary. */
function page(element: ReactNode): ReactNode {
  return <Suspense fallback={<RouteFallback />}>{element}</Suspense>;
}

/**
 * The route table, exported apart from the router it builds.
 *
 * `createBrowserRouter` needs a real History, which a test does not have, so
 * keeping the array addressable is what lets a test mount the same routes
 * through `createMemoryRouter` and assert on what an unmatched URL actually
 * renders — rather than on this file still containing the right line.
 */
export const routes: RouteObject[] = [
  { path: "/admin/login", element: page(<AdminLoginPage />) },
  {
    element: <PublicShell />,
    children: [
      { path: "/", element: page(<HomePage />) },
      { path: "/about", element: page(<AboutPage />) },
      { path: "/__smoke", element: page(<SmokePage />) },
      // The catch-all lives here, inside the shell, so someone who lands on a
      // dead link still has the nav and the footer to leave by. Declared last
      // because a splat matches anything; every sibling above must be tried
      // first.
      //
      // It replaces `<Navigate to="/__smoke" replace />`, which sent every
      // unmatched URL to the proxy-diagnostics page. Harmless while the domain
      // still pointed at the Jinja monolith; the cutover is what would have
      // put that screen in front of real users, crawlers following retired
      // URLs, and the scanner traffic that is 39% of all inbound requests
      // (docs/refactor/10_CUTOVER_RUNBOOK.md §4, B1).
      { path: "*", element: page(<NotFoundPage />) },
    ],
  },
  // `login.html` and `register.html` set `include_app_shell` aside and render
  // a full-bleed `.auth-container` with their own brand mark: no site nav, no
  // footer. They are siblings of the public shell rather than children of it.
  {
    path: "/login",
    element: <RequireAnonymous>{page(<LoginPage />)}</RequireAnonymous>,
  },
  {
    path: "/register",
    element: <RequireAnonymous>{page(<RegisterPage />)}</RequireAnonymous>,
  },
  {
    element: (
      <RequireActor allow={["student"]}>
        <StudentShell />
      </RequireActor>
    ),
    children: [
      { path: "/dashboard", element: page(<DashboardPage />) },
      { path: "/profile", element: page(<ProfilePage />) },
      { path: "/questionnaire", element: page(<QuestionnairePage />) },
      { path: "/resources", element: page(<ResourcesListPage />) },
      { path: "/resources/:resourceId", element: page(<ResourceDetailPage />) },
      { path: "/roadmaps", element: page(<RoadmapsListPage />) },
      { path: "/roadmaps/:slug", element: page(<RoadmapDetailPage />) },
      { path: "/jobs", element: page(<JobsPage />) },
      { path: "/jobs/applications", element: page(<ApplicationsPage />) },
      { path: "/career-lab", element: page(<CareerLabPage />) },
      { path: "/community", element: page(<CommunitiesListPage />) },
      { path: "/community/:communityId", element: page(<CommunityFeedPage />) },
      { path: "/messages", element: page(<MessagesPage />) },
      { path: "/messages/:conversationId", element: page(<MessagesPage />) },
    ],
  },
  {
    element: (
      <RequireActor allow={["recruiter"]}>
        <CompanyShell />
      </RequireActor>
    ),
    children: [
      { path: "/company", element: page(<CompanyDashboardPage />) },
      { path: "/company/postings", element: page(<JobPostingsPage />) },
      { path: "/company/applicants", element: page(<ApplicantsPage />) },
      { path: "/company/recruiters", element: page(<RecruitersPage />) },
    ],
  },
  {
    element: (
      <RequireAdmin>
        <AdminShell />
      </RequireAdmin>
    ),
    children: [{ path: "/admin", element: page(<AdminPage />) }],
  },
];

export const router = createBrowserRouter(routes);
