import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { ResumeAuditWidget } from "@/features/profile-resumes/ResumeAuditWidget";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

function renderWidget() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <ResumeAuditWidget />
    </QueryClientProvider>,
  );
}

describe("ResumeAuditWidget", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("disables the widget once the daily limit is reached", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(200, { attempts_today: 3, daily_limit: 3, attempts_remaining: 0 }))),
    );

    renderWidget();

    expect(await screen.findByText("You have used all of today's audit attempts. Try again tomorrow.")).toBeInTheDocument();
    expect(document.querySelector('input[type="file"]')).toBeNull();
  });

  it("uploads with a fresh Idempotency-Key and shows a passing result", async () => {
    const fetchMock = vi.fn((_path: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        return Promise.resolve(
          jsonResponse(200, {
            resume_id: "r1",
            file_url: "https://x/y.pdf",
            original_filename: "resume.pdf",
            evaluation_id: "e1",
            overall_score: 9.2,
            llm_confidence: 0.9,
            pass_status: true,
            report: "Well structured.",
            reason_for_score: "Clear achievements.",
            main_weaknesses: [],
            improvements: ["Add metrics to the third bullet."],
            scores: {},
            attempts_today: 2,
            daily_limit: 3,
            attempts_remaining: 1,
          }),
        );
      }
      return Promise.resolve(jsonResponse(200, { attempts_today: 1, daily_limit: 3, attempts_remaining: 2 }));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderWidget();
    await screen.findByText("2 attempts remaining today");

    const file = new File(["%PDF-1.4"], "resume.pdf", { type: "application/pdf" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, file);

    await waitFor(() => expect(screen.getByText(/Great work\. Score: 9\.2\/10\. You passed\./)).toBeInTheDocument());
    expect(screen.getByText("Add metrics to the third bullet.")).toBeInTheDocument();

    const [, uploadInit] = fetchMock.mock.calls.find(([, init]) => init?.method === "POST") as unknown as [
      string,
      RequestInit,
    ];
    const idempotencyKey = (uploadInit.headers as Record<string, string>)["Idempotency-Key"];
    expect(idempotencyKey).toMatch(/^[0-9a-f-]{36}$/);
  });
});
