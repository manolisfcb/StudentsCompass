import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import type { ActorType } from "@/api/session";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { SIGN_IN_PATH, homePathFor } from "@/app/routes";
import { useSession } from "@/app/useSession";

/**
 * Navigation guards. They decide **what to render**, never what is allowed.
 *
 * This distinction is the whole point and is easy to erode: every endpoint
 * behind a guarded route re-checks authorization for itself, and a guard that
 * passes by mistake produces a 403 from the API, not an escalation. Reading
 * `actor_type` to pick a menu is a rendering decision; anything that reads it
 * to decide whether an action is *permitted* belongs in the backend.
 *
 * See `backend/app/schemas/sessionSchema.py`, which says the same thing from
 * the other side of the wire.
 */

/**
 * Renders `children` only for a signed-in actor of one of `allow`.
 *
 * The redirect carries the attempted location in state so the sign-in screen
 * (TASK-046) can return the person where they were going.
 */
export function RequireActor({
  allow,
  signInPath = SIGN_IN_PATH,
  children,
}: {
  allow: readonly ActorType[];
  signInPath?: string;
  children: ReactNode;
}) {
  const session = useSession();
  const location = useLocation();

  return (
    <AsyncBoundary query={session}>
      {(value) => {
        if (value === null) {
          return <Navigate to={signInPath} replace state={{ from: location }} />;
        }
        // `actors` rather than `actor`: a person holding both a student and a
        // recruiter cookie should reach either surface without signing out of
        // the other. `actor` is only the default presentation.
        const matches = value.actors.some((actor) => allow.includes(actor.actor_type));
        return matches ? <>{children}</> : <Navigate to={homePathFor(value.actor.actor_type)} replace />;
      }}
    </AsyncBoundary>
  );
}

/** The mirror image: keeps a signed-in actor off the sign-in screen. */
export function RequireAnonymous({ children }: { children: ReactNode }) {
  const session = useSession();

  return (
    <AsyncBoundary query={session}>
      {(value) =>
        value === null ? (
          <>{children}</>
        ) : (
          <Navigate to={homePathFor(value.actor.actor_type)} replace />
        )
      }
    </AsyncBoundary>
  );
}
