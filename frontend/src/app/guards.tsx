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

/**
 * Renders `children` only for a signed-in student who is also a superuser.
 *
 * `RequireActor allow={["student"]}` is not enough for `/admin`, and the
 * difference is not cosmetic: the monolith bounced `user is None or not
 * user.is_superuser` to `/admin/login` (`backend/app/views/views.py`), so an
 * ordinary student never saw the panel. Guarding only on `actor_type`
 * reproduced the *permissions* faithfully — every `/api/v1/admin/*` call still
 * answers 403 to a non-admin, and nothing leaks — but not the *navigation*: the
 * student landed on the admin shell and watched it fill with errors instead of
 * being sent away. TASK-053 asks for "el acceso prohibido responde igual", and
 * that was a different answer.
 *
 * This still decides rendering only. `is_superuser` arrives from the session
 * for the same reason `actor_type` does, and carries no more authority.
 */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const session = useSession();
  const location = useLocation();

  return (
    <AsyncBoundary query={session}>
      {(value) => {
        const admin = value?.actors.find(
          (actor) => actor.actor_type === "student" && actor.is_superuser,
        );
        if (!admin) {
          // Same destination for "not signed in" and "signed in without
          // rights", as in the monolith: the admin sign-in screen does not
          // confirm that some other account would have got in.
          return <Navigate to="/admin/login" replace state={{ from: location }} />;
        }
        return <>{children}</>;
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
