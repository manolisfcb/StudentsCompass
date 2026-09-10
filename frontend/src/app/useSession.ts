import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { fetchSession, type Session } from "@/api/session";
import { queryKeys } from "@/api/queryKeys";

/**
 * The one place the session is read. TanStack Query is the cache, so the
 * session is not copied into a global store (plan 08 §7) — a copy is what
 * makes a logged-out tab keep rendering a signed-in menu.
 *
 * `null` is a settled answer meaning "anonymous", not an error.
 */
export function useSession(): UseQueryResult<Session | null> {
  return useQuery({
    queryKey: queryKeys.session.current,
    queryFn: fetchSession,
    // Longer than the default: every shell mounts this, and the value only
    // changes on login, logout or an explicit refresh — all of which
    // invalidate the key directly.
    staleTime: 60_000,
    retry: false,
  });
}
