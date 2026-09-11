import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import {
  createAdminResource,
  deleteAdminJobPosting,
  fetchAdminApplications,
  fetchAdminCommunities,
  fetchAdminCompanies,
  fetchAdminJobPostings,
  fetchAdminResources,
  fetchAdminStats,
  fetchAdminUsers,
  updateAdminJobPosting,
  updateAdminResourceState,
  updateAdminUser,
  uploadAdminResourceFile,
} from "@/features/admin/api";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("admin REST api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("uses numbered pages and explicit desired-state PATCHes", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, {})));
    vi.stubGlobal("fetch", fetchMock);

    await fetchAdminStats();
    await fetchAdminUsers(2, 20);
    await updateAdminUser("u1", { is_active: false });
    await fetchAdminResources(3, 10);
    await updateAdminResourceState("r1", { is_published: false, is_locked: true });

    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    expect(calls.map(([path, init]) => [path, init.method ?? "GET"])).toEqual([
      ["/api/v1/admin/stats", "GET"],
      ["/api/v1/admin/users?page=2&page_size=20", "GET"],
      ["/api/v1/admin/users/u1", "PATCH"],
      ["/api/v1/admin/resources?page=3&page_size=10", "GET"],
      ["/api/v1/admin/resources/r1", "PATCH"],
    ]);
    expect(JSON.parse(calls[2]![1].body as string)).toEqual({ is_active: false });
    expect(JSON.parse(calls[4]![1].body as string)).toEqual({ is_published: false, is_locked: true });
  });

  it("uses every renamed admin endpoint and never a legacy toggle/action path", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, {})));
    vi.stubGlobal("fetch", fetchMock);

    await fetchAdminJobPostings();
    await updateAdminJobPosting("j1", { is_active: false });
    await deleteAdminJobPosting("j1");
    await fetchAdminCommunities();
    await fetchAdminCompanies();
    await fetchAdminApplications();
    await uploadAdminResourceFile(new File(["hello"], "lesson.txt", { type: "text/plain" }));

    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    const paths = calls.map(([path]) => String(path));
    expect(paths).toContain("/api/v1/admin/job-postings?page=1&page_size=20");
    expect(paths).toContain("/api/v1/admin/job-postings/j1");
    expect(paths).toContain("/api/v1/admin/resource-files");
    expect(paths.every((path) => !path.includes("toggle-") && !path.includes("upload-file"))).toBe(true);
  });

  it("sends the generated ResourceCreate contract", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(201, {})));
    vi.stubGlobal("fetch", fetchMock);
    await createAdminResource({
      title: "Interview prep",
      description: "Practice",
      category: "career",
      is_published: true,
      is_locked: false,
      modules: [],
    });
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/admin/resources");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string).title).toBe("Interview prep");
  });
});
