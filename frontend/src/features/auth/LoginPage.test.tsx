import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { LoginPage } from "@/features/auth/LoginPage";

function jsonResponse(status: number, body: unknown): Response {
  const hasBody = status !== 204;
  return new Response(hasBody ? JSON.stringify(body ?? {}) : null, {
    status,
    headers: hasBody ? { "content-type": "application/json" } : {},
  });
}

function renderAt(entry: string | { pathname: string; state?: unknown }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<p>student home</p>} />
          <Route path="/company" element={<p>company home</p>} />
          <Route path="/deep-link" element={<p>the deep link</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LoginPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("defaults to the student account type and submits to the student login path", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(204, null)));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderAt("/login");

    await user.type(screen.getByLabelText("Email"), "person@example.invalid");
    await user.type(screen.getByLabelText("Password"), "hunter2");
    await user.click(screen.getByRole("button", { name: "Login" }));

    await waitFor(() => expect(screen.getByText("student home")).toBeInTheDocument());
    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/auth/student/login");
  });

  it("submits to the company login path and lands on the company home", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(204, null)));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderAt("/login");

    await user.click(screen.getByRole("radio", { name: "Company" }));
    await user.type(screen.getByLabelText("Email"), "team@example.invalid");
    await user.type(screen.getByLabelText("Password"), "hunter2");
    await user.click(screen.getByRole("button", { name: "Login" }));

    await waitFor(() => expect(screen.getByText("company home")).toBeInTheDocument());
    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/auth/company/login");
  });

  it("shows a friendly message on bad credentials and does not navigate", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(400, { detail: "LOGIN_BAD_CREDENTIALS" }))));
    const user = userEvent.setup();

    renderAt("/login");

    await user.type(screen.getByLabelText("Email"), "person@example.invalid");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Login" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password.");
    expect(screen.queryByText("student home")).not.toBeInTheDocument();
  });

  it("returns a redirected visitor to the page they were trying to reach", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(204, null))));
    const user = userEvent.setup();

    renderAt({ pathname: "/login", state: { from: { pathname: "/deep-link" } } });

    await user.type(screen.getByLabelText("Email"), "person@example.invalid");
    await user.type(screen.getByLabelText("Password"), "hunter2");
    await user.click(screen.getByRole("button", { name: "Login" }));

    expect(await screen.findByText("the deep link")).toBeInTheDocument();
  });
});
