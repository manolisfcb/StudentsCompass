import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { JobTargetsPage } from "@/features/career-lab/JobTargetsPage";

const RESUME = {
  id: "r1",
  folder_id: "resumes",
  original_filename: "cv.pdf",
  storage_file_id: "resumes/cv.pdf",
  view_url: "https://storage.example/cv.pdf",
  created_at: "2026-01-01T00:00:00Z",
};

const POSTING = `Data Analyst\n\nRequirements\n- SQL\n- Python\n${"We turn data into decisions. ".repeat(10)}`;

function summary(id: string, overrides: Record<string, unknown> = {}) {
  return {
    id,
    resume_id: "r1",
    status: "ready",
    source: "paste",
    title: `Vacancy ${id}`,
    company: null,
    location: null,
    workplace_type: null,
    score: 0.59,
    band: "match",
    created_at: "2026-10-05T10:00:00Z",
    updated_at: "2026-10-05T10:00:00Z",
    ...overrides,
  };
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

function emptyPage() {
  return { items: [], next_cursor: null, has_more: false, limit: 20 };
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/career-lab/vacancies"]}>
        <Routes>
          <Route path="/career-lab/vacancies" element={<JobTargetsPage />} />
          <Route path="/career-lab/vacancies/:targetId" element={<p>analysis screen</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function postCalls(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls
    .map((call) => call as unknown as [string, RequestInit | undefined])
    .filter(([path, init]) => path === "/api/v1/career-lab/job-targets" && init?.method === "POST");
}

describe("JobTargetsPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("sends a student without a CV to their profile", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((path: string) =>
        Promise.resolve(jsonResponse(200, path === "/api/v1/resumes" ? [] : emptyPage())),
      ),
    );
    renderPage();
    const link = await screen.findByRole("link", { name: "Go to profile" });
    expect(link).toHaveAttribute("href", "/profile");
    expect(screen.queryByLabelText("Job description")).not.toBeInTheDocument();
  });

  it("refuses a paste below the backend's minimum without calling it", async () => {
    const fetchMock = vi.fn((path: string) =>
      Promise.resolve(jsonResponse(200, path === "/api/v1/resumes" ? [RESUME] : emptyPage())),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage();

    await user.type(await screen.findByLabelText("Job description"), "Too short");
    await user.click(screen.getByRole("button", { name: "Analyze vacancy" }));

    expect(await screen.findByText(/at least 200 characters/)).toBeInTheDocument();
    expect(postCalls(fetchMock)).toHaveLength(0);
  });

  it("analyses a paste against the chosen CV and opens its analysis", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/v1/resumes") return Promise.resolve(jsonResponse(200, [RESUME]));
      if (path === "/api/v1/career-lab/job-targets" && init?.method === "POST") {
        return Promise.resolve(jsonResponse(201, { ...summary("t9"), raw_text: POSTING, error_message: null }));
      }
      return Promise.resolve(jsonResponse(200, emptyPage()));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage();

    fireEvent.change(await screen.findByLabelText("Job description"), { target: { value: POSTING } });
    fireEvent.click(screen.getByRole("button", { name: "Analyze vacancy" }));

    expect(await screen.findByText("analysis screen")).toBeInTheDocument();
    const [[, init]] = postCalls(fetchMock) as [[string, RequestInit]];
    expect(JSON.parse(init.body as string)).toEqual({ text: POSTING, resume_id: "r1" });
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toMatch(/[0-9a-f-]{36}/);
  });

  it("retries the same paste under the same Idempotency-Key, and a new paste under a new one", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/v1/resumes") return Promise.resolve(jsonResponse(200, [RESUME]));
      if (init?.method === "POST") {
        return Promise.resolve(
          jsonResponse(503, { error: { code: "service_unavailable", message: "Try again.", details: null, request_id: "x" } }),
        );
      }
      return Promise.resolve(jsonResponse(200, emptyPage()));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage();

    const textarea = await screen.findByLabelText("Job description");
    const submit = screen.getByRole("button", { name: "Analyze vacancy" });
    fireEvent.change(textarea, { target: { value: POSTING } });
    fireEvent.click(submit);
    expect(await screen.findByText("Try again.")).toBeInTheDocument();
    fireEvent.click(submit);
    await waitFor(() => expect(postCalls(fetchMock)).toHaveLength(2));
    fireEvent.change(textarea, { target: { value: `${POSTING} edited` } });
    fireEvent.click(submit);
    await waitFor(() => expect(postCalls(fetchMock)).toHaveLength(3));

    const keys = postCalls(fetchMock).map(([, init]) => (init?.headers as Record<string, string>)["Idempotency-Key"]);
    expect(keys[0]).toBe(keys[1]);
    expect(keys[2]).not.toBe(keys[0]);
  });

  it("lists analysed vacancies with their band and walks the cursor", async () => {
    const fetchMock = vi.fn((path: string) => {
      if (path === "/api/v1/resumes") return Promise.resolve(jsonResponse(200, [RESUME]));
      if (path === "/api/v1/career-lab/job-targets") {
        return Promise.resolve(
          jsonResponse(200, {
            items: [summary("t1"), summary("t2", { status: "failed", score: null, band: null })],
            next_cursor: "c1",
            has_more: true,
            limit: 2,
          }),
        );
      }
      if (path === "/api/v1/career-lab/job-targets?before=c1") {
        return Promise.resolve(
          jsonResponse(200, { items: [summary("t3", { band: "strong_match", score: 0.81 })], next_cursor: null, has_more: false, limit: 2 }),
        );
      }
      return Promise.resolve(jsonResponse(404, {}));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage();

    const first = await screen.findByRole("link", { name: /Vacancy t1/ });
    expect(first).toHaveAttribute("href", "/career-lab/vacancies/t1");
    expect(first).toHaveTextContent("59% · Match");
    expect(screen.getByRole("link", { name: /Vacancy t2/ })).toHaveTextContent("Analysis failed");

    await user.click(screen.getByRole("button", { name: "Load more" }));
    expect(await screen.findByRole("link", { name: /Vacancy t3/ })).toHaveTextContent("81% · Strong match");
    expect(screen.getByRole("link", { name: /Vacancy t1/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
  });
});
