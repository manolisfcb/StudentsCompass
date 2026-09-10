import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import {
  createApplication,
  fetchApplicationsPage,
  fetchCvAnalysisStatus,
  fetchEligibleResumes,
  fetchJobBoard,
  searchJobs,
  selectInterviewSlot,
  startCvAnalysis,
} from "@/features/jobs-applications/api";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

describe("jobs-applications api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("fetches the job board", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, [])));
    vi.stubGlobal("fetch", fetchMock);
    await fetchJobBoard();
    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/jobs/board?limit=50");
  });

  it("searches jobs on the renamed /job-searches path", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { students_compass: [], linkedin: [] })));
    vi.stubGlobal("fetch", fetchMock);
    await searchJobs({ keywords: "engineer", location: "Toronto", limit: 25, remote: false });
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/job-searches");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toMatchObject({ keywords: "engineer" });
  });

  it("starts a CV analysis on the renamed /cv-analyses path with an Idempotency-Key", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(jsonResponse(202, { job_id: "j1", status: "pending", message: "started" })),
    );
    vi.stubGlobal("fetch", fetchMock);
    await startCvAnalysis("11111111-1111-1111-1111-111111111111");
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/cv-analyses");
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBe(
      "11111111-1111-1111-1111-111111111111",
    );
  });

  it("polls CV analysis status on the renamed /cv-analyses/{id} path", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(jsonResponse(200, { job_id: "j1", status: "completed", created_at: "2026-01-01T00:00:00Z" })),
    );
    vi.stubGlobal("fetch", fetchMock);
    await fetchCvAnalysisStatus("j1");
    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/cv-analyses/j1");
  });

  it("fetches eligible resumes for a quick apply", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, [])));
    vi.stubGlobal("fetch", fetchMock);
    await fetchEligibleResumes();
    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/applications/eligible-resumes");
  });

  it("creates an application with an Idempotency-Key", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { id: "a1" })));
    vi.stubGlobal("fetch", fetchMock);
    await createApplication(
      { job_title: "Engineer", company_id: "c1", job_posting_id: "p1", resume_id: "r1" },
      "22222222-2222-2222-2222-222222222222",
    );
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/applications");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBe(
      "22222222-2222-2222-2222-222222222222",
    );
  });

  it("fetches a cursor page of applications, with and without a cursor", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { items: [], has_more: false, limit: 20 })));
    vi.stubGlobal("fetch", fetchMock);
    await fetchApplicationsPage(null);
    await fetchApplicationsPage("cursor-1");
    const paths = (fetchMock.mock.calls as unknown as [string, RequestInit][]).map(([path]) => path);
    expect(paths).toEqual(["/api/v1/applications/page", "/api/v1/applications/page?before=cursor-1"]);
  });

  it("selects an interview slot with PUT on the renamed idempotent path", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { id: "a1" })));
    vi.stubGlobal("fetch", fetchMock);
    await selectInterviewSlot("a1", "s1");
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/applications/a1/selected-interview");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body as string)).toEqual({ slot_id: "s1" });
  });
});
