import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { JobTargetRoadmapPanel } from "@/features/career-lab/JobTargetRoadmapPanel";

function gap(name: string, rank: number, reason?: "no_course" | "out_of_reach") {
  return {
    skill_id: `s-${name}`,
    display_name: name,
    requirement: "required",
    kind: "gap",
    priority_rank: rank,
    ...(reason ? { reason } : {}),
  };
}

function step(order: number, title: string, start: number, end: number, skill: string) {
  return {
    order,
    start_day: start,
    end_day: end,
    course_id: `c${order}`,
    title,
    provider: "Coursera",
    url: `https://courses.example/${order}`,
    cost: 0,
    currency: "CAD",
    duration_hours: 8,
    difficulty: "beginner",
    rating: 4.5,
    skills: [{ skill_id: `s-${skill}`, display_name: skill }],
  };
}

function roadmap(overrides: Record<string, unknown> = {}) {
  return {
    target_id: "t1",
    objective_version: "cp_sat_route_v1",
    solver_status: "OPTIMAL",
    constraints: { days_until_interview: 14, hours_per_day: 2, available_hours: 28, budget: null, max_courses: null },
    total_cost: 0,
    total_hours: 16,
    gap_coverage: 0.6,
    steps: [step(1, "Data Cleaning with Pandas", 1, 4, "Data Cleaning"), step(2, "Power BI Data Analyst", 5, 8, "Power BI")],
    covered_gaps: [gap("Data Cleaning", 1), gap("Power BI", 2)],
    uncovered_gaps: [gap("Statistics", 4, "out_of_reach"), gap("Sales", 3, "no_course")],
    ...overrides,
  };
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

function renderPanel(answer: () => Response) {
  const fetchMock = vi.fn(() => Promise.resolve(answer()));
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <JobTargetRoadmapPanel targetId="t1" />
    </QueryClientProvider>,
  );
  return fetchMock;
}

function calls(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls.map((call) => call as unknown as [string, RequestInit]);
}

describe("JobTargetRoadmapPanel", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("plans the days left: steps with their day windows, then the interview", async () => {
    const fetchMock = renderPanel(() => jsonResponse(200, roadmap()));

    fireEvent.change(screen.getByLabelText("Hours a day"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Plan my study" }));

    const first = (await screen.findByRole("link", { name: "Data Cleaning with Pandas" })).closest("li") as HTMLElement;
    expect(within(first).getByText("Days 1–4")).toBeInTheDocument();
    expect(within(first).getByText("Data Cleaning")).toBeInTheDocument();
    expect(screen.getByText("Interview").closest("li")).toHaveTextContent("Day 14");
    expect(screen.getByText("16 of 28 h")).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();

    const [[path, init]] = calls(fetchMock) as [[string, RequestInit]];
    expect(path).toBe("/api/v1/career-lab/job-targets/t1/roadmap");
    expect(JSON.parse(init.body as string)).toEqual({ days_until_interview: 14, hours_per_day: 2, budget: null });
  });

  it("separates what did not fit from what no course teaches", async () => {
    renderPanel(() => jsonResponse(200, roadmap()));
    fireEvent.click(screen.getByRole("button", { name: "Plan my study" }));

    const outOfReach = (await screen.findByText("Did not fit this time")).parentElement as HTMLElement;
    expect(within(outOfReach).getByText("Statistics")).toBeInTheDocument();
    const noCourse = screen.getByText("Not in our course catalogue yet").parentElement as HTMLElement;
    expect(within(noCourse).getByText("Sales")).toBeInTheDocument();
  });

  it("says more time would help only when time is what kept courses out", async () => {
    renderPanel(() => jsonResponse(200, roadmap({ steps: [], gap_coverage: 0, uncovered_gaps: [gap("Sales", 1, "no_course")] })));
    fireEvent.click(screen.getByRole("button", { name: "Plan my study" }));
    expect(await screen.findByText("Not in our course catalogue yet")).toBeInTheDocument();
    expect(screen.queryByText(/No course fits in that time/)).not.toBeInTheDocument();
  });

  it("warns that nothing fits when every course is out of reach", async () => {
    renderPanel(() =>
      jsonResponse(200, roadmap({ steps: [], gap_coverage: 0, uncovered_gaps: [gap("Statistics", 1, "out_of_reach")] })),
    );
    fireEvent.click(screen.getByRole("button", { name: "Plan my study" }));
    expect(await screen.findByText(/No course fits in that time/)).toBeInTheDocument();
  });

  it("refuses days outside the backend's bounds without calling it", async () => {
    const fetchMock = renderPanel(() => jsonResponse(200, roadmap()));
    fireEvent.change(screen.getByLabelText("Days until the interview"), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: "Plan my study" }));
    expect(await screen.findByText("Enter whole days, from 1 to 365.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("retries under the same Idempotency-Key and changes it when an input changes", async () => {
    const fetchMock = renderPanel(() =>
      jsonResponse(503, { error: { code: "service_unavailable", message: "Busy.", details: null, request_id: "x" } }),
    );
    const submit = screen.getByRole("button", { name: "Plan my study" });
    fireEvent.click(submit);
    expect(await screen.findByText("Busy.")).toBeInTheDocument();
    fireEvent.click(submit);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    fireEvent.change(screen.getByLabelText("Days until the interview"), { target: { value: "7" } });
    fireEvent.click(submit);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));

    const keys = calls(fetchMock).map(([, init]) => (init.headers as Record<string, string>)["Idempotency-Key"]);
    expect(keys[0]).toBe(keys[1]);
    expect(keys[2]).not.toBe(keys[0]);
  });
});
