import { createBrowserRouter, Navigate } from "react-router-dom";

import { RequireActor, RequireAnonymous } from "@/app/guards";
import { AdminShell, CompanyShell, PublicShell, StudentShell } from "@/components/layout/shells";
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
      { path: "/__smoke", element: <SmokePage /> },
      {
        element: <RequireAnonymous>{<Navigate to="/dashboard" replace />}</RequireAnonymous>,
        path: "/login",
      },
    ],
  },
  {
    element: (
      <RequireActor allow={["student"]}>
        <StudentShell />
      </RequireActor>
    ),
    children: [{ path: "/dashboard", element: <Navigate to="/__smoke" replace /> }],
  },
  {
    element: (
      <RequireActor allow={["recruiter"]}>
        <CompanyShell />
      </RequireActor>
    ),
    children: [{ path: "/company", element: <Navigate to="/__smoke" replace /> }],
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
