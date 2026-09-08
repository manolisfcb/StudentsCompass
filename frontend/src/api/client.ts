/**
 * The single HTTP layer (plan 08 §7).
 *
 * Deliberately small: TASK-040 defines the error model and the request id,
 * TASK-042 adds session and CSRF double-submit, and TASK-043 generates the
 * types. What lives here now is only what the same-origin contract requires,
 * so those tasks extend one file instead of unpicking a guess.
 *
 * Two properties are already load-bearing:
 *   - every path is relative, so the browser sees one origin and cookies are
 *     first-party, whether the request goes through Vite's dev proxy or Nginx;
 *   - a non-2xx response becomes an `ApiError` carrying the status, so callers
 *     never branch on `res.ok` themselves.
 */

export class ApiError extends Error {
  readonly status: number;
  readonly requestId: string | null;
  readonly body: unknown;

  constructor(
    status: number,
    message: string,
    options: { requestId?: string | null; body?: unknown } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.requestId = options.requestId ?? null;
    this.body = options.body;
  }
}

/** Header the API will echo once TASK-040 lands; read defensively until then. */
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
