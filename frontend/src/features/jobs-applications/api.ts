/**
 * Job board, CV analysis, and applications (TASK-049, plan 08 §5.2).
 *
 * `POST /jobs/search` renamed to `POST /job-searches`; `POST /jobs/keywords/analyze`
 * to `POST /cv-analyses` (now answering `202`, a job resource, instead of `200`);
 * `GET /jobs/keywords/{id}` to `GET /cv-analyses/{id}`;
 * `POST /applications/{id}/interview-selection` to
 * `PUT /applications/{id}/selected-interview` (idempotent: reselecting the same
 * slot answers `200` with the existing state, per TASK-015's DB-level
 * one-booking-per-application constraint).
 */

import { apiRequest } from "@/api/client";
import type { RequestOf, ResponseOf } from "@/api/types";

export type JobBoardPosting = ResponseOf<"jobs_list_job_board_postings">[number];
export type JobSearchRequest = RequestOf<"jobs_search_jobs">;
export type JobSearchResults = ResponseOf<"jobs_search_jobs">;
export type CvAnalysisJob = ResponseOf<"jobs_start_cv_analysis">;
export type CvAnalysisStatus = ResponseOf<"jobs_get_job_status">;
export type Application = ResponseOf<"dashboard_create_application">;
export type ApplicationPage = ResponseOf<"dashboard_get_application_page">;
export type EligibleResume = ResponseOf<"dashboard_get_eligible_resumes_for_application">[number];

export async function fetchJobBoard(): Promise<JobBoardPosting[]> {
  const { data } = await apiRequest<JobBoardPosting[]>("/api/v1/jobs/board?limit=50");
  return data;
}

export async function searchJobs(payload: JobSearchRequest): Promise<JobSearchResults> {
  const { data } = await apiRequest<JobSearchResults>("/api/v1/job-searches", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return data;
}

/** Spends AI credit, so it always carries a fresh `Idempotency-Key` (TASK-041). */
export async function startCvAnalysis(idempotencyKey: string): Promise<CvAnalysisJob> {
  const { data } = await apiRequest<CvAnalysisJob>("/api/v1/cv-analyses", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
  });
  return data;
}

export async function fetchCvAnalysisStatus(jobId: string): Promise<CvAnalysisStatus> {
  const { data } = await apiRequest<CvAnalysisStatus>(`/api/v1/cv-analyses/${jobId}`);
  return data;
}

export async function fetchEligibleResumes(): Promise<EligibleResume[]> {
  const { data } = await apiRequest<EligibleResume[]>("/api/v1/applications/eligible-resumes");
  return data;
}

export interface CreateApplicationPayload {
  job_title: string;
  company_id: string;
  job_posting_id?: string | null;
  resume_id?: string | null;
  application_url?: string | null;
}

/** Creating an application always carries a fresh `Idempotency-Key`: a lost
 * response must not risk a second application for the same click. */
export async function createApplication(
  payload: CreateApplicationPayload,
  idempotencyKey: string,
): Promise<Application> {
  const { data } = await apiRequest<Application>("/api/v1/applications", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(payload),
  });
  return data;
}

export async function fetchApplicationsPage(before?: string | null): Promise<ApplicationPage> {
  const query = before ? `?before=${encodeURIComponent(before)}` : "";
  const { data } = await apiRequest<ApplicationPage>(`/api/v1/applications/page${query}`);
  return data;
}

export async function selectInterviewSlot(applicationId: string, slotId: string): Promise<Application> {
  const { data } = await apiRequest<Application>(`/api/v1/applications/${applicationId}/selected-interview`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slot_id: slotId }),
  });
  return data;
}
