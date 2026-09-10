import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { RoadmapsListPage } from "@/features/resources-roadmaps/RoadmapsListPage";

const ROADMAP = {
  id: "rm1",
  slug: "frontend-engineer",
  title: "Frontend Engineer",
  description: "Become a frontend engineer.",
  role_target: "Frontend Engineer",
  difficulty: "intermediate",
  duration_weeks_min: 8,
  duration_weeks_max: 12,
  popularity: 4,
  is_saved: false,
  total_tasks: 0,
  completed_tasks: 0,
  overall_progress_percent: 0,
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RoadmapsListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RoadmapsListPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("shows an empty state for saved roadmaps and lists the browsable ones", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((path: string) => {
        if (path === "/api/v1/me/roadmaps") return Promise.resolve(jsonResponse(200, []));
        return Promise.resolve(jsonResponse(200, [ROADMAP]));
      }),
    );

    renderPage();

    expect(await screen.findByText("You have not saved any roadmaps yet.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Frontend Engineer/ })).toHaveAttribute(
      "href",
      "/roadmaps/frontend-engineer",
    );
  });

  it("renders a saved roadmap's progress from the backend response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((path: string) => {
        if (path === "/api/v1/me/roadmaps") {
          return Promise.resolve(
            jsonResponse(200, [
              { saved_at: "2026-01-01T00:00:00Z", roadmap: { ...ROADMAP, total_tasks: 4, completed_tasks: 1, overall_progress_percent: 25 } },
            ]),
          );
        }
        return Promise.resolve(jsonResponse(200, []));
      }),
    );

    renderPage();

    expect(await screen.findByText("1/4 tasks completed")).toBeInTheDocument();
  });
});
