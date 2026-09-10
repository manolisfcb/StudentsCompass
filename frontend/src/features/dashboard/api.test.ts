import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import { fetchStudentDashboard } from "@/features/dashboard/api";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

describe("dashboard api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("fetches the renamed /dashboard/student path", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { stats: {} })));
    vi.stubGlobal("fetch", fetchMock);

    await fetchStudentDashboard();

    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/dashboard/student");
  });
});
