import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { ApplicantsPage } from "@/features/company/ApplicantsPage";

const APPLICANT = {
  application: {
    id: "a1",
    job_posting_id: "p1",
    job_title: "Frontend Engineer",
    status: "in_review",
    match_strength: "strong_match",
    application_date: "2026-01-01T00:00:00Z",
    notes: null,
    selected_interview_slot: null,
    available_interview_slots: [],
  },
  candidate: {
    id: "u1",
    first_name: "Grace",
    last_name: "Hopper",
    full_name: "Grace Hopper",
    email: "grace@example.invalid",
  },
  resume: {
    id: "r1",
    original_filename: "resume.pdf",
    uploaded_at: "2026-01-01T00:00:00Z",
    preview_url: "https://storage.example/preview",
    download_url: "https://storage.example/download",
  },
  certifications: [],
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <ApplicantsPage />
    </QueryClientProvider>,
  );
}

describe("ApplicantsPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("updates an applicant's pipeline status via PATCH", async () => {
    const fetchMock = vi.fn((_path: string, init?: RequestInit) => {
      if (init?.method === "PATCH") return Promise.resolve(jsonResponse(200, { ...APPLICANT, application: { ...APPLICANT.application, status: "interview" } }));
      return Promise.resolve(jsonResponse(200, [APPLICANT]));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPage();

    const select = await screen.findByDisplayValue("in review");
    await user.selectOptions(select, "interview");

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path, init]) => path === "/api/v1/companies/me/applicants/a1" && (init as RequestInit | undefined)?.method === "PATCH",
        ),
      ).toBe(true),
    );
  });

  it("publishes interview availability slots", async () => {
    const fetchMock = vi.fn((_path: string, init?: RequestInit) => {
      if (init?.method === "POST") return Promise.resolve(jsonResponse(200, APPLICANT));
      return Promise.resolve(jsonResponse(200, [APPLICANT]));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPage();

    await screen.findByText("Grace Hopper");
    await user.click(screen.getByRole("button", { name: "Schedule interview" }));

    await user.type(screen.getByLabelText("Starts at"), "2026-02-01T10:00");
    await user.type(screen.getByLabelText("Ends at"), "2026-02-01T10:30");
    await user.click(screen.getByRole("button", { name: "Publish availability" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path, init]) =>
            path === "/api/v1/companies/me/applicants/a1/interview-availabilities" &&
            (init as RequestInit | undefined)?.method === "POST",
        ),
      ).toBe(true),
    );
  });
});
