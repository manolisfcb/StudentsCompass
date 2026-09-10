import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest, errorDetail } from "@/api/client";

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

  it("reads the catalogue code and the logged id out of the error envelope", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: {
            code: "rate_limited",
            message: "Too many requests.",
            details: null,
            request_id: "req-from-body",
          },
        }),
        {
          status: 429,
          // A different id in the header on purpose: the envelope's is the one
          // the server wrote to its log, so it must win.
          headers: { "content-type": "application/json", "x-request-id": "req-from-header" },
        },
      ),
    );

    const error = (await apiRequest("/api/v1/anything").catch(
      (thrown: unknown) => thrown,
    )) as ApiError;

    expect(error.code).toBe("rate_limited");
    expect(error.requestId).toBe("req-from-body");
    expect(error.detail?.message).toBe("Too many requests.");
  });

  it("leaves the code null when the failure never reached the API handlers", async () => {
    // What Nginx or the dev proxy answers when the API is not there at all.
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response("<html>502 Bad Gateway</html>", {
        status: 502,
        headers: { "content-type": "text/html" },
      }),
    );

    const error = (await apiRequest("/api/v1/anything").catch(
      (thrown: unknown) => thrown,
    )) as ApiError;

    expect(error.status).toBe(502);
    expect(error.code).toBeNull();
    expect(error.detail).toBeNull();
  });
});

describe("errorDetail", () => {
  it("rejects anything that is not the envelope", () => {
    expect(errorDetail(null)).toBeNull();
    expect(errorDetail("<html>502</html>")).toBeNull();
    expect(errorDetail({ detail: "the old FastAPI shape" })).toBeNull();
    // Shaped like the envelope but without the two keys a caller branches on.
    expect(errorDetail({ error: { request_id: "abc" } })).toBeNull();
  });
});
