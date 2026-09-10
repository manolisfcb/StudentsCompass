/**
 * Student dashboard (TASK-048, plan 08 §5.2). `/students_dashboard` renamed
 * to `/dashboard/student`, typed with `StudentDashboardRead` instead of the
 * `Dict` the legacy route answered with — see `backend/app/routes/dashboardRoute.py`.
 */

import { apiRequest } from "@/api/client";
import type { ResponseOf } from "@/api/types";

export type StudentDashboard = ResponseOf<"dashboard_get_students_dashboard">;

const DASHBOARD_PATH = "/api/v1/dashboard/student";

export async function fetchStudentDashboard(): Promise<StudentDashboard> {
  const { data } = await apiRequest<StudentDashboard>(DASHBOARD_PATH);
  return data;
}
