/**
 * Query keys live in one place so an invalidation cannot miss a cache entry
 * because two features spelled the same resource differently (plan 08 §7).
 * Features append their own namespaces as they are migrated.
 */
export const queryKeys = {
  session: {
    /** Read by every shell and guard, so it has exactly one key. */
    current: ["session"] as const,
  },
  smoke: {
    origin: ["smoke", "origin"] as const,
  },
} as const;
