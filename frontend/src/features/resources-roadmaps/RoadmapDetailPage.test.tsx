import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { RoadmapDetailPage } from "@/features/resources-roadmaps/RoadmapDetailPage";

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
  total_tasks: 2,
  completed_tasks: 0,
  overall_progress_percent: 0,
  stages: [
    {
      id: "s1",
      order_index: 0,
      title: "Foundations",
      objective: "Learn the basics.",
      duration_weeks: 2,
      progress_percent: 0,
      tasks: [
        {
          id: "t1",
          order_index: 0,
          title: "Learn HTML",
          description: "Structure a page.",
          estimated_hours: 4,
          task_type: "learn",
          status: "not_started",
        },
      ],
      projects: [],
    },
  ],
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/roadmaps/frontend-engineer"]}>
        <Routes>
          <Route path="/roadmaps/:slug" element={<RoadmapDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RoadmapDetailPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("saves the roadmap and flips the button to 'Unsave'", async () => {
    const fetchMock = vi.fn((_path: string, init?: RequestInit) => {
      if (init?.method === "PUT") {
        return Promise.resolve(jsonResponse(200, { roadmap_slug: "frontend-engineer", saved: true, popularity: 5 }));
      }
      return Promise.resolve(jsonResponse(200, ROADMAP));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPage();

    const saveButton = await screen.findByRole("button", { name: "Save roadmap" });
    await user.click(saveButton);

    expect(await screen.findByRole("button", { name: "Unsave roadmap" })).toBeInTheDocument();
    const [, init] = fetchMock.mock.calls.find(([, i]) => i?.method === "PUT") as unknown as [string, RequestInit];
    expect(init.method).toBe("PUT");
  });

  it("updates task status and reflects the backend's recomputed progress, not a local guess", async () => {
    const fetchMock = vi.fn((_path: string, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        return Promise.resolve(
          jsonResponse(200, {
            task_id: "t1",
            status: "completed",
            stage_id: "s1",
            stage_progress_percent: 100,
            roadmap_id: "rm1",
            roadmap_progress_percent: 50,
            completed_tasks: 1,
            total_tasks: 2,
          }),
        );
      }
      return Promise.resolve(jsonResponse(200, ROADMAP));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPage();

    const select = await screen.findByDisplayValue("Not started");
    await user.selectOptions(select, "completed");

    await waitFor(() => expect(screen.getByText("1/2 tasks completed")).toBeInTheDocument());
  });
});
