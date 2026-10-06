import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { JobTargetDetailPage } from "@/features/career-lab/JobTargetDetailPage";

function component(value: number | null, weight: number, effective: number) {
  return { value, available: value !== null, weight, effective_weight: effective };
}

const ANALYSIS = {
  analysis_version: "job_match_v1",
  computed_at: "2026-10-05T10:00:00Z",
  resume_id: "r1",
  score: 0.59,
  band: "match",
  gate: { value: 1, reason: "No location or workplace preference declared." },
  components: {
    skills: component(0.62, 0.45, 0.5),
    context: component(0.7, 0.25, 0.28),
    title: component(0.5, 0.2, 0.22),
    seniority: component(null, 0.1, 0),
  },
  context: { value: 0.74, level: "moderate", message: "Your CV reads close to this role." },
  seniority: { asked: "senior", cv: "junior", min_years: 6 },
  title: "Data Analyst",
  workplace_type: "remote",
  requirements: { evidence: 0.67, required: 2, preferred: 0, required_covered: 1 },
  strengths: [
    { skill_id: "s1", display_name: "SQL", requirement: "required", match_type: "exact", matched_with: null, similarity: null },
    { skill_id: "s2", display_name: "Tableau", requirement: null, match_type: "semantic", matched_with: "Power BI", similarity: 0.81 },
  ],
  gaps: [
    {
      skill_id: "s4",
      display_name: "Statistics",
      requirement: "preferred",
      kind: "reinforce",
      closest_skill: "Excel",
      similarity: 0.6,
      priority_rank: 2,
      skill_gap_score: 0.4,
      reason: "Nice to have; Excel covers it in part.",
    },
    {
      skill_id: "s3",
      display_name: "Python",
      requirement: "required",
      kind: "gap",
      closest_skill: null,
      similarity: null,
      priority_rank: 1,
      skill_gap_score: 0.9,
      reason: "Required and nothing in your CV covers it.",
    },
  ],
  semantic_matching_ready: true,
  parse_version: "jd_rules_v1",
};

function target(overrides: Record<string, unknown> = {}) {
  return {
    id: "t1",
    resume_id: "r1",
    status: "ready",
    source: "paste",
    title: "Data Analyst",
    company: "Acme",
    location: "Toronto",
    workplace_type: "remote",
    score: 0.59,
    band: "match",
    created_at: "2026-10-05T10:00:00Z",
    updated_at: "2026-10-05T10:00:00Z",
    raw_text: "Data Analyst\nRequirements\n- SQL\n- Python",
    error_message: null,
    analysis: ANALYSIS,
    ...overrides,
  };
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

function renderPage(body: unknown) {
  const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, body)));
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/career-lab/vacancies/t1"]}>
        <Routes>
          <Route path="/career-lab/vacancies/:targetId" element={<JobTargetDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetchMock;
}

describe("JobTargetDetailPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("reopens the stored analysis: score with its band and breakdown", async () => {
    const fetchMock = renderPage(target());

    expect(await screen.findByRole("heading", { name: "Data Analyst" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/career-lab/job-targets/t1", expect.anything());
    expect(screen.getByText("59%")).toBeInTheDocument();
    expect(screen.getByText("Match")).toBeInTheDocument();
    expect(screen.getByText("Remote")).toBeInTheDocument();

    const breakdown = screen.getByRole("region", { name: "Score breakdown" });
    expect(within(breakdown).getByRole("progressbar", { name: "Skills coverage" })).toHaveAttribute("aria-valuenow", "62");
    expect(within(breakdown).getByText("Counts for 50% of the score")).toBeInTheDocument();
  });

  it("shows a component without signal as not available, never as 0", async () => {
    renderPage(target());
    const breakdown = await screen.findByRole("region", { name: "Score breakdown" });
    expect(within(breakdown).getByText("Not available")).toBeInTheDocument();
    expect(within(breakdown).queryByRole("progressbar", { name: "Seniority fit" })).not.toBeInTheDocument();
  });

  it("says when the catalogue read few requirements", async () => {
    renderPage(target());
    expect(await screen.findByText("Few skills recognized")).toBeInTheDocument();
    expect(screen.getByText(/recognized only 2 skills in this posting/)).toBeInTheDocument();
  });

  it("lists strengths and gaps in priority order with their reasons", async () => {
    renderPage(target());
    expect(await screen.findByText("Covered by Power BI in your CV")).toBeInTheDocument();

    const gaps = screen.getAllByRole("listitem").filter((item) => /Priority \d/.test(item.textContent ?? ""));
    expect(gaps.map((item) => within(item).getByText(/Python|Statistics/).textContent)).toEqual([
      expect.stringContaining("Python"),
      expect.stringContaining("Statistics"),
    ]);
    expect(within(gaps[0] as HTMLElement).getByText("Missing")).toBeInTheDocument();
    expect(within(gaps[1] as HTMLElement).getByText("Reinforce")).toBeInTheDocument();
    expect(within(gaps[1] as HTMLElement).getByText("Closest in your CV: Excel")).toBeInTheDocument();
    expect(screen.getByText("Required and nothing in your CV covers it.")).toBeInTheDocument();
    expect(screen.getByText(/asks for senior; your CV reads as junior/)).toBeInTheDocument();
  });

  it("shows a gate that ruled the vacancy out, with its reason", async () => {
    renderPage(
      target({ analysis: { ...ANALYSIS, gate: { value: 0, reason: "The role is on-site in another city." } } }),
    );
    expect(await screen.findByText("A hard requirement does not fit")).toBeInTheDocument();
    expect(screen.getByText("The role is on-site in another city.")).toBeInTheDocument();
  });

  it("explains a failed analysis and keeps the pasted text", async () => {
    renderPage(
      target({
        status: "failed",
        score: null,
        band: null,
        analysis: null,
        error_message: "We could not analyse this job description. Please try again.",
      }),
    );
    expect(await screen.findByText("This analysis failed")).toBeInTheDocument();
    expect(screen.getByText("We could not analyse this job description. Please try again.")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Score breakdown" })).not.toBeInTheDocument();
    expect(screen.getByText("The job description you pasted")).toBeInTheDocument();
  });

  it("does not show a bare number when nothing could be scored", async () => {
    renderPage(target({ score: null, band: null, analysis: { ...ANALYSIS, score: null, band: null } }));
    expect(await screen.findByText("Not scored")).toBeInTheDocument();
    expect(screen.getByText(/no score to show/)).toBeInTheDocument();
  });

  it("offers the study plan only when there are gaps to plan for", async () => {
    renderPage(target());
    expect(await screen.findByRole("button", { name: "Plan my study" })).toBeInTheDocument();
  });

  it("has no study plan for a vacancy without gaps", async () => {
    renderPage(target({ analysis: { ...ANALYSIS, gaps: [] } }));
    expect(await screen.findByText("No gaps among the skills we recognized in this posting.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Plan my study" })).not.toBeInTheDocument();
  });
});
