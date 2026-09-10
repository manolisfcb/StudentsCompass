import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { CareerSummary } from "@/features/profile-resumes/CareerSummary";

function jsonResponse(status: number, body: unknown): Response {
  const hasBody = status !== 204;
  return new Response(hasBody ? JSON.stringify(body ?? {}) : null, {
    status,
    headers: hasBody ? { "content-type": "application/json" } : {},
  });
}

function renderSummary() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <CareerSummary />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("CareerSummary", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("offers the questionnaire when the 404 answer means 'not taken yet'", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(404, { detail: "not found" }))));

    renderSummary();

    expect(await screen.findByText("You have not completed the career questionnaire yet.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Take the questionnaire" })).toHaveAttribute("href", "/questionnaire");
  });

  it("shows the top career matches when a questionnaire profile exists", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(200, {
            user_id: "u1",
            user_name: "Ada",
            user_email: "ada@example.invalid",
            created_at: "2026-01-01T00:00:00Z",
            version: "v1",
            answers: [],
            results: [
              { career: "Software Engineer", score: 9 },
              { career: "Data Analyst", score: 7 },
              { career: "Product Manager", score: 6 },
            ],
            questionnaire: null,
            questionnaire_definition_available: false,
          }),
        ),
      ),
    );

    renderSummary();

    expect(await screen.findByText("Software Engineer")).toBeInTheDocument();
    expect(screen.getByText("Data Analyst")).toBeInTheDocument();
    expect(screen.getByText("Product Manager")).toBeInTheDocument();
  });
});
