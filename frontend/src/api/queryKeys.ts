/**
 * Query keys live in one place so an invalidation cannot miss a cache entry
 * because two features spelled the same resource differently (plan 08 §7).
 * Features append their own namespaces as they are migrated.
 */
export const queryKeys = {
  smoke: {
    origin: ["smoke", "origin"] as const,
  },
} as const;
