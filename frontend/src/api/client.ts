/**
 * The single HTTP layer (plan 08 §7).
 *
 * Deliberately small: TASK-040 defines the error model and the request id,
 * TASK-042 adds session and CSRF double-submit, and TASK-043 generates the
 * types. What lives here now is only what the same-origin contract requires,
 * so those tasks extend one file instead of unpicking a guess.
 *
 * Three properties are load-bearing:
 *   - every path is relative, so the browser sees one origin and cookies are
 *     first-party, whether the request goes through Vite's dev proxy or Nginx;
 *   - a non-2xx response becomes an `ApiError` carrying the status, so callers
 *     never branch on `res.ok` themselves;
 *   - that `ApiError` carries the *contract's* error shape, not a guess: the
 *     envelope and the code catalogue come from `src/api/types.ts`, which is
 *     generated from the same OpenAPI the API serves.
 */

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

/** Performs the request and returns the parsed body, raising on non-2xx. */
export async function apiRequest<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<ApiResponse<T>> {
  assertRelativePath(path);

  const response = await fetch(path, {
    // Session cookies are the authentication mechanism; a same-origin request
    // that forgets this silently authenticates as nobody.
    credentials: "same-origin",
    ...init,
    headers: {
      Accept: "application/json",
      ...init.headers,
    },
  });

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
    const { status, requestId } = await apiRequest(path);
    return { status, requestId };
  } catch (error) {
    if (error instanceof ApiError) {
      return { status: error.status, requestId: error.requestId };
    }
    throw error;
  }
}
