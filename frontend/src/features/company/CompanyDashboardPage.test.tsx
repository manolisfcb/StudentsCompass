import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { CompanyDashboardPage } from "@/features/company/CompanyDashboardPage";

const DASHBOARD = {
  company: { id: "c1", company_name: "Acme Inc.", industry: "Software", location: "Toronto" },
  stats: { active_job_postings: 3, total_applications: 12, scheduled_interviews: 2, shortlisted: 4 },
  recent_job_postings: [
    {
      id: "p1",
      title: "Frontend Engineer",
      location: "Remote",
      job_type: "full_time",
      is_active: true,
      status: "active",
      status_label: "Active",
      created_at: "2026-01-01T00:00:00Z",
      application_count: 5,
    },
  ],
  current_recruiter: { id: "r1", email: "ada@acme.invalid", first_name: "Ada", last_name: "Lovelace", role: "owner", is_active: true },
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

describe("CompanyDashboardPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("renders the numbers and postings the backend sent, unchanged", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(200, DASHBOARD))));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });

    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <CompanyDashboardPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Acme Inc.")).toBeInTheDocument();
    expect(screen.getByText("Signed in as Ada Lovelace (owner)")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("Frontend Engineer")).toBeInTheDocument();
    expect(screen.getByText("5 applicants")).toBeInTheDocument();
  });
});
