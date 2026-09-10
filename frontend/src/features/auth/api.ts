/**
 * Login, register and logout for both actors (TASK-046, plan 08 §8).
 *
 * These three endpoints are fastapi-users' own routers
 * (`fastapi_users.get_auth_router` / `get_register_router`, mounted in
 * `app/app.py`), not the app's `/api/v1` handlers. That matters for error
 * shape: everywhere else in the contract a failure is the envelope TASK-040
 * defines (`{"error": {"code": ..., "message": ...}}`), but these answer with
 * fastapi-users' own `{"detail": "LOGIN_BAD_CREDENTIALS"}` — a bare code, not
 * a message meant for a person. `describeAuthError` below is what translates
 * the closed set of codes fastapi-users actually raises into copy; the login
 * form showing `LOGIN_BAD_CREDENTIALS` verbatim (which the legacy JS did) is
 * exactly the kind of thing F-03's "render user-facing text as text, not as
 * whatever the server happened to send" lesson generalizes to.
 */

import { ApiError, apiRequest } from "@/api/client";
import type { RequestOf } from "@/api/types";

export type ActorKind = "student" | "company";

const LOGIN_PATH: Record<ActorKind, string> = {
  student: "/api/v1/auth/student/login",
  company: "/api/v1/auth/company/login",
};

const LOGOUT_PATH: Record<ActorKind, string> = {
  student: "/api/v1/auth/student/logout",
  company: "/api/v1/auth/company/logout",
};

export const REGISTER_STUDENT_PATH = "/api/v1/auth/register";
export const REGISTER_COMPANY_PATH = "/api/v1/auth/company/register";

export interface Credentials {
  email: string;
  password: string;
}

/** `Body_auth_jwt_login` / `Body_companies_auth_jwt_login`: OAuth2 password form, not JSON. */
async function postCredentials(path: string, { email, password }: Credentials): Promise<void> {
  const body = new URLSearchParams({ grant_type: "password", username: email, password });
  await apiRequest(
    path,
    {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
    },
    // A login attempt's own 401/400 is the answer being tested, not a session
    // that needs refreshing.
    { retryOnUnauthorized: false },
  );
}

export async function login(kind: ActorKind, credentials: Credentials): Promise<void> {
  await postCredentials(LOGIN_PATH[kind], credentials);
}

export async function logout(kind: ActorKind): Promise<void> {
  await apiRequest(LOGOUT_PATH[kind], { method: "POST" }, { retryOnUnauthorized: false });
}

export type StudentRegistration = RequestOf<"auth_register_register">;
export type CompanyRegistration = RequestOf<"companies_register_company_with_initial_recruiter">;

export async function registerStudent(payload: StudentRegistration): Promise<void> {
  await apiRequest(
    REGISTER_STUDENT_PATH,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    { retryOnUnauthorized: false },
  );
}

export async function registerCompany(payload: CompanyRegistration): Promise<void> {
  await apiRequest(
    REGISTER_COMPANY_PATH,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    { retryOnUnauthorized: false },
  );
}

/** The fastapi-users detail codes these three routes actually raise. */
type FastapiUsersDetail =
  | "LOGIN_BAD_CREDENTIALS"
  | "LOGIN_USER_NOT_VERIFIED"
  | "REGISTER_USER_ALREADY_EXISTS"
  | (string & {});

function fastapiUsersDetail(body: unknown): string | { code?: string; reason?: string } | null {
  if (typeof body !== "object" || body === null || !("detail" in body)) return null;
  const detail = (body as { detail: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (typeof detail === "object" && detail !== null) return detail as { code?: string; reason?: string };
  return null;
}

/**
 * A message safe to show under the form, for any of the six calls above.
 *
 * `t` is threaded in rather than imported, so this stays a plain function the
 * pages and their tests can call without mounting the i18n provider twice.
 */
export function describeAuthError(error: unknown, t: (key: string) => string): string {
  if (!(error instanceof ApiError)) return t("auth.error.unexpected");

  // The app's own envelope (rate limiting, CSRF) — TASK-040's message is
  // already meant to be read.
  if (error.detail) return error.detail.message;

  const detail = fastapiUsersDetail(error.body);
  if (typeof detail === "string") {
    const code = detail as FastapiUsersDetail;
    switch (code) {
      case "LOGIN_BAD_CREDENTIALS":
        return t("auth.login.error.badCredentials");
      case "LOGIN_USER_NOT_VERIFIED":
        return t("auth.login.error.notVerified");
      case "REGISTER_USER_ALREADY_EXISTS":
        return t("auth.register.error.alreadyExists");
      default:
        return t("auth.error.unexpected");
    }
  }
  // `InvalidPasswordException.reason` (REGISTER_INVALID_PASSWORD) is already a
  // sentence the backend composed for a person; showing it is not
  // reimplementing the password policy, only displaying its answer.
  if (detail?.reason) return detail.reason;

  return t("auth.error.unexpected");
}
