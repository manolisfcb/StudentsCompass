import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { ResumeList } from "@/features/profile-resumes/ResumeList";

function jsonResponse(status: number, body: unknown): Response {
  const hasBody = status !== 204;
  return new Response(hasBody ? JSON.stringify(body ?? {}) : null, {
    status,
    headers: hasBody ? { "content-type": "application/json" } : {},
  });
}

function renderList() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <ResumeList />
    </QueryClientProvider>,
  );
}

describe("ResumeList", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("shows an empty state with no resumes", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(200, []))));

    renderList();

    expect(await screen.findByText("You have not uploaded a CV yet.")).toBeInTheDocument();
  });

  it("renders the filename as text, never as markup (F-03)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(200, [
            {
              id: "r1",
              user_id: "u1",
              view_url: "https://storage.example/resume.pdf",
              original_filename: "<img src=x onerror=alert(1)>.pdf",
              storage_file_id: "s1",
              folder_id: "f1",
            },
          ]),
        ),
      ),
    );

    renderList();

    const cell = await screen.findByText("<img src=x onerror=alert(1)>.pdf");
    expect(cell.tagName).not.toBe("IMG");
    expect(document.querySelector("img[onerror]")).toBeNull();
  });

  it("uploads a chosen file and refreshes the list", async () => {
    const fetchMock = vi.fn((_path: string, init?: RequestInit) => {
      if (init?.method === "POST") return Promise.resolve(jsonResponse(200, { file_url: "u", resume_id: "r1" }));
      const body = (fetchMock.mock.calls.some(([, i]) => i?.method === "POST"))
        ? [
            {
              id: "r1",
              user_id: "u1",
              view_url: "https://storage.example/resume.pdf",
              original_filename: "resume.pdf",
              storage_file_id: "s1",
              folder_id: "f1",
            },
          ]
        : [];
      return Promise.resolve(jsonResponse(200, body));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderList();
    await screen.findByText("You have not uploaded a CV yet.");

    const file = new File(["%PDF-1.4"], "resume.pdf", { type: "application/pdf" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, file);

    await waitFor(() => expect(screen.getByText("resume.pdf")).toBeInTheDocument());
  });

  it("deletes a resume", async () => {
    let deleted = false;
    vi.stubGlobal(
      "fetch",
      vi.fn((_path: string, init?: RequestInit) => {
        if (init?.method === "DELETE") {
          deleted = true;
          return Promise.resolve(jsonResponse(200, { status: "deleted" }));
        }
        const rows = deleted
          ? []
          : [
              {
                id: "r1",
                user_id: "u1",
                view_url: "https://storage.example/resume.pdf",
                original_filename: "resume.pdf",
                storage_file_id: "s1",
                folder_id: "f1",
              },
            ];
        return Promise.resolve(jsonResponse(200, rows));
      }),
    );
    const user = userEvent.setup();

    renderList();
    await screen.findByText("resume.pdf");

    await user.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(screen.getByText("You have not uploaded a CV yet.")).toBeInTheDocument());
  });
});
