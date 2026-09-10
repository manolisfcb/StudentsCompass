import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { JobsPage } from "@/features/jobs-applications/JobsPage";

const BOARD = [
  {
    id: "p1",
    company_id: "c1",
    title: "Frontend Engineer",
    is_active: true,
    company_name: "Acme",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

const ELIGIBLE_RESUMES = [
  {
    id: "r1",
    original_filename: "resume.pdf",
    created_at: "2026-01-01T00:00:00Z",
    overall_score: 9,
    approved_at: "2026-01-01T00:00:00Z",
    is_latest: true,
  },
];

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <JobsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("JobsPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("quick-applies to a board posting with a chosen resume, sending an Idempotency-Key", async () => {
    const fetchMock = vi.fn((path: string) => {
      if (path.includes("/jobs/board")) return Promise.resolve(jsonResponse(200, BOARD));
      if (path.includes("/eligible-resumes")) return Promise.resolve(jsonResponse(200, ELIGIBLE_RESUMES));
      if (path === "/api/v1/applications") return Promise.resolve(jsonResponse(200, { id: "a1" }));
      return Promise.resolve(jsonResponse(200, {}));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPage();

    await screen.findByText("Frontend Engineer");
    await user.click(screen.getByRole("button", { name: "Quick Apply" }));

    await screen.findByText(/resume\.pdf/);
    await user.click(screen.getByRole("radio"));
    await user.click(screen.getByRole("button", { name: "Submit application" }));

    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    await waitFor(() =>
      expect(calls.some(([path, init]) => path === "/api/v1/applications" && init?.method === "POST")).toBe(true),
    );
    const [, init] = calls.find(
      ([path, i]) => path === "/api/v1/applications" && i?.method === "POST",
    ) as [string, RequestInit];
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toMatch(/^[0-9a-f-]{36}$/);
  });
});
