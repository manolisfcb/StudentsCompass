import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { CareerLabPage } from "@/features/career-lab/CareerLabPage";

const RESUME = {
  id: "r1",
  folder_id: "resumes",
  original_filename: "cv.pdf",
  storage_file_id: "resumes/cv.pdf",
  view_url: "https://storage.example/cv.pdf",
  created_at: "2026-01-01T00:00:00Z",
};

const GAP_ANALYSIS = {
  status: "ok",
  resume_id: "r1",
  target_role: "Data Analyst",
  requirements_source: "job_postings",
  coverage_ratio: 0.5,
  analysis_version: "semantic_gap_v1",
  match_score: 0.6,
  overall_readiness_score: 0.7,
  semantic_score: 0.5,
  context_similarity_score: 0.4,
  context_match_level: "moderate",
  semantic_context_ready: true,
  context_evidence_sources: [],
  exact_match_count: 1,
  semantic_match_count: 0,
  weak_match_count: 0,
  priority_gap_score: 0.3,
  current_skills: [],
  required_skills: [{ skill_id: "s1", normalized_name: "sql", display_name: "SQL", importance_score: 0.9 }],
  matched_required_skills: [],
  semantic_matched_skills: [],
  weak_matched_skills: [],
  missing_skills: [{ skill_id: "s1", normalized_name: "sql", display_name: "SQL" }],
  priority_missing_skills: [{ skill_id: "s1", normalized_name: "sql", display_name: "SQL" }],
  recommended_courses: [],
  gap_insights: [],
  market_signals: { target_role: "Data Analyst", source: "job_postings", synced_job_postings_count: 0, skills: [] },
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/career-lab"]}>
        <CareerLabPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("CareerLabPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("runs a gap analysis: syncs skills, then shows the readiness metrics", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/v1/resumes") return Promise.resolve(jsonResponse(200, [RESUME]));
      if (path === "/api/v1/capstone/analytics/roles") {
        return Promise.resolve(jsonResponse(200, { roles: [{ target_role: "Data Analyst" }] }));
      }
      if (path.includes("/learning-route/runs")) return Promise.resolve(jsonResponse(200, { runs: [] }));
      if (path.includes("/skills/sync") && init?.method === "POST") {
        return Promise.resolve(jsonResponse(200, { resume_id: "r1", extracted_skills: [] }));
      }
      if (path === "/api/v1/capstone/resumes/r1/skills") {
        return Promise.resolve(jsonResponse(200, { resume_id: "r1", skills: [] }));
      }
      if (path.startsWith("/api/v1/capstone/gap-analysis")) {
        return Promise.resolve(jsonResponse(200, GAP_ANALYSIS));
      }
      return Promise.resolve(jsonResponse(200, {}));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPage();

    await screen.findByText("cv.pdf");
    await user.click(screen.getByRole("button", { name: "Analyze gap" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path, init]) =>
            path === "/api/v1/capstone/resumes/r1/skills/sync" && (init as RequestInit | undefined)?.method === "POST",
        ),
      ).toBe(true),
    );

    expect(await screen.findByText("70%")).toBeInTheDocument();
  });

  it("generates a learning route with a fresh Idempotency-Key on optimize and evaluate-baselines", async () => {
    const fetchMock = vi.fn((path: string) => {
      if (path === "/api/v1/resumes") return Promise.resolve(jsonResponse(200, [RESUME]));
      if (path === "/api/v1/capstone/analytics/roles") {
        return Promise.resolve(jsonResponse(200, { roles: [{ target_role: "Data Analyst" }] }));
      }
      if (path.includes("/learning-route/runs")) return Promise.resolve(jsonResponse(200, { runs: [] }));
      if (path === "/api/v1/capstone/resumes/r1/skills") {
        return Promise.resolve(jsonResponse(200, { resume_id: "r1", skills: [] }));
      }
      if (path === "/api/v1/capstone/learning-route/optimize") {
        return Promise.resolve(
          jsonResponse(200, {
            status: "ok",
            optimization_run_id: "run1",
            objective_version: "heuristic_v1",
            target_role: "Data Analyst",
            match_score_before: 0.5,
            projected_match_score_after: 0.8,
            total_cost: 90,
            total_hours: 20,
            selected_courses: [],
            covered_skills: [],
            remaining_gaps: [],
            route_summary: "Optimized route ready.",
          }),
        );
      }
      if (path === "/api/v1/capstone/learning-route/evaluate-baselines") {
        return Promise.resolve(
          jsonResponse(200, {
            status: "ok",
            resume_id: "r1",
            target_role: "Data Analyst",
            match_score_before: 0.5,
            evaluation_version: "phase_7_v1",
            baseline_seed: 42,
            constraints: {},
            methods: [],
            winner_summary: { best_method: "cp_sat_route_v1", summary: "CP-SAT wins." },
          }),
        );
      }
      return Promise.resolve(jsonResponse(200, {}));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPage();

    await screen.findByText("cv.pdf");
    await user.click(screen.getByRole("button", { name: "Generate learning route" }));

    await waitFor(() => expect(screen.getByText("Optimized route ready.")).toBeInTheDocument());

    const optimizeCall = fetchMock.mock.calls.find(
      ([path]) => path === "/api/v1/capstone/learning-route/optimize",
    ) as unknown as [string, RequestInit];
    const evaluateCall = fetchMock.mock.calls.find(
      ([path]) => path === "/api/v1/capstone/learning-route/evaluate-baselines",
    ) as unknown as [string, RequestInit];

    expect((optimizeCall[1].headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
    expect((evaluateCall[1].headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
    expect(await screen.findByText(/CP-SAT wins\./)).toBeInTheDocument();
  });
});
