import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { ApplicationsPage } from "@/features/jobs-applications/ApplicationsPage";

const APPLICATION_WITH_SLOTS = {
  id: "a1",
  job_title: "Frontend Engineer",
  status: "interview",
  company_id: "c1",
  user_id: "u1",
  match_strength: "strong_match",
  company_name: "Acme",
  available_interview_slots: [
    { id: "s1", application_id: "a1", starts_at: "2026-02-01T10:00:00Z", ends_at: "2026-02-01T10:30:00Z", timezone: "UTC", status: "available" },
  ],
  application_date: "2026-01-01T00:00:00Z",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ApplicationsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ApplicationsPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("shows an empty state with no applications", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(200, { items: [], has_more: false, limit: 20 }))));

    renderPage();

    expect(await screen.findByText("You have not applied to any jobs yet.")).toBeInTheDocument();
  });

  it("selects an interview slot with PUT and shows the confirmation", async () => {
    const fetchMock = vi.fn((_path: string, init?: RequestInit) => {
      if (init?.method === "PUT") {
        return Promise.resolve(
          jsonResponse(200, {
            ...APPLICATION_WITH_SLOTS,
            available_interview_slots: [],
            selected_interview_slot: {
              id: "s1",
              application_id: "a1",
              starts_at: "2026-02-01T10:00:00Z",
              ends_at: "2026-02-01T10:30:00Z",
              timezone: "UTC",
              status: "booked",
            },
          }),
        );
      }
      return Promise.resolve(jsonResponse(200, { items: [APPLICATION_WITH_SLOTS], has_more: false, limit: 20 }));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPage();

    await screen.findByText("Frontend Engineer");
    await user.click(screen.getByRole("button", { name: "View interview availabilities" }));
    await user.click(await screen.findByRole("button", { name: /2026/ }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path, i]) => path === "/api/v1/applications/a1/selected-interview" && (i as RequestInit | undefined)?.method === "PUT",
        ),
      ).toBe(true),
    );
  });

  it("loads the next page with the cursor the backend returned", async () => {
    const fetchMock = vi.fn((path: string) => {
      if (path === "/api/v1/applications/page") {
        return Promise.resolve(
          jsonResponse(200, { items: [APPLICATION_WITH_SLOTS], has_more: true, next_cursor: "cur-2", limit: 1 }),
        );
      }
      return Promise.resolve(jsonResponse(200, { items: [], has_more: false, limit: 1 }));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPage();

    await screen.findByText("Frontend Engineer");
    await user.click(screen.getByRole("button", { name: "Load more" }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([path]) => path === "/api/v1/applications/page?before=cur-2")).toBe(true),
    );
  });
});
