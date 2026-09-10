import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import {
  fetchResourceDetail,
  fetchResourceProgress,
  fetchResources,
  fetchRoadmapDetail,
  fetchRoadmaps,
  fetchSavedRoadmaps,
  saveRoadmap,
  setLessonProgress,
  setTaskProgress,
  submitProject,
  unsaveRoadmap,
} from "@/features/resources-roadmaps/api";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

describe("resources-roadmaps api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("lists resources", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, [])));
    vi.stubGlobal("fetch", fetchMock);
    await fetchResources();
    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/resources");
  });

  it("fetches a resource's detail and progress from their own paths", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, {})));
    vi.stubGlobal("fetch", fetchMock);
    await fetchResourceDetail("r1");
    await fetchResourceProgress("r1");
    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    expect(calls.map(([path]) => path)).toEqual(["/api/v1/resources/r1", "/api/v1/resources/r1/progress"]);
  });

  it("patches lesson progress as JSON", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, {})));
    vi.stubGlobal("fetch", fetchMock);
    await setLessonProgress("l1", true);
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/resources/lessons/l1/progress");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ completed: true });
  });

  it("lists roadmaps and saved roadmaps from their own paths", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, [])));
    vi.stubGlobal("fetch", fetchMock);
    await fetchRoadmaps();
    await fetchSavedRoadmaps();
    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    expect(calls.map(([path]) => path)).toEqual(["/api/v1/roadmaps", "/api/v1/me/roadmaps"]);
  });

  it("fetches a roadmap's detail by slug", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, {})));
    vi.stubGlobal("fetch", fetchMock);
    await fetchRoadmapDetail("frontend-engineer");
    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/roadmaps/frontend-engineer");
  });

  it("saves a roadmap with PUT on the renamed idempotent path", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { roadmap_slug: "x", saved: true, popularity: 1 })));
    vi.stubGlobal("fetch", fetchMock);
    await saveRoadmap("x");
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/roadmaps/x/saves/me");
    expect(init.method).toBe("PUT");
  });

  it("unsaves a roadmap with DELETE on the renamed path", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { roadmap_slug: "x", saved: false, popularity: 0 })));
    vi.stubGlobal("fetch", fetchMock);
    await unsaveRoadmap("x");
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/roadmaps/x/saves/me");
    expect(init.method).toBe("DELETE");
  });

  it("patches task progress as JSON", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, {})));
    vi.stubGlobal("fetch", fetchMock);
    await setTaskProgress("t1", "in_progress");
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/tasks/t1/progress");
    expect(JSON.parse(init.body as string)).toEqual({ status: "in_progress" });
  });

  it("submits a project as JSON", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, {})));
    vi.stubGlobal("fetch", fetchMock);
    await submitProject("p1", { repo_url: "https://x", live_url: null, notes: null, status: "submitted" });
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/projects/p1/submit");
    expect(JSON.parse(init.body as string)).toMatchObject({ repo_url: "https://x", status: "submitted" });
  });
});
