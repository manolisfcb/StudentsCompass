import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import {
  describeAuthError,
  login,
  logout,
  registerCompany,
  registerStudent,
} from "@/features/auth/api";
import "@/i18n";
import i18n from "@/i18n";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  // A 204 may not carry a body (the Response constructor throws if it does) —
  // exactly the shape fastapi-users' login and logout answer with on success.
  const hasBody = status !== 204;
  return new Response(hasBody ? JSON.stringify(body ?? {}) : null, {
    status,
    headers: hasBody ? { "content-type": "application/json", ...headers } : headers,
  });
}

const t = (key: string) => i18n.t(key);

describe("login", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("posts the OAuth2 password form to the student login path", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(204, null)));
    vi.stubGlobal("fetch", fetchMock);

    await login("student", { email: "person@example.invalid", password: "hunter2" });

    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/auth/student/login");
    expect(init.headers).toMatchObject({ "Content-Type": "application/x-www-form-urlencoded" });
    expect(init.body).toBe("grant_type=password&username=person%40example.invalid&password=hunter2");
  });

  it("posts to the company login path for a company account", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(204, null)));
    vi.stubGlobal("fetch", fetchMock);

    await login("company", { email: "team@example.invalid", password: "hunter2" });

    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/auth/company/login");
  });

  it("throws with the fastapi-users detail on bad credentials", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(400, { detail: "LOGIN_BAD_CREDENTIALS" })));
    vi.stubGlobal("fetch", fetchMock);

    await expect(login("student", { email: "a@b.invalid", password: "wrong" })).rejects.toThrow();
  });
});

describe("logout", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("posts to the actor's own logout path", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(204, null)));
    vi.stubGlobal("fetch", fetchMock);

    await logout("company");

    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/auth/company/logout");
    expect(init.method).toBe("POST");
  });
});

describe("registerStudent / registerCompany", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("posts JSON to the student register path", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(201, { id: "1", email: "a@b.invalid" })));
    vi.stubGlobal("fetch", fetchMock);

    await registerStudent({
      email: "a@b.invalid",
      password: "password123",
      first_name: "A",
      last_name: "B",
      nickname: "nick",
      is_active: true,
      is_superuser: false,
      is_verified: false,
    });

    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/auth/register");
    expect(init.headers).toMatchObject({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body as string)).toMatchObject({ email: "a@b.invalid", nickname: "nick" });
  });

  it("posts JSON to the company register path", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(201, { id: "1" })));
    vi.stubGlobal("fetch", fetchMock);

    await registerCompany({
      email: "team@example.invalid",
      password: "password123",
      company_name: "Acme",
    });

    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/auth/company/register");
  });

  it("surfaces REGISTER_USER_ALREADY_EXISTS as a translated message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(400, { detail: "REGISTER_USER_ALREADY_EXISTS" }))),
    );

    try {
      await registerStudent({
        email: "dup@example.invalid",
        password: "password123",
        is_active: true,
        is_superuser: false,
        is_verified: false,
      });
      expect.unreachable("registerStudent should have thrown");
    } catch (error) {
      expect(describeAuthError(error, t)).toBe(t("auth.register.error.alreadyExists"));
    }
  });
});

describe("describeAuthError", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("falls back to the generic message for a non-ApiError", () => {
    expect(describeAuthError(new Error("boom"), t)).toBe(t("auth.error.unexpected"));
  });

  it("maps LOGIN_BAD_CREDENTIALS to a friendly message", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(400, { detail: "LOGIN_BAD_CREDENTIALS" }))));

    try {
      await login("student", { email: "a@b.invalid", password: "wrong" });
      expect.unreachable("login should have thrown");
    } catch (error) {
      expect(describeAuthError(error, t)).toBe(t("auth.login.error.badCredentials"));
    }
  });

  it("shows the backend's own reason for an invalid-password detail object", async () => {
    const reason = "Password should be at least 8 characters";
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(jsonResponse(400, { detail: { code: "REGISTER_INVALID_PASSWORD", reason } })),
      ),
    );

    try {
      await registerStudent({
        email: "a@b.invalid",
        password: "short",
        is_active: true,
        is_superuser: false,
        is_verified: false,
      });
      expect.unreachable("registerStudent should have thrown");
    } catch (error) {
      expect(describeAuthError(error, t)).toBe(reason);
    }
  });
});
