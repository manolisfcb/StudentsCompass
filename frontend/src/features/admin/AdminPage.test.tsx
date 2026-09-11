import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { AdminPage } from "@/features/admin/AdminPage";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

function renderPage(path = "/admin") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AdminPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AdminPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("renders the four baseline dashboard cards from server state", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(200, {
      total_users: 3,
      total_companies: 1,
      total_communities: 1,
      total_resources: 4,
      total_jobs: 2,
      total_applications: 2,
      total_resumes: 5,
      total_questionnaires: 6,
      recent_users: 0,
    }))));
    renderPage();
    expect(await screen.findByText("Total Users")).toBeInTheDocument();
    expect(screen.getByText("Resources")).toBeInTheDocument();
    expect(screen.getByText("Resumes")).toBeInTheDocument();
    expect(screen.getByText("Questionnaires")).toBeInTheDocument();
    expect(screen.getByText("6")).toBeInTheDocument();
  });

  it("deep-links to users and sends an explicit state instead of a toggle", async () => {
    const fetchMock = vi.fn((...args: [string | URL | Request, RequestInit?]) => {
      const init = args[1];
      if (init?.method === "PATCH") {
        return Promise.resolve(jsonResponse(200, {
          id: "u1", email: "ada@example.invalid", is_active: false, is_superuser: false, is_verified: true,
        }));
      }
      return Promise.resolve(jsonResponse(200, {
        items: [{ id: "u1", email: "ada@example.invalid", first_name: "Ada", last_name: "Lovelace", is_active: true, is_superuser: false, is_verified: true }],
        users: [], page: 1, page_size: 20, total: 1,
      }));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage("/admin?section=users");

    expect(await screen.findByText("ada@example.invalid")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Deactivate" }));

    const patch = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(patch?.[0]).toBe("/api/v1/admin/users/u1");
    expect(JSON.parse(patch?.[1]?.body as string)).toEqual({ is_active: false });
  });

  it("renders a 403 using the API's safe error message", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(403, {
      error: { code: "forbidden", message: "Admin privileges required.", details: null, request_id: "req-53" },
    }))));
    renderPage();
    expect(await screen.findByText("Admin privileges required.")).toBeInTheDocument();
    expect(screen.getByText(/req-53/)).toBeInTheDocument();
  });
});
