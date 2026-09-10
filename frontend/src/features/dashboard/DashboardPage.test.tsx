import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { DashboardPage } from "@/features/dashboard/DashboardPage";

const DASHBOARD = {
  user: { id: "u1", email: "ada@example.invalid", nickname: "Ada", first_name: "Ada", last_name: "Lovelace" },
  stats: {
    overall_progress: 42,
    total_applications: 5,
    in_review: 2,
    interviews_scheduled: 1,
    offers_received: 0,
    applied: 2,
  },
  progress: { resume: 80, linkedin: 60, interview_prep: 40, portfolio: 20 },
  application_breakdown: { applied: 2, in_review: 2, interviews: 1, offers: 0 },
  resource_navigation: { resume: "/resources/r1", linkedin: "/resources/r2", interview_prep: "/resources", portfolio: "/resources" },
  recent_applications: [],
  resources: [{ title: "Resume Templates", url: "#", icon: "📄" }],
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

describe("DashboardPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("renders the numbers the backend sent, without recomputing anything", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(200, DASHBOARD))));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });

    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Welcome back, Ada")).toBeInTheDocument();
    expect(screen.getByText("42%")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("80%")).toBeInTheDocument();
    expect(screen.getByText("Resume Templates")).toBeInTheDocument();

    const resumeLink = screen.getByText("Resume").closest("a");
    expect(resumeLink).toHaveAttribute("href", "/resources/r1");
  });
});
