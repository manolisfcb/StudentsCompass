import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest } from "@/api/client";

describe("apiRequest", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response('{"ok":true}', {
            status: 200,
            headers: { "content-type": "application/json", "x-request-id": "abc" },
          }),
        ),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("refuses an absolute URL, which would give the browser a second origin", async () => {
    await expect(apiRequest("https://api.example.com/v1/users/me")).rejects.toThrow(
      /relative to the current origin/,
    );
    expect(fetch).not.toHaveBeenCalled();
  });

  it("returns the parsed body and the request id", async () => {
    const result = await apiRequest<{ ok: boolean }>("/api/v1/anything");
    expect(result.data.ok).toBe(true);
    expect(result.requestId).toBe("abc");
  });

  it("raises ApiError carrying the status and the body on a non-2xx", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response('{"detail":"nope"}', {
        status: 403,
        headers: { "content-type": "application/json" },
      }),
    );

    const error: unknown = await apiRequest("/api/v1/anything").catch(
      (thrown: unknown) => thrown,
    );

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(403);
    expect((error as ApiError).body).toEqual({ detail: "nope" });
  });
});
