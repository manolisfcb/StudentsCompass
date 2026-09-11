/** REST-only client for the administration vertical (TASK-053). */

import { apiRequest } from "@/api/client";
import type { RequestOf, ResponseOf, Schemas } from "@/api/types";

export type AdminStats = ResponseOf<"admin_stats">;
export type AdminUsersPage = ResponseOf<"admin_list_users">;
export type AdminUser = Schemas["AdminUserRead"];
export type AdminUserPatch = RequestOf<"admin_update_user">;
export type AdminResourcesPage = ResponseOf<"admin_list_resources">;
export type AdminResource = Schemas["AdminResourceRead"];
export type AdminResourceDetail = ResponseOf<"admin_get_resource_detail">;
export type AdminResourceCreate = RequestOf<"admin_create_resource">;
export type AdminResourceStatePatch = RequestOf<"admin_update_resource_state">;
export type AdminResourceFile = ResponseOf<"admin_create_resource_file">;
export type AdminJobPostingsPage = ResponseOf<"admin_list_job_postings">;
export type AdminJobPostingPatch = RequestOf<"admin_update_job_posting">;
export type AdminCommunitiesPage = ResponseOf<"admin_list_communities">;
export type AdminCompaniesPage = ResponseOf<"admin_list_companies">;
export type AdminApplicationsPage = ResponseOf<"admin_list_applications">;

function pageQuery(page: number, pageSize: number): string {
  return new URLSearchParams({ page: String(page), page_size: String(pageSize) }).toString();
}

export async function fetchAdminStats(): Promise<AdminStats> {
  const { data } = await apiRequest<AdminStats>("/api/v1/admin/stats");
  return data;
}

export async function fetchAdminUsers(page = 1, pageSize = 20): Promise<AdminUsersPage> {
  const { data } = await apiRequest<AdminUsersPage>(`/api/v1/admin/users?${pageQuery(page, pageSize)}`);
  return data;
}

export async function updateAdminUser(userId: string, payload: AdminUserPatch): Promise<AdminUser> {
  const { data } = await apiRequest<AdminUser>(`/api/v1/admin/users/${userId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return data;
}

export async function deleteAdminUser(userId: string): Promise<void> {
  await apiRequest(`/api/v1/admin/users/${userId}`, { method: "DELETE" });
}

export async function fetchAdminResources(page = 1, pageSize = 20): Promise<AdminResourcesPage> {
  const { data } = await apiRequest<AdminResourcesPage>(
    `/api/v1/admin/resources?${pageQuery(page, pageSize)}`,
  );
  return data;
}

export async function fetchAdminResource(resourceId: string): Promise<AdminResourceDetail> {
  const { data } = await apiRequest<AdminResourceDetail>(`/api/v1/admin/resources/${resourceId}`);
  return data;
}

export async function createAdminResource(payload: AdminResourceCreate): Promise<void> {
  await apiRequest("/api/v1/admin/resources", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function replaceAdminResource(resourceId: string, payload: AdminResourceCreate): Promise<void> {
  await apiRequest(`/api/v1/admin/resources/${resourceId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function updateAdminResourceState(
  resourceId: string,
  payload: AdminResourceStatePatch,
): Promise<void> {
  await apiRequest(`/api/v1/admin/resources/${resourceId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteAdminResource(resourceId: string): Promise<void> {
  await apiRequest(`/api/v1/admin/resources/${resourceId}`, { method: "DELETE" });
}

export async function uploadAdminResourceFile(file: File): Promise<AdminResourceFile> {
  const body = new FormData();
  body.append("file", file);
  const { data } = await apiRequest<AdminResourceFile>("/api/v1/admin/resource-files", {
    method: "POST",
    body,
  });
  return data;
}

export async function fetchAdminJobPostings(page = 1, pageSize = 20): Promise<AdminJobPostingsPage> {
  const { data } = await apiRequest<AdminJobPostingsPage>(
    `/api/v1/admin/job-postings?${pageQuery(page, pageSize)}`,
  );
  return data;
}

export async function updateAdminJobPosting(
  jobId: string,
  payload: AdminJobPostingPatch,
): Promise<void> {
  await apiRequest(`/api/v1/admin/job-postings/${jobId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteAdminJobPosting(jobId: string): Promise<void> {
  await apiRequest(`/api/v1/admin/job-postings/${jobId}`, { method: "DELETE" });
}

export async function fetchAdminCommunities(page = 1, pageSize = 20): Promise<AdminCommunitiesPage> {
  const { data } = await apiRequest<AdminCommunitiesPage>(
    `/api/v1/admin/communities?${pageQuery(page, pageSize)}`,
  );
  return data;
}

export async function fetchAdminCompanies(page = 1, pageSize = 20): Promise<AdminCompaniesPage> {
  const { data } = await apiRequest<AdminCompaniesPage>(
    `/api/v1/admin/companies?${pageQuery(page, pageSize)}`,
  );
  return data;
}

export async function fetchAdminApplications(page = 1, pageSize = 20): Promise<AdminApplicationsPage> {
  const { data } = await apiRequest<AdminApplicationsPage>(
    `/api/v1/admin/applications?${pageQuery(page, pageSize)}`,
  );
  return data;
}
