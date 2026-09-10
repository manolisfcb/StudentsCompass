/**
 * The single HTTP layer (plan 08 §7).
 *
 * Deliberately small: TASK-040 defines the error model and the request id,
 * TASK-042 adds session and CSRF double-submit, and TASK-043 generates the
 * types. What lives here now is only what the same-origin contract requires,
 * so those tasks extend one file instead of unpicking a guess.
 *
 * Five properties are load-bearing:
 *   - every path is relative, so the browser sees one origin and cookies are
 *     first-party, whether the request goes through Vite's dev proxy or Nginx;
 *   - a non-2xx response becomes an `ApiError` carrying the status, so callers
 *     never branch on `res.ok` themselves;
 *   - that `ApiError` carries the *contract's* error shape, not a guess: the
 *     envelope and the code catalogue come from `src/api/types.ts`, which is
 *     generated from the same OpenAPI the API serves;
 *   - every unsafe method carries `X-CSRF-Token` automatically, so no caller
 *     can forget it and no caller needs to know the scheme exists (TASK-044);
 *   - a `401` is retried exactly once, behind a session refresh. Exactly once,
 *     not "until it works": a genuinely expired session would otherwise turn
 *     every navigation into an unbounded retry storm against `/auth/session`.
 *     Callers whose `401` *is* the answer opt out — see `RequestOptions`.
 */

import { CSRF_HEADER_NAME, isSafeMethod, readCsrfToken } from "./csrf";
import type { ApiErrorDetail, ApiErrorResponse, ErrorCode } from "./types";

/**
 * Reads the error envelope out of a response body, or `null` if it is not one.
 *
 * Not every failure arrives shaped: Nginx, the dev proxy or a crash before the
 * handlers run answer with HTML or with nothing. The guard is what keeps a
 * caller reading `error.code` from throwing a second, worse error on top of the
 * first one.
 */
export function errorDetail(body: unknown): ApiErrorDetail | null {
  if (typeof body !== "object" || body === null || !("error" in body)) return null;
  const detail = (body as ApiErrorResponse).error;
  if (typeof detail !== "object" || detail === null) return null;
  return typeof detail.code === "string" && typeof detail.message === "string"
    ? detail
    : null;
}

export class ApiError extends Error {
  readonly status: number;
  readonly requestId: string | null;
  readonly body: unknown;
  /**
   * The catalogue code, when the API answered with its own envelope.
   *
   * `null` means the failure did not come from the API's error handlers, so
   * there is nothing to branch on and only the status is meaningful.
   */
  readonly code: ErrorCode | null;
  readonly detail: ApiErrorDetail | null;

  constructor(
    status: number,
    message: string,
    options: { requestId?: string | null; body?: unknown } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = options.body;
    this.detail = errorDetail(options.body);
    this.code = this.detail?.code ?? null;
    // The envelope's own id is the one the server logged. The header is the
    // fallback for a failure that never reached the handlers.
    this.requestId = this.detail?.request_id ?? options.requestId ?? null;
  }
}

/** Header the API echoes on every response (TASK-040). */
const REQUEST_ID_HEADER = "x-request-id";

function assertRelativePath(path: string): void {
  if (!path.startsWith("/")) {
    throw new Error(
      `API paths must be relative to the current origin, got "${path}". ` +
        "An absolute URL would make the browser see two origins and drop cookies.",
    );
  }
}

async function readBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return await response.text();
  }
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export interface ApiResponse<T> {
  status: number;
  requestId: string | null;
  data: T;
}

export interface RequestOptions {
  /**
   * Whether a `401` should trigger one session refresh and one replay.
   *
   * On by default, because for almost every endpoint a `401` means the session
   * expired mid-session. It is turned off for the few whose `401` is a settled
   * *answer* rather than a failure — `GET /auth/session` says "anonymous" that
   * way. Refreshing there would make every anonymous page load cost a second,
   * guaranteed-failing request.
   */
  retryOnUnauthorized?: boolean;
}

/**
 * Path the client calls to mint a fresh session and CSRF token (TASK-042).
 *
 * Refreshing is explicit rather than sliding: the API re-issues the cookie only
 * when asked, so an idle tab's session still expires on schedule.
 */
export const SESSION_REFRESH_PATH = "/api/v1/auth/session/refresh";

/**
 * Set while a refresh is in flight so N concurrent 401s produce one refresh.
 *
 * Without this, a screen that fires six queries on mount would fire six
 * refreshes, and five of them would race against the token the first one
 * rotated — turning an expired session into a burst of `csrf_token_invalid`.
 */
let refreshInFlight: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  refreshInFlight ??= (async () => {
    try {
      const response = await fetch(SESSION_REFRESH_PATH, {
        method: "POST",
        credentials: "same-origin",
        headers: withCsrfHeader({ Accept: "application/json" }, "POST"),
      });
      return response.ok;
    } catch {
      // The network is down, not the session. Reporting `false` lets the
      // original 401 surface unchanged instead of being masked.
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();
  return await refreshInFlight;
}

/** Exposed for tests, which must not leak a pending refresh between cases. */
export function resetSessionRefreshState(): void {
  refreshInFlight = null;
}

function withCsrfHeader(headers: HeadersInit, method: string | undefined): HeadersInit {
  if (isSafeMethod(method)) return headers;
  const token = readCsrfToken();
  // No cookie yet means no session yet, so there is nothing to forge. Sending
  // an empty header would be refused by `tokens_match` anyway; omitting it
  // keeps the API's own error ("no token") legible.
  return token === null ? headers : { ...headers, [CSRF_HEADER_NAME]: token };
}

async function performRequest(path: string, init: RequestInit): Promise<Response> {
  return await fetch(path, {
    // Session cookies are the authentication mechanism; a same-origin request
    // that forgets this silently authenticates as nobody.
    credentials: "same-origin",
    ...init,
    headers: withCsrfHeader(
      {
        Accept: "application/json",
        ...init.headers,
      },
      init.method,
    ),
  });
}

/** Performs the request and returns the parsed body, raising on non-2xx. */
export async function apiRequest<T = unknown>(
  path: string,
  init: RequestInit = {},
  { retryOnUnauthorized = true }: RequestOptions = {},
): Promise<ApiResponse<T>> {
  assertRelativePath(path);

  let response = await performRequest(path, init);

  // The one retry. Refreshing the session is itself a request that can 401, so
  // it is excluded explicitly rather than by counting depth.
  if (retryOnUnauthorized && response.status === 401 && path !== SESSION_REFRESH_PATH) {
    if (await refreshSession()) {
      response = await performRequest(path, init);
    }
  }

  const requestId = response.headers.get(REQUEST_ID_HEADER);
  const body = await readBody(response);

  if (!response.ok) {
    throw new ApiError(response.status, `${response.status} ${path}`, {
      requestId,
      body,
    });
  }

  return { status: response.status, requestId, data: body as T };
}

/**
 * Like `apiRequest`, but reports the status instead of throwing on 4xx/5xx.
 * The smoke page needs this: a 401 from `/api/v1/users/me` is the *expected*
 * anonymous answer and is precisely what proves the proxy reached the API.
 */
export async function apiProbe(
  path: string,
): Promise<{ status: number; requestId: string | null }> {
  try {
    // No retry: the probe is asking what the API answers *now*, and a refresh
    // would both change the answer and cost a request that must fail.
    const { status, requestId } = await apiRequest(path, {}, { retryOnUnauthorized: false });
    return { status, requestId };
  } catch (error) {
    if (error instanceof ApiError) {
      return { status: error.status, requestId: error.requestId };
    }
    throw error;
  }
}
