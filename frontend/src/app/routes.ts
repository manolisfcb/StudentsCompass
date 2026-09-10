import type { ActorType } from "@/api/session";

/**
 * Route constants, apart from the components that use them.
 *
 * They live here rather than in `guards.tsx` so that file exports only
 * components: mixing the two breaks React Fast Refresh, which is what the
 * `react-refresh/only-export-components` rule is warning about.
 */

export const SIGN_IN_PATH = "/login";

/** Where a signed-in actor belongs when they land somewhere anonymous-only. */
export function homePathFor(actorType: ActorType): string {
  return actorType === "recruiter" ? "/company" : "/dashboard";
}
