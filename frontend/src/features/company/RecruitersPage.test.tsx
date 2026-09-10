import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { RecruitersPage } from "@/features/company/RecruitersPage";

const RECRUITER = {
  id: "r1",
  company_id: "c1",
  email: "ada@acme.invalid",
  first_name: "Ada",
  last_name: "Lovelace",
  role: "recruiter",
  is_active: true,
  is_verified: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
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
      <RecruitersPage />
    </QueryClientProvider>,
  );
}

describe("RecruitersPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("shows the 403 error state for a non-owner recruiter, not a broken screen", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ error: { code: "forbidden", message: "Only an owner can do that." } }), {
            status: 403,
            headers: { "content-type": "application/json" },
          }),
        ),
      ),
    );

    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("Only an owner can do that.");
  });

  it("updates a recruiter's role via PATCH", async () => {
    const fetchMock = vi.fn((_path: string, init?: RequestInit) => {
      if (init?.method === "PATCH") return Promise.resolve(jsonResponse(200, { ...RECRUITER, role: "admin" }));
      return Promise.resolve(jsonResponse(200, [RECRUITER]));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPage();

    const select = await screen.findByDisplayValue("recruiter");
    await user.selectOptions(select, "admin");

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path, init]) =>
            path === "/api/v1/companies/me/recruiters/r1" && (init as RequestInit | undefined)?.method === "PATCH",
        ),
      ).toBe(true),
    );
  });

  it("invites a new recruiter", async () => {
    const fetchMock = vi.fn((_path: string, init?: RequestInit) => {
      if (init?.method === "POST") return Promise.resolve(jsonResponse(201, { ...RECRUITER, id: "r2" }));
      return Promise.resolve(jsonResponse(200, [RECRUITER]));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPage();
    await screen.findByText("ada@acme.invalid");

    await user.click(screen.getByRole("button", { name: "Invite recruiter" }));
    await user.type(screen.getByLabelText("Email"), "grace@acme.invalid");
    await user.type(screen.getByLabelText("Temporary password"), "password123");
    await user.click(screen.getByRole("button", { name: "Send invite" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path, init]) =>
            path === "/api/v1/companies/me/recruiters" && (init as RequestInit | undefined)?.method === "POST",
        ),
      ).toBe(true),
    );
  });
});
