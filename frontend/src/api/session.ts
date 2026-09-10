/**
 * Reading the session is the client's first call, and the only one every shell
 * makes (TASK-042 serves it at `GET /api/v1/auth/session`).
 *
 * The types come from the generated contract rather than being restated here,
 * so a field the API renames breaks the build instead of silently reading
 * `undefined` at runtime.
 */

import { ApiError, apiRequest } from "./client";
import type { ResponseOf, Schemas } from "./types";

export type Session = ResponseOf<"auth_read_session">;
export type SessionActor = Schemas["SessionActor"];
export type ActorType = SessionActor["actor_type"];

export const SESSION_PATH = "/api/v1/auth/session";

/**
 * The session, or `null` when nobody is signed in.
 *
 * A 401 here is an *answer*, not a failure: it is how the API says "anonymous".
 * Letting it throw would put every public page into an error boundary. Every
 * other status still throws, because "the API is down" and "you are logged
 * out" must not render the same way.
 */
export async function fetchSession(): Promise<Session | null> {
  try {
    // No retry: a 401 here *is* the answer ("anonymous"). Refreshing would add
    // a guaranteed-failing request to every anonymous page load.
    const { data } = await apiRequest<Session>(SESSION_PATH, {}, { retryOnUnauthorized: false });
    return data;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}
