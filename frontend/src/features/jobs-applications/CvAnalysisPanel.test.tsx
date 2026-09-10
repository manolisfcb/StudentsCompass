import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { CvAnalysisPanel } from "@/features/jobs-applications/CvAnalysisPanel";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

function renderPanel(onKeywords: (keywords: string) => void) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <CvAnalysisPanel onKeywords={onKeywords} />
    </QueryClientProvider>,
  );
}

describe("CvAnalysisPanel", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("starts analysis, polls, and reports keywords once the job completes", async () => {
    let pollCount = 0;
    const fetchMock = vi.fn((_path: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        return Promise.resolve(jsonResponse(202, { job_id: "j1", status: "pending", message: "started" }));
      }
      pollCount += 1;
      if (pollCount < 2) {
        return Promise.resolve(
          jsonResponse(200, { job_id: "j1", status: "processing", created_at: "2026-01-01T00:00:00Z" }),
        );
      }
      return Promise.resolve(
        jsonResponse(200, {
          job_id: "j1",
          status: "completed",
          keywords: "react, typescript",
          created_at: "2026-01-01T00:00:00Z",
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const onKeywords = vi.fn();

    renderPanel(onKeywords);

    await user.click(screen.getByRole("button", { name: "Use my CV" }));
    expect(await screen.findByRole("button", { name: "Analyzing your CV…" })).toBeInTheDocument();

    await vi.advanceTimersByTimeAsync(20000);

    expect(onKeywords).toHaveBeenCalledWith("react, typescript");
    expect(await screen.findByText("AI extracted these keywords: react, typescript")).toBeInTheDocument();
  });

  it("shows a timeout message if the job never settles within the bound", async () => {
    const fetchMock = vi.fn((_path: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        return Promise.resolve(jsonResponse(202, { job_id: "j1", status: "pending", message: "started" }));
      }
      return Promise.resolve(
        jsonResponse(200, { job_id: "j1", status: "processing", created_at: "2026-01-01T00:00:00Z" }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    renderPanel(vi.fn());

    await user.click(screen.getByRole("button", { name: "Use my CV" }));
    await vi.advanceTimersByTimeAsync(65000);

    expect(
      await screen.findByText("This is taking longer than expected. Check back in a moment."),
    ).toBeInTheDocument();
  });
});
