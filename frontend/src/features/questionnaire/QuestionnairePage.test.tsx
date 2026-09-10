import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { QuestionnairePage } from "@/features/questionnaire/QuestionnairePage";

const QUESTIONNAIRE = {
  version: "v1",
  title: "Career fit",
  questions: [
    {
      id: "q1",
      title: "Do you enjoy building things?",
      kind: "single",
      options: [
        { id: "yes", label: "Yes" },
        { id: "no", label: "No" },
      ],
    },
    {
      id: "q2",
      title: "Do you enjoy helping people?",
      kind: "single",
      options: [
        { id: "yes", label: "Yes" },
        { id: "no", label: "No" },
      ],
    },
  ],
};

const RESULT = {
  id: "r1",
  version: "v1",
  top_careers: [
    { career: "Software Engineer", score: 9 },
    { career: "Product Manager", score: 7 },
  ],
  created_at: "2026-01-01T00:00:00Z",
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/questionnaire"]}>
        <Routes>
          <Route path="/questionnaire" element={<QuestionnairePage />} />
          <Route path="/dashboard" element={<p>dashboard</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("QuestionnairePage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("steps through the questions and shows the results the backend scored", async () => {
    const fetchMock = vi.fn((_path: string, init?: RequestInit) => {
      if (init?.method === "POST") return Promise.resolve(jsonResponse(200, RESULT));
      return Promise.resolve(jsonResponse(200, QUESTIONNAIRE));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPage();

    expect(await screen.findByText("Do you enjoy building things?")).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "Yes" }));
    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(await screen.findByText("Do you enjoy helping people?")).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "No" }));
    await user.click(screen.getByRole("button", { name: "Submit" }));

    expect(await screen.findByText("Software Engineer")).toBeInTheDocument();
    expect(screen.getByText("Product Manager")).toBeInTheDocument();

    const [, submitInit] = fetchMock.mock.calls.find(([, init]) => init?.method === "POST") as unknown as [
      string,
      RequestInit,
    ];
    expect(JSON.parse(submitInit.body as string)).toEqual({
      answers: [
        { question_id: "q1", option_id: "yes" },
        { question_id: "q2", option_id: "no" },
      ],
    });
  });

  it("lets a person retake the questionnaire after seeing results", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((_path: string, init?: RequestInit) =>
        Promise.resolve(jsonResponse(200, init?.method === "POST" ? RESULT : QUESTIONNAIRE)),
      ),
    );
    const user = userEvent.setup();

    renderPage();

    await user.click(await screen.findByRole("radio", { name: "Yes" }));
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(await screen.findByRole("radio", { name: "No" }));
    await user.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => expect(screen.getByText("Software Engineer")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Retake" }));

    expect(await screen.findByText("Do you enjoy building things?")).toBeInTheDocument();
  });
});
