import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { ResourceDetailPage } from "@/features/resources-roadmaps/ResourceDetailPage";

const RESOURCE = {
  id: "r1",
  title: "Interview Prep",
  description: "Get ready for interviews.",
  category: "Career",
  is_published: true,
  is_locked: false,
  created_at: "2026-01-01T00:00:00Z",
  modules: [
    {
      id: "m1",
      resource_id: "r1",
      title: "Module 1",
      position: 0,
      lessons: [
        { id: "l1", module_id: "m1", title: "Intro", position: 0, content_type: "text", content: "Welcome.", created_at: "2026-01-01T00:00:00Z" },
        { id: "l2", module_id: "m1", title: "Practice", position: 1, content_type: "text", content: "Practice time.", created_at: "2026-01-01T00:00:00Z" },
      ],
    },
  ],
};

const PROGRESS = {
  resource_id: "r1",
  completed_lesson_ids: [],
  completed_lessons: 0,
  total_lessons: 2,
  progress_percent: 0,
  modules: [{ module_id: "m1", completed_lessons: 0, total_lessons: 2, progress_percent: 0 }],
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/resources/r1"]}>
        <Routes>
          <Route path="/resources/:resourceId" element={<ResourceDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ResourceDetailPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("shows the first lesson, and marking it complete advances to the next", async () => {
    const fetchMock = vi.fn((path: string) => {
      if (path.endsWith("/progress") && !path.includes("lessons")) {
        return Promise.resolve(jsonResponse(200, PROGRESS));
      }
      if (path.includes("/lessons/l1/progress")) {
        return Promise.resolve(
          jsonResponse(200, {
            ...PROGRESS,
            completed_lesson_ids: ["l1"],
            completed_lessons: 1,
            progress_percent: 50,
            modules: [{ module_id: "m1", completed_lessons: 1, total_lessons: 2, progress_percent: 50 }],
          }),
        );
      }
      return Promise.resolve(jsonResponse(200, RESOURCE));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPage();

    expect(await screen.findByText("Welcome.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Mark as complete" }));

    await waitFor(() => expect(screen.getByText("Practice time.")).toBeInTheDocument());
    expect(screen.getByText("50% complete")).toBeInTheDocument();
  });

  it("embeds the CV audit widget for a resume_upload lesson instead of a mark-complete button", async () => {
    const resourceWithAudit = {
      ...RESOURCE,
      modules: [
        {
          ...RESOURCE.modules[0],
          lessons: [
            {
              id: "l1",
              module_id: "m1",
              title: "Submit your resume",
              position: 0,
              content_type: "resume_upload",
              content: "",
              created_at: "2026-01-01T00:00:00Z",
            },
          ],
        },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((path: string) => {
        if (path.includes("course-audit-attempts")) {
          return Promise.resolve(jsonResponse(200, { attempts_today: 0, daily_limit: 3, attempts_remaining: 3 }));
        }
        if (path.endsWith("/progress")) return Promise.resolve(jsonResponse(200, PROGRESS));
        return Promise.resolve(jsonResponse(200, resourceWithAudit));
      }),
    );

    renderPage();

    expect(await screen.findByText("CV course audit")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mark as complete" })).not.toBeInTheDocument();
  });
});
