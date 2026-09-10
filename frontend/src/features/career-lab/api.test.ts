import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import {
  addManualResumeSkill,
  deleteResumeSkill,
  evaluateLearningRouteBaselines,
  fetchGapAnalysis,
  fetchLearningRouteRuns,
  fetchResumeSkillReview,
  fetchTargetRoles,
  optimizeLearningRoute,
  syncResumeSkills,
  updateResumeSkillStatus,
} from "@/features/career-lab/api";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

describe("career-lab api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("fetches the supported target roles", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { roles: [{ target_role: "Data Analyst" }] })));
    vi.stubGlobal("fetch", fetchMock);
    const roles = await fetchTargetRoles();
    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/capstone/analytics/roles");
    expect(roles).toEqual([{ target_role: "Data Analyst" }]);
  });

  it("fetches a resume's skill review", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { resume_id: "r1", skills: [] })));
    vi.stubGlobal("fetch", fetchMock);
    await fetchResumeSkillReview("r1");
    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/capstone/resumes/r1/skills");
  });

  it("syncs resume skills with POST", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { resume_id: "r1", extracted_skills: [] })));
    vi.stubGlobal("fetch", fetchMock);
    await syncResumeSkills("r1");
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/capstone/resumes/r1/skills/sync");
    expect(init.method).toBe("POST");
  });

  it("updates a resume skill's review status with PATCH", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { resume_id: "r1", skills: [] })));
    vi.stubGlobal("fetch", fetchMock);
    await updateResumeSkillStatus("r1", "s1", "confirmed");
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/capstone/resumes/r1/skills/s1");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ status: "confirmed" });
  });

  it("adds a manual skill", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { resume_id: "r1", skills: [] })));
    vi.stubGlobal("fetch", fetchMock);
    await addManualResumeSkill("r1", "python");
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/capstone/resumes/r1/skills/manual");
    expect(JSON.parse(init.body as string)).toMatchObject({ normalized_name: "python" });
  });

  it("deletes a resume skill", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { resume_id: "r1", skills: [] })));
    vi.stubGlobal("fetch", fetchMock);
    await deleteResumeSkill("r1", "s1");
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/capstone/resumes/r1/skills/s1");
    expect(init.method).toBe("DELETE");
  });

  it("fetches a gap analysis with resume_id and target_role as query params", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { status: "ok" })));
    vi.stubGlobal("fetch", fetchMock);
    await fetchGapAnalysis("r1", "Data Analyst");
    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/capstone/gap-analysis?resume_id=r1&target_role=Data+Analyst");
  });

  it("optimizes a learning route with an Idempotency-Key", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { status: "ok" })));
    vi.stubGlobal("fetch", fetchMock);
    await optimizeLearningRoute(
      { resume_id: "r1", target_role: "Data Analyst", budget: 100, available_hours: 30, max_courses: 2 },
      "11111111-1111-1111-1111-111111111111",
    );
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/capstone/learning-route/optimize");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBe(
      "11111111-1111-1111-1111-111111111111",
    );
  });

  it("evaluates learning route baselines with an Idempotency-Key", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { status: "ok" })));
    vi.stubGlobal("fetch", fetchMock);
    await evaluateLearningRouteBaselines(
      { resume_id: "r1", target_role: "Data Analyst", budget: 100, available_hours: 30, max_courses: 2 },
      "22222222-2222-2222-2222-222222222222",
    );
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/capstone/learning-route/evaluate-baselines");
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBe(
      "22222222-2222-2222-2222-222222222222",
    );
  });

  it("fetches learning route runs with a limit", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { runs: [] })));
    vi.stubGlobal("fetch", fetchMock);
    await fetchLearningRouteRuns(5);
    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/capstone/learning-route/runs?limit=5");
  });
});
