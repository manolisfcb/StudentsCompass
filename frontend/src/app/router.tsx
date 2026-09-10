import { createBrowserRouter, Navigate } from "react-router-dom";

import { RequireActor, RequireAnonymous } from "@/app/guards";
import { AdminShell, CompanyShell, PublicShell, StudentShell } from "@/components/layout/shells";
import { LoginPage } from "@/features/auth/LoginPage";
import { RegisterPage } from "@/features/auth/RegisterPage";
import { ApplicantsPage } from "@/features/company/ApplicantsPage";
import { CompanyDashboardPage } from "@/features/company/CompanyDashboardPage";
import { JobPostingsPage } from "@/features/company/JobPostingsPage";
import { RecruitersPage } from "@/features/company/RecruitersPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { ApplicationsPage } from "@/features/jobs-applications/ApplicationsPage";
import { JobsPage } from "@/features/jobs-applications/JobsPage";
import { AboutPage } from "@/features/marketing/AboutPage";
import { HomePage } from "@/features/marketing/HomePage";
import { ProfilePage } from "@/features/profile-resumes/ProfilePage";
import { QuestionnairePage } from "@/features/questionnaire/QuestionnairePage";
import { ResourceDetailPage } from "@/features/resources-roadmaps/ResourceDetailPage";
import { ResourcesListPage } from "@/features/resources-roadmaps/ResourcesListPage";
import { RoadmapDetailPage } from "@/features/resources-roadmaps/RoadmapDetailPage";
import { RoadmapsListPage } from "@/features/resources-roadmaps/RoadmapsListPage";
import { SmokePage } from "@/features/smoke/SmokePage";

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
export const router = createBrowserRouter([
  {
    element: <PublicShell />,
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/about", element: <AboutPage /> },
      { path: "/__smoke", element: <SmokePage /> },
      {
        path: "/login",
        element: (
          <RequireAnonymous>
            <LoginPage />
          </RequireAnonymous>
        ),
      },
      {
        path: "/register",
        element: (
          <RequireAnonymous>
            <RegisterPage />
          </RequireAnonymous>
        ),
      },
    ],
  },
  {
    element: (
      <RequireActor allow={["student"]}>
        <StudentShell />
      </RequireActor>
    ),
    children: [
      { path: "/dashboard", element: <DashboardPage /> },
      { path: "/profile", element: <ProfilePage /> },
      { path: "/questionnaire", element: <QuestionnairePage /> },
      { path: "/resources", element: <ResourcesListPage /> },
      { path: "/resources/:resourceId", element: <ResourceDetailPage /> },
      { path: "/roadmaps", element: <RoadmapsListPage /> },
      { path: "/roadmaps/:slug", element: <RoadmapDetailPage /> },
      { path: "/jobs", element: <JobsPage /> },
      { path: "/jobs/applications", element: <ApplicationsPage /> },
    ],
  },
  {
    element: (
      <RequireActor allow={["recruiter"]}>
        <CompanyShell />
      </RequireActor>
    ),
    children: [
      { path: "/company", element: <CompanyDashboardPage /> },
      { path: "/company/postings", element: <JobPostingsPage /> },
      { path: "/company/applicants", element: <ApplicantsPage /> },
      { path: "/company/recruiters", element: <RecruitersPage /> },
    ],
  },
  {
    element: (
      <RequireActor allow={["student"]}>
        <AdminShell />
      </RequireActor>
    ),
    children: [{ path: "/admin", element: <Navigate to="/__smoke" replace /> }],
  },
  { path: "*", element: <Navigate to="/__smoke" replace /> },
]);
