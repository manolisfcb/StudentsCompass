import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { ResourcesListPage } from "@/features/resources-roadmaps/ResourcesListPage";

const RESOURCES = [
  {
    id: "r1",
    title: "Resume Basics",
    description: "Write a strong resume.",
    category: "Resume",
    is_published: true,
    is_locked: false,
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "r2",
    title: "Advanced Interviewing",
    description: "Nail the interview.",
    category: "Interview",
    is_published: true,
    is_locked: true,
    created_at: "2026-01-01T00:00:00Z",
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
        <ResourcesListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ResourcesListPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("filters by search text", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(200, RESOURCES))));
    const user = userEvent.setup();

    renderPage();
    await screen.findByText("Resume Basics");

    await user.type(screen.getByLabelText("Search resources"), "interview");

    expect(screen.queryByText("Resume Basics")).not.toBeInTheDocument();
    expect(screen.getByText("Advanced Interviewing")).toBeInTheDocument();
  });

  it("does not link a locked resource", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(200, RESOURCES))));

    renderPage();

    const lockedCard = await screen.findByText("Advanced Interviewing");
    expect(lockedCard.closest("a")).toBeNull();
    const unlockedCard = screen.getByText("Resume Basics");
    expect(unlockedCard.closest("a")).toHaveAttribute("href", "/resources/r1");
  });
});
