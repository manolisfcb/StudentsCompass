import { QueryClient } from "@tanstack/react-query";

/**
 * TanStack Query is the cache for server state; nothing duplicates it in a
 * global store (plan 08 §7). The defaults below are the conservative ones for
 * an authenticated product: a stale window short enough that a permission
 * change is noticed, and no blind retry on a 4xx, which would turn one
 * rejected request into four.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: false,
      },
    },
  });
}
