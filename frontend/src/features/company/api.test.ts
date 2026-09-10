import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import {
  createJobPosting,
  createRecruiter,
  deleteJobPosting,
  deleteRecruiter,
  fetchApplicants,
  fetchCompanyDashboard,
  fetchCurrentRecruiter,
  fetchJobPostings,
  fetchRecruiters,
  publishInterviewAvailabilities,
  updateApplicantPipeline,
  updateJobPosting,
  updateRecruiter,
} from "@/features/company/api";

function jsonResponse(status: number, body: unknown): Response {
  const hasBody = status !== 204;
  return new Response(hasBody ? JSON.stringify(body ?? {}) : null, {
    status,
    headers: hasBody ? { "content-type": "application/json" } : {},
  });
}

describe("company api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("fetches the company dashboard on the renamed /companies/me/dashboard path", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, {})));
    vi.stubGlobal("fetch", fetchMock);
    await fetchCompanyDashboard();
    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/companies/me/dashboard");
  });

  it("fetches the current recruiter's own profile", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, {})));
    vi.stubGlobal("fetch", fetchMock);
    await fetchCurrentRecruiter();
    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/companies/me/recruiters/current");
  });

  it("lists, creates, updates and deletes a job posting", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { id: "p1" })));
    vi.stubGlobal("fetch", fetchMock);

    await fetchJobPostings();
    await createJobPosting({ title: "Engineer", is_active: true });
    await updateJobPosting("p1", { is_active: false });
    await deleteJobPosting("p1");

    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    expect(calls.map(([path, init]) => [path, init.method ?? "GET"])).toEqual([
      ["/api/v1/companies/me/job-postings", "GET"],
      ["/api/v1/companies/me/job-postings", "POST"],
      ["/api/v1/companies/me/job-postings/p1", "PATCH"],
      ["/api/v1/companies/me/job-postings/p1", "DELETE"],
    ]);
  });

  it("fetches applicants with status and job posting filters as query params", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, [])));
    vi.stubGlobal("fetch", fetchMock);

    await fetchApplicants({ jobPostingId: "p1", statuses: ["in_review", "interview"] });

    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    const url = new URL(path, "http://localhost");
    expect(url.pathname).toBe("/api/v1/companies/me/applicants");
    expect(url.searchParams.get("job_posting_id")).toBe("p1");
    expect(url.searchParams.getAll("status")).toEqual(["in_review", "interview"]);
  });

  it("updates an applicant's pipeline status", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, {})));
    vi.stubGlobal("fetch", fetchMock);
    await updateApplicantPipeline("a1", { status: "interview" });
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/companies/me/applicants/a1");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ status: "interview" });
  });

  it("publishes interview availabilities", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, {})));
    vi.stubGlobal("fetch", fetchMock);
    await publishInterviewAvailabilities("a1", {
      slots: [{ starts_at: "2026-02-01T10:00:00Z", ends_at: "2026-02-01T10:30:00Z", timezone: "UTC" }],
    });
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/companies/me/applicants/a1/interview-availabilities");
    expect(init.method).toBe("POST");
  });

  it("lists, invites, updates and removes recruiters", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { id: "r1" })));
    vi.stubGlobal("fetch", fetchMock);

    await fetchRecruiters();
    await createRecruiter({ email: "a@b.invalid", password: "password123", role: "recruiter" });
    await updateRecruiter("r1", { role: "admin" });
    await deleteRecruiter("r1");

    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    expect(calls.map(([path, init]) => [path, init.method ?? "GET"])).toEqual([
      ["/api/v1/companies/me/recruiters", "GET"],
      ["/api/v1/companies/me/recruiters", "POST"],
      ["/api/v1/companies/me/recruiters/r1", "PATCH"],
      ["/api/v1/companies/me/recruiters/r1", "DELETE"],
    ]);
  });
});
