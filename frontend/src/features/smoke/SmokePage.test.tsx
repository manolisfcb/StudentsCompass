import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppProviders } from "@/app/providers";
import { createQueryClient } from "@/app/queryClient";
import { SmokePage } from "@/features/smoke/SmokePage";

function jsonResponse(status: number): Response {
  return new Response(status === 200 ? "{}" : '{"detail":"Unauthorized"}', {
    status,
    headers: { "content-type": "application/json" },
  });
}

function renderPage() {
  return render(
    <AppProviders client={createQueryClient()}>
      <SmokePage />
    </AppProviders>,
  );
}

describe("SmokePage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        return Promise.resolve(jsonResponse(path === "/api/v1/users/me" ? 401 : 404));
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reports the status of every probe", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("401")).toBeInTheDocument();
    });
    expect(screen.getAllByText("404")).toHaveLength(2);
  });

  it("asks for every probe with a relative path, so the browser stays on one origin", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("401")).toBeInTheDocument();
    });

    const calls = vi.mocked(fetch).mock.calls.map(([input]) => String(input));
    expect(calls).toEqual(["/api/v1/users/me", "/healthz", "/readyz"]);
    for (const call of calls) {
      expect(call.startsWith("/")).toBe(true);
    }
  });

  it("sends session cookies", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("401")).toBeInTheDocument();
    });

    for (const [, init] of vi.mocked(fetch).mock.calls) {
      expect(init?.credentials).toBe("same-origin");
    }
  });

  it("re-runs the probes on demand", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("401")).toBeInTheDocument();
    });
    const before = vi.mocked(fetch).mock.calls.length;

    await userEvent.click(screen.getByRole("button", { name: /run the probes/i }));

    await waitFor(() => {
      expect(vi.mocked(fetch).mock.calls.length).toBeGreaterThan(before);
    });
  });
});
