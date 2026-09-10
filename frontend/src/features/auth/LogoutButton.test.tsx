import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { LogoutButton } from "@/features/auth/LogoutButton";

function jsonResponse(status: number): Response {
  return new Response(null, { status });
}

describe("LogoutButton", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("posts to the given actor's own logout path and returns home", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(204)));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });

    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/company"]}>
          <Routes>
            <Route path="/company" element={<LogoutButton actorKind="company" />} />
            <Route path="/" element={<p>home</p>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Log out" }));

    expect(await screen.findByText("home")).toBeInTheDocument();
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/auth/company/logout");
    expect(init.method).toBe("POST");
  });
});
