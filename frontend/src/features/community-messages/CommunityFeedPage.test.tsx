import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { CommunityFeedPage } from "@/features/community-messages/CommunityFeedPage";

const COMMUNITY = {
  id: "c1",
  name: "Frontend Builders",
  description: "For people shipping UI.",
  icon: "🛠️",
  member_count: 12,
  created_at: "2026-01-01T00:00:00Z",
  created_by: "someone-else",
};

function jsonResponse(status: number, body: unknown): Response {
  const hasBody = status !== 204;
  return new Response(hasBody ? JSON.stringify(body ?? {}) : null, {
    status,
    headers: hasBody ? { "content-type": "application/json" } : {},
  });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/community/c1"]}>
        <Routes>
          <Route path="/community/:communityId" element={<CommunityFeedPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("CommunityFeedPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("joins the community optimistically, then reconciles member_count from the server", async () => {
    let joined = false;
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (init?.method === "PUT") {
        joined = true;
        return Promise.resolve(
          jsonResponse(200, { id: "m1", community_id: "c1", user_id: "u1", joined_at: "2026-02-01T00:00:00Z" }),
        );
      }
      if (path.endsWith("/membership")) return Promise.resolve(jsonResponse(200, { is_member: joined }));
      if (path.endsWith("/posts/enriched")) return Promise.resolve(jsonResponse(200, []));
      return Promise.resolve(jsonResponse(200, { ...COMMUNITY, member_count: joined ? 13 : 12 }));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPage();

    await screen.findByText("Frontend Builders");
    expect(screen.getByText("12 members")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Join" }));

    // Optimistic: the Leave button appears immediately, before the server settles.
    expect(await screen.findByRole("button", { name: "Leave" })).toBeInTheDocument();

    // Reconciled: the authoritative member_count from the follow-up GET.
    await waitFor(() => expect(screen.getByText("13 members")).toBeInTheDocument());

    expect(
      fetchMock.mock.calls.some(([path, init]) => path === "/api/v1/communities/c1/members/me" && init?.method === "PUT"),
    ).toBe(true);
  });

  it("shows the backend's own refusal when a creator tries to leave, instead of hiding the button", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (init?.method === "DELETE") {
        return Promise.resolve(
          new Response(
            JSON.stringify({ error: { code: "forbidden", message: "El creador no puede abandonar la comunidad" } }),
            { status: 403, headers: { "content-type": "application/json" } },
          ),
        );
      }
      if (path.endsWith("/membership")) return Promise.resolve(jsonResponse(200, { is_member: true }));
      if (path.endsWith("/posts/enriched")) return Promise.resolve(jsonResponse(200, []));
      return Promise.resolve(jsonResponse(200, COMMUNITY));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPage();

    await user.click(await screen.findByRole("button", { name: "Leave" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("El creador no puede abandonar la comunidad");
    vi.restoreAllMocks();
  });
});
