import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { RegisterPage } from "@/features/auth/RegisterPage";

function jsonResponse(status: number, body: unknown): Response {
  const hasBody = status !== 204;
  return new Response(hasBody ? JSON.stringify(body ?? {}) : null, {
    status,
    headers: hasBody ? { "content-type": "application/json" } : {},
  });
}

function renderRegisterPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/register"]}>
        <Routes>
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/login" element={<p>sign in</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RegisterPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("rejects a submission whose passwords do not match, without calling the API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderRegisterPage();

    await user.type(screen.getByLabelText("First Name"), "Ada");
    await user.type(screen.getByLabelText("Last Name"), "Lovelace");
    await user.type(screen.getByLabelText("Nickname"), "ada");
    await user.type(screen.getByLabelText("Email"), "ada@example.invalid");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.type(screen.getByLabelText("Confirm Password"), "password124");
    await user.click(screen.getByRole("button", { name: "Create student account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Passwords do not match.");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects a password under 8 characters, without calling the API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderRegisterPage();

    await user.type(screen.getByLabelText("First Name"), "Ada");
    await user.type(screen.getByLabelText("Last Name"), "Lovelace");
    await user.type(screen.getByLabelText("Nickname"), "ada");
    await user.type(screen.getByLabelText("Email"), "ada@example.invalid");
    await user.type(screen.getByLabelText("Password"), "short");
    await user.type(screen.getByLabelText("Confirm Password"), "short");
    await user.click(screen.getByRole("button", { name: "Create student account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Password must be at least 8 characters long.",
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("registers a student account and shows the success message", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(201, { id: "1", email: "ada@example.invalid" })));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderRegisterPage();

    await user.type(screen.getByLabelText("First Name"), "Ada");
    await user.type(screen.getByLabelText("Last Name"), "Lovelace");
    await user.type(screen.getByLabelText("Nickname"), "ada");
    await user.type(screen.getByLabelText("Email"), "ada@example.invalid");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.type(screen.getByLabelText("Confirm Password"), "password123");
    await user.click(screen.getByRole("button", { name: "Create student account" }));

    expect(await screen.findByText(/Student account created successfully/)).toBeInTheDocument();
    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/auth/register");
  });

  it("switches to the company form and registers a company account", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(201, { id: "1" })));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderRegisterPage();

    await user.click(screen.getByRole("radio", { name: "Company" }));
    await user.type(screen.getByLabelText("Company Name"), "Acme Inc.");
    await user.type(screen.getByLabelText("Email"), "team@example.invalid");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.type(screen.getByLabelText("Confirm Password"), "password123");
    await user.click(screen.getByRole("button", { name: "Create company account" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/auth/company/register");
  });
});
