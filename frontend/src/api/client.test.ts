import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  SESSION_REFRESH_PATH,
  apiRequest,
  errorDetail,
  resetSessionRefreshState,
} from "@/api/client";
import { CSRF_COOKIE_NAME, CSRF_HEADER_NAME } from "@/api/csrf";

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

describe("CSRF double submit", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response("{}", {
            status: 200,
            headers: { "content-type": "application/json" },
          }),
        ),
      ),
    );
    document.cookie = `${CSRF_COOKIE_NAME}=token-from-cookie; path=/`;
    resetSessionRefreshState();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    document.cookie = `${CSRF_COOKIE_NAME}=; path=/; max-age=0`;
  });

  function headersOf(call: number): Headers {
    return new Headers(vi.mocked(fetch).mock.calls[call]?.[1]?.headers as HeadersInit);
  }

  it("copies the cookie into the header on an unsafe method", async () => {
    await apiRequest("/api/v1/anything", { method: "POST" });
    expect(headersOf(0).get(CSRF_HEADER_NAME)).toBe("token-from-cookie");
  });

  it("does not send the header on a safe method, which the API never checks", async () => {
    await apiRequest("/api/v1/anything");
    expect(headersOf(0).has(CSRF_HEADER_NAME)).toBe(false);
  });

  it("omits the header rather than sending an empty one when there is no cookie", async () => {
    document.cookie = `${CSRF_COOKIE_NAME}=; path=/; max-age=0`;
    await apiRequest("/api/v1/anything", { method: "POST" });
    expect(headersOf(0).has(CSRF_HEADER_NAME)).toBe(false);
  });

  it("reads the cookie per request, so a rotated token is picked up", async () => {
    await apiRequest("/api/v1/anything", { method: "POST" });
    document.cookie = `${CSRF_COOKIE_NAME}=rotated; path=/`;
    await apiRequest("/api/v1/anything", { method: "POST" });
    expect(headersOf(1).get(CSRF_HEADER_NAME)).toBe("rotated");
  });
});

describe("the single 401 retry", () => {
  function jsonResponse(status: number): Response {
    return new Response("{}", {
      status,
      headers: { "content-type": "application/json" },
    });
  }

  beforeEach(() => {
    resetSessionRefreshState();
    document.cookie = `${CSRF_COOKIE_NAME}=token-from-cookie; path=/`;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    document.cookie = `${CSRF_COOKIE_NAME}=; path=/; max-age=0`;
  });

  it("refreshes the session once and replays the request", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((path: string) => {
        calls.push(path);
        if (path === SESSION_REFRESH_PATH) return Promise.resolve(jsonResponse(200));
        return Promise.resolve(jsonResponse(calls.length === 1 ? 401 : 200));
      }),
    );

    const result = await apiRequest("/api/v1/protected");

    expect(result.status).toBe(200);
    expect(calls).toEqual(["/api/v1/protected", SESSION_REFRESH_PATH, "/api/v1/protected"]);
  });

  it("retries exactly once: a second 401 is raised, not chased", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((path: string) =>
        Promise.resolve(jsonResponse(path === SESSION_REFRESH_PATH ? 200 : 401)),
      ),
    );

    await expect(apiRequest("/api/v1/protected")).rejects.toBeInstanceOf(ApiError);
    // Original + refresh + replay. A fourth call would be an unbounded retry.
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(3);
  });

  it("does not retry when the refresh itself fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((path: string) =>
        Promise.resolve(jsonResponse(path === SESSION_REFRESH_PATH ? 401 : 401)),
      ),
    );

    await expect(apiRequest("/api/v1/protected")).rejects.toBeInstanceOf(ApiError);
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(2);
  });

  it("never refreshes in response to the refresh endpoint's own 401", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(401))));

    await expect(apiRequest(SESSION_REFRESH_PATH, { method: "POST" })).rejects.toBeInstanceOf(
      ApiError,
    );
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1);
  });

  it("collapses concurrent 401s into a single refresh", async () => {
    let refreshes = 0;
    const seen = new Set<string>();
    vi.stubGlobal(
      "fetch",
      vi.fn((path: string) => {
        if (path === SESSION_REFRESH_PATH) {
          refreshes += 1;
          return Promise.resolve(jsonResponse(200));
        }
        if (seen.has(path)) return Promise.resolve(jsonResponse(200));
        seen.add(path);
        return Promise.resolve(jsonResponse(401));
      }),
    );

    await Promise.all([
      apiRequest("/api/v1/a"),
      apiRequest("/api/v1/b"),
      apiRequest("/api/v1/c"),
    ]);

    expect(refreshes).toBe(1);
  });

  it("does not retry a 403, which is an authorization answer and not an expiry", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(403))));

    await expect(apiRequest("/api/v1/protected")).rejects.toBeInstanceOf(ApiError);
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1);
  });
});
