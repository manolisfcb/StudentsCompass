/**
 * Career Optimization Lab (TASK-052, plan 08 §5.2).
 *
 * No backend rename here: `career_lab.js` already spoke the `/capstone/*`
 * contract this screen uses. The one behavioural addition is `Idempotency-Key`
 * on `optimize` and `evaluate-baselines` — both spend bounded CP-SAT solver
 * capacity (`app/core/offload.py`), the same reason `/cv-analyses` and
 * `/applications` carry the header.
 *
 * Trimmed from the legacy page: no CV upload here (`/profile` already owns
 * that, TASK-047's `ResumeAuditWidget`), no radar chart, and the two
 * admin-facing diagnostics panels (catalog quality, embedding status) are
 * left out as out of scope for the student-facing workflow.
 */

import { apiRequest } from "@/api/client";
import type { RequestOf, ResponseOf } from "@/api/types";

export type TargetRole = ResponseOf<"capstone_get_capstone_analytics_roles">["roles"][number];
export type SkillReview = ResponseOf<"capstone_list_resume_skills_for_review">;
export type ReviewedSkill = SkillReview["skills"][number];
export type GapAnalysis = ResponseOf<"capstone_get_capstone_gap_analysis">;
export type LearningRouteOptimizeRequest = RequestOf<"capstone_optimize_capstone_learning_route">;
export type RouteOptimization = ResponseOf<"capstone_optimize_capstone_learning_route">;
export type BaselineEvaluation = ResponseOf<"capstone_evaluate_capstone_learning_route_baselines">;
export type RouteRun = ResponseOf<"capstone_list_capstone_learning_route_runs">["runs"][number];

export async function fetchTargetRoles(): Promise<TargetRole[]> {
  const { data } = await apiRequest<ResponseOf<"capstone_get_capstone_analytics_roles">>(
    "/api/v1/capstone/analytics/roles",
  );
  return data.roles;
}

export async function fetchResumeSkillReview(resumeId: string): Promise<SkillReview> {
  const { data } = await apiRequest<SkillReview>(`/api/v1/capstone/resumes/${resumeId}/skills`);
  return data;
}

export async function syncResumeSkills(resumeId: string): Promise<void> {
  await apiRequest(`/api/v1/capstone/resumes/${resumeId}/skills/sync`, { method: "POST" });
}

export async function updateResumeSkillStatus(
  resumeId: string,
  resumeSkillId: string,
  status: "confirmed" | "rejected",
): Promise<SkillReview> {
  const { data } = await apiRequest<SkillReview>(
    `/api/v1/capstone/resumes/${resumeId}/skills/${resumeSkillId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    },
  );
  return data;
}

export async function addManualResumeSkill(resumeId: string, normalizedName: string): Promise<SkillReview> {
  const { data } = await apiRequest<SkillReview>(`/api/v1/capstone/resumes/${resumeId}/skills/manual`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      normalized_name: normalizedName,
      source_section: "student_review",
      evidence_text: "Added from Career Lab review.",
    }),
  });
  return data;
}

export async function deleteResumeSkill(resumeId: string, resumeSkillId: string): Promise<SkillReview> {
  const { data } = await apiRequest<SkillReview>(
    `/api/v1/capstone/resumes/${resumeId}/skills/${resumeSkillId}`,
    { method: "DELETE" },
  );
  return data;
}

export async function fetchGapAnalysis(resumeId: string, targetRole: string): Promise<GapAnalysis> {
  const params = new URLSearchParams({ resume_id: resumeId, target_role: targetRole });
  const { data } = await apiRequest<GapAnalysis>(`/api/v1/capstone/gap-analysis?${params.toString()}`);
  return data;
}

/** Spends bounded solver capacity, so it always carries a fresh `Idempotency-Key`. */
export async function optimizeLearningRoute(
  payload: LearningRouteOptimizeRequest,
  idempotencyKey: string,
): Promise<RouteOptimization> {
  const { data } = await apiRequest<RouteOptimization>("/api/v1/capstone/learning-route/optimize", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(payload),
  });
  return data;
}

/** Also spends bounded solver capacity — same reason as `optimizeLearningRoute`. */
export async function evaluateLearningRouteBaselines(
  payload: LearningRouteOptimizeRequest,
  idempotencyKey: string,
): Promise<BaselineEvaluation> {
  const { data } = await apiRequest<BaselineEvaluation>(
    "/api/v1/capstone/learning-route/evaluate-baselines",
    {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(payload),
    },
  );
  return data;
}

export async function fetchLearningRouteRuns(limit = 5): Promise<RouteRun[]> {
  const { data } = await apiRequest<ResponseOf<"capstone_list_capstone_learning_route_runs">>(
    `/api/v1/capstone/learning-route/runs?limit=${limit}`,
  );
  return data.runs;
}
