/**
 * The client half of the double-submit CSRF scheme (TASK-042).
 *
 * The backend sets `studentscompass_csrf` with `httponly=False` precisely so
 * this file can read it back and copy it into `X-CSRF-Token`
 * (`backend/app/core/csrf.py`). An attacker's page can cause the cookie to be
 * *sent*, but same-origin policy stops it from *reading* the value, so it
 * cannot produce the header — that asymmetry is the whole mechanism.
 *
 * Reading the cookie on each request rather than caching it matters: the API
 * rotates the token on `POST /auth/session/refresh`, and a cached copy would
 * make the request after a rotation fail with `csrf_token_invalid`.
 */

export const CSRF_COOKIE_NAME = "studentscompass_csrf";
export const CSRF_HEADER_NAME = "X-CSRF-Token";

/** Methods RFC 9110 calls safe. The API only checks the token on the others. */
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);

export function isSafeMethod(method: string | undefined): boolean {
  return SAFE_METHODS.has((method ?? "GET").toUpperCase());
}

export function readCsrfToken(cookieSource: string = document.cookie): string | null {
  for (const part of cookieSource.split(";")) {
    const separator = part.indexOf("=");
    if (separator === -1) continue;
    if (part.slice(0, separator).trim() !== CSRF_COOKIE_NAME) continue;
    const value = decodeURIComponent(part.slice(separator + 1).trim());
    return value === "" ? null : value;
  }
  return null;
}
