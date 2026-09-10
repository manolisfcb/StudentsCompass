import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { MessagesPage } from "@/features/community-messages/MessagesPage";

const CONVERSATION = {
  id: "conv1",
  kind: "direct",
  other_user: { id: "u2", display_name: "Grace Hopper" },
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  last_message_preview: "Latest reply",
  unread_count: 0,
};

const RECENT_PAGE = {
  items: [
    { id: "m2", conversation_id: "conv1", sender_id: "u2", sender_display_name: "Grace Hopper", content: "Latest reply", created_at: "2026-01-02T00:00:00Z", is_mine: false },
  ],
  next_cursor: "cursor-older",
  has_more: true,
  limit: 20,
};

const OLDER_PAGE = {
  items: [
    { id: "m1", conversation_id: "conv1", sender_id: "u1", sender_display_name: "Ada Lovelace", content: "Hi there", created_at: "2026-01-01T00:00:00Z", is_mine: true },
  ],
  next_cursor: null,
  has_more: false,
  limit: 20,
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/messages/conv1"]}>
        <Routes>
          <Route path="/messages/:conversationId" element={<MessagesPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("MessagesPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("loads the most recent page, then loads an older page and orders messages oldest-first", async () => {
    const fetchMock = vi.fn((path: string) => {
      if (path === "/api/v1/conversations") return Promise.resolve(jsonResponse(200, [CONVERSATION]));
      if (path.includes("before=cursor-older")) return Promise.resolve(jsonResponse(200, OLDER_PAGE));
      if (path.includes("/messages/page")) return Promise.resolve(jsonResponse(200, RECENT_PAGE));
      if (path.includes("/read")) return Promise.resolve(new Response(JSON.stringify({}), { status: 200, headers: { "content-type": "application/json" } }));
      return Promise.resolve(jsonResponse(200, {}));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPage();

    expect(await screen.findByText("Latest reply")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Load older messages" }));

    await waitFor(() => expect(screen.getByText("Hi there")).toBeInTheDocument());

    // Excludes the sidebar's conversation preview, which repeats the same
    // text inside an `<a>`; only the message bubbles are plain `<div>`s.
    const messages = screen.getAllByText(/Latest reply|Hi there/).filter((el) => !el.closest("a"));
    expect(messages.map((el) => el.textContent)).toEqual(["Hi there", "Latest reply"]);
  });

  it("sends a message and clears the composer", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/v1/conversations") return Promise.resolve(jsonResponse(200, [CONVERSATION]));
      if (init?.method === "POST" && path.endsWith("/messages")) {
        return Promise.resolve(
          jsonResponse(201, {
            id: "m3",
            conversation_id: "conv1",
            sender_id: "u1",
            sender_display_name: "Ada Lovelace",
            content: "New message",
            created_at: "2026-01-03T00:00:00Z",
            is_mine: true,
          }),
        );
      }
      if (path.includes("/messages/page")) return Promise.resolve(jsonResponse(200, RECENT_PAGE));
      if (path.includes("/read")) return Promise.resolve(jsonResponse(200, {}));
      return Promise.resolve(jsonResponse(200, {}));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPage();
    await screen.findByText("Latest reply");

    const input = screen.getByPlaceholderText("Write a message…");
    await user.type(input, "New message");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path, init]) => path === "/api/v1/conversations/conv1/messages" && (init as RequestInit | undefined)?.method === "POST",
        ),
      ).toBe(true),
    );
    expect(input).toHaveValue("");
  });
});
