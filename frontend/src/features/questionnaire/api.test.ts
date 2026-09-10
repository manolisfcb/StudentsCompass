import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, resetSessionRefreshState } from "@/api/client";
import {
  fetchQuestionnaire,
  fetchQuestionnaireProfile,
  submitQuestionnaire,
} from "@/features/questionnaire/api";

function jsonResponse(status: number, body: unknown): Response {
  const hasBody = status !== 204;
  return new Response(hasBody ? JSON.stringify(body ?? {}) : null, {
    status,
    headers: hasBody ? { "content-type": "application/json" } : {},
  });
}

describe("questionnaire api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("fetches the current questionnaire", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(jsonResponse(200, { version: "v1", title: "Careers", questions: [] })),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchQuestionnaire();

    expect(result.version).toBe("v1");
    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/questionnaire");
  });

  it("submits answers as JSON", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        jsonResponse(200, {
          id: "r1",
          version: "v1",
          top_careers: [{ career: "Engineer", score: 9 }],
          created_at: "2026-01-01T00:00:00Z",
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await submitQuestionnaire({ answers: [{ question_id: "q1", option_id: "o1" }] });

    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/questionnaire");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ answers: [{ question_id: "q1", option_id: "o1" }] });
  });

  it("returns null for a person who has not completed the questionnaire (404)", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(404, { detail: "No questionnaire responses found" }))));

    const result = await fetchQuestionnaireProfile();

    expect(result).toBeNull();
  });

  it("still throws for a non-404 failure", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(500, { detail: "boom" }))));

    await expect(fetchQuestionnaireProfile()).rejects.toBeInstanceOf(ApiError);
  });
});
