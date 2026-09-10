/**
 * The recruiter/company vertical (TASK-050, plan 08 §5.2 and §6.2).
 *
 * `GET /company_dashboard` renamed to `GET /companies/me/dashboard`, now
 * typed with `CompanyDashboardRead` (was `response_model=Dict`). Everything
 * else here — job postings, applicants, recruiters — was already correctly
 * named and typed; this vertical only consumes it.
 *
 * Role ranges (who may call what) are the backend's: `current_active_company`
 * lets any active recruiter read; `current_company_job_manager_recruiter`
 * (owner/admin/recruiter, not viewer) gates postings, the applicant pipeline
 * and interview scheduling; `current_company_owner_recruiter` (owner only)
 * gates recruiter management. This file does not re-derive any of that — a
 * `viewer` who reaches a gated screen gets the same 403 a curious URL edit
 * would, and the UI only has to render whatever that response says.
 */

import { apiRequest } from "@/api/client";
import type { RequestOf, ResponseOf } from "@/api/types";

export type CompanyDashboard = ResponseOf<"dashboard_get_company_dashboard">;
export type Company = ResponseOf<"companies_get_current_company_profile">;
export type CompanyUpdate = RequestOf<"companies_update_current_company_profile">;
export type JobPosting = ResponseOf<"jobs_list_current_company_job_postings">[number];
export type JobPostingCreate = RequestOf<"jobs_create_current_company_job_posting">;
export type JobPostingUpdate = RequestOf<"jobs_update_current_company_job_posting">;
export type Applicant = ResponseOf<"companies_list_company_applicants">[number];
export type ApplicantPipelineUpdate = RequestOf<"companies_update_company_applicant_pipeline">;
export type InterviewAvailabilityPublish = RequestOf<"companies_publish_company_applicant_interview_availabilities">;
export type Recruiter = ResponseOf<"companies_list_company_recruiters">[number];
export type RecruiterCreate = RequestOf<"companies_create_company_recruiter">;
export type RecruiterUpdate = RequestOf<"companies_update_company_recruiter">;
export type CurrentRecruiter = ResponseOf<"companies_get_current_company_recruiter_profile">;

export async function fetchCompanyDashboard(): Promise<CompanyDashboard> {
  const { data } = await apiRequest<CompanyDashboard>("/api/v1/companies/me/dashboard");
  return data;
}

export async function fetchCurrentRecruiter(): Promise<CurrentRecruiter> {
  const { data } = await apiRequest<CurrentRecruiter>("/api/v1/companies/me/recruiters/current");
  return data;
}

export async function fetchJobPostings(): Promise<JobPosting[]> {
  const { data } = await apiRequest<JobPosting[]>("/api/v1/companies/me/job-postings");
  return data;
}

export async function createJobPosting(payload: JobPostingCreate): Promise<JobPosting> {
  const { data } = await apiRequest<JobPosting>("/api/v1/companies/me/job-postings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return data;
}

export async function updateJobPosting(jobPostingId: string, payload: JobPostingUpdate): Promise<JobPosting> {
  const { data } = await apiRequest<JobPosting>(`/api/v1/companies/me/job-postings/${jobPostingId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return data;
}

export async function deleteJobPosting(jobPostingId: string): Promise<void> {
  await apiRequest(`/api/v1/companies/me/job-postings/${jobPostingId}`, { method: "DELETE" });
}

export interface ApplicantFilters {
  jobPostingId?: string | null;
  statuses?: string[];
}

export async function fetchApplicants(filters: ApplicantFilters = {}): Promise<Applicant[]> {
  const params = new URLSearchParams();
  if (filters.jobPostingId) params.set("job_posting_id", filters.jobPostingId);
  for (const status of filters.statuses ?? []) params.append("status", status);
  const query = params.toString();
  const { data } = await apiRequest<Applicant[]>(`/api/v1/companies/me/applicants${query ? `?${query}` : ""}`);
  return data;
}

export async function updateApplicantPipeline(
  applicationId: string,
  payload: ApplicantPipelineUpdate,
): Promise<Applicant> {
  const { data } = await apiRequest<Applicant>(`/api/v1/companies/me/applicants/${applicationId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return data;
}

export async function publishInterviewAvailabilities(
  applicationId: string,
  payload: InterviewAvailabilityPublish,
): Promise<Applicant> {
  const { data } = await apiRequest<Applicant>(
    `/api/v1/companies/me/applicants/${applicationId}/interview-availabilities`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  return data;
}

export async function fetchRecruiters(): Promise<Recruiter[]> {
  const { data } = await apiRequest<Recruiter[]>("/api/v1/companies/me/recruiters");
  return data;
}

export async function createRecruiter(payload: RecruiterCreate): Promise<Recruiter> {
  const { data } = await apiRequest<Recruiter>("/api/v1/companies/me/recruiters", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return data;
}

export async function updateRecruiter(recruiterId: string, payload: RecruiterUpdate): Promise<Recruiter> {
  const { data } = await apiRequest<Recruiter>(`/api/v1/companies/me/recruiters/${recruiterId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return data;
}

export async function deleteRecruiter(recruiterId: string): Promise<void> {
  await apiRequest(`/api/v1/companies/me/recruiters/${recruiterId}`, { method: "DELETE" });
}
