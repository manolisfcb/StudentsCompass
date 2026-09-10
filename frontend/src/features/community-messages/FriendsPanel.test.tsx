import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { FriendsPanel } from "@/features/community-messages/FriendsPanel";

const INCOMING = [
  {
    id: "r1",
    status: "pending",
    created_at: "2026-01-01T00:00:00Z",
    sender: { id: "u2", display_name: "Grace Hopper" },
    receiver: { id: "u1", display_name: "Ada Lovelace" },
  },
];

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <FriendsPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("FriendsPanel", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("accepts an incoming request with PATCH and refreshes all three lists", async () => {
    let accepted = false;
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        accepted = true;
        return Promise.resolve(jsonResponse(200, { ...INCOMING[0], status: "accepted" }));
      }
      if (path === "/api/v1/friends/requests/incoming") return Promise.resolve(jsonResponse(200, accepted ? [] : INCOMING));
      if (path === "/api/v1/friends/requests/outgoing") return Promise.resolve(jsonResponse(200, []));
      if (path === "/api/v1/friends")
        return Promise.resolve(
          jsonResponse(200, accepted ? [{ friend: INCOMING[0]!.sender, created_at: "2026-02-01T00:00:00Z" }] : []),
        );
      return Promise.resolve(jsonResponse(200, []));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPanel();

    await screen.findByText("Grace Hopper");
    await user.click(screen.getByRole("button", { name: "Accept" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path, init]) => path === "/api/v1/friend-requests/r1" && (init as RequestInit | undefined)?.method === "PATCH",
        ),
      ).toBe(true),
    );
    await waitFor(() => expect(screen.getByText("No incoming requests.")).toBeInTheDocument());
  });
});
