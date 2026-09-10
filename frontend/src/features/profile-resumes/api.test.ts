import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import {
  deleteResume,
  fetchCourseAuditAttempts,
  fetchProfile,
  fetchResumes,
  updateProfile,
  uploadResume,
  uploadResumeForCourseAudit,
} from "@/features/profile-resumes/api";

function jsonResponse(status: number, body: unknown): Response {
  const hasBody = status !== 204;
  return new Response(hasBody ? JSON.stringify(body ?? {}) : null, {
    status,
    headers: hasBody ? { "content-type": "application/json" } : {},
  });
}

describe("profile-resumes api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("fetches the profile from /api/v1/users/me", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { id: "1", email: "a@b.invalid" })));
    vi.stubGlobal("fetch", fetchMock);

    await fetchProfile();

    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/users/me");
  });

  it("patches the profile as JSON", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { id: "1", email: "a@b.invalid" })));
    vi.stubGlobal("fetch", fetchMock);

    await updateProfile({ first_name: "Ada" });

    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/users/me");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ first_name: "Ada" });
  });

  it("lists resumes from the renamed /resumes path", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, [])));
    vi.stubGlobal("fetch", fetchMock);

    await fetchResumes();

    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/resumes");
  });

  it("uploads a resume as multipart form data under the 'cv' field, without setting Content-Type", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(jsonResponse(200, { file_url: "https://x/y.pdf", resume_id: "r1" })),
    );
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["%PDF-1.4"], "resume.pdf", { type: "application/pdf" });
    await uploadResume(file);

    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/resumes");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("cv")).toBe(file);
    expect((init.headers as Record<string, string> | undefined)?.["Content-Type"]).toBeUndefined();
  });

  it("deletes a resume by id on the renamed path", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { status: "deleted" })));
    vi.stubGlobal("fetch", fetchMock);

    await deleteResume("r1");

    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/resumes/r1");
    expect(init.method).toBe("DELETE");
  });

  it("fetches course-audit attempts from the nested path", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(jsonResponse(200, { attempts_today: 1, daily_limit: 3, attempts_remaining: 2 })),
    );
    vi.stubGlobal("fetch", fetchMock);

    await fetchCourseAuditAttempts();

    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/resume-course-audits/attempts");
  });

  it("uploads a course audit with the Idempotency-Key header set, unlike the legacy client", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        jsonResponse(200, {
          resume_id: "r1",
          file_url: "https://x/y.pdf",
          original_filename: "resume.pdf",
          evaluation_id: "e1",
          overall_score: 9,
          llm_confidence: 0.9,
          pass_status: true,
          report: "Good",
          reason_for_score: "Strong",
          main_weaknesses: [],
          improvements: [],
          scores: {},
          attempts_today: 1,
          daily_limit: 3,
          attempts_remaining: 2,
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["%PDF-1.4"], "resume.pdf", { type: "application/pdf" });
    await uploadResumeForCourseAudit(file, "11111111-1111-1111-1111-111111111111");

    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/resume-course-audits");
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBe(
      "11111111-1111-1111-1111-111111111111",
    );
    expect((init.body as FormData).get("cv")).toBe(file);
  });
});
