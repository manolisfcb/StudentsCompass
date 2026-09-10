/**
 * Profile and resume/CV management (TASK-047, plan 08 §5.2).
 *
 * Profile reuses `/api/v1/users/me` (fastapi-users' own route) rather than the
 * legacy `/api/v1/profile`: both already serve the same `UserRead`/`UserUpdate`
 * schemas, so there was nothing to rename. Resumes and resume-course-audits
 * *were* renamed in this task — see `backend/app/routes/resumeRoute.py` for the
 * new `/resumes` / `/resume-course-audits` paths and the `legacy_router` that
 * keeps `/profile/cv/*` alive for the Jinja screen until TASK-059.
 */

import { apiRequest } from "@/api/client";
import type { RequestOf, ResponseOf } from "@/api/types";

export type Profile = ResponseOf<"users_current_user">;
export type ProfileUpdate = RequestOf<"users_patch_current_user">;
export type Resume = ResponseOf<"resume_list_resumes">[number];
export type CourseAuditAttempts = ResponseOf<"resume_get_course_audit_attempts">;
export type CourseAuditResult = ResponseOf<"resume_upload_resume_for_course_audit">;

const PROFILE_PATH = "/api/v1/users/me";
const RESUMES_PATH = "/api/v1/resumes";
const COURSE_AUDITS_PATH = "/api/v1/resume-course-audits";
const COURSE_AUDIT_ATTEMPTS_PATH = "/api/v1/resume-course-audits/attempts";

export async function fetchProfile(): Promise<Profile> {
  const { data } = await apiRequest<Profile>(PROFILE_PATH);
  return data;
}

export async function updateProfile(payload: ProfileUpdate): Promise<Profile> {
  const { data } = await apiRequest<Profile>(PROFILE_PATH, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return data;
}

export async function fetchResumes(): Promise<Resume[]> {
  const { data } = await apiRequest<Resume[]>(RESUMES_PATH);
  return data;
}

/**
 * `RequestOf` cannot describe a multipart body (it only resolves
 * `application/json` operations), so this takes a `File` directly rather than
 * a generated request type — same reasoning as the auth login form post.
 */
export async function uploadResume(file: File): Promise<ResponseOf<"resume_upload_resume">> {
  const body = new FormData();
  body.append("cv", file);
  // No Content-Type header: the browser sets `multipart/form-data` with the
  // boundary itself, and overriding it here would send a body the boundary
  // doesn't match.
  const { data } = await apiRequest<ResponseOf<"resume_upload_resume">>(RESUMES_PATH, {
    method: "POST",
    body,
  });
  return data;
}

export async function deleteResume(resumeId: string): Promise<void> {
  await apiRequest(`${RESUMES_PATH}/${resumeId}`, { method: "DELETE" });
}

export async function fetchCourseAuditAttempts(): Promise<CourseAuditAttempts> {
  const { data } = await apiRequest<CourseAuditAttempts>(COURSE_AUDIT_ATTEMPTS_PATH);
  return data;
}

/**
 * Spends AI budget, so it carries `Idempotency-Key` (TASK-041): a retry after
 * a lost response replays the first evaluation instead of spending a second
 * one. The legacy uploader (`resource_detail.js`) never sent this header —
 * closing that gap is this vertical's job, not a change to keep parity with.
 */
export async function uploadResumeForCourseAudit(
  file: File,
  idempotencyKey: string,
): Promise<CourseAuditResult> {
  const body = new FormData();
  body.append("cv", file);
  const { data } = await apiRequest<CourseAuditResult>(COURSE_AUDITS_PATH, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body,
  });
  return data;
}
