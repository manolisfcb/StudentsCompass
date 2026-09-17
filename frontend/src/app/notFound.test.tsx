import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import { routes } from "@/app/router";

/**
 * What an unknown URL renders (TASK-058 pre-flight, runbook §4 B1).
 *
 * The catch-all used to redirect to `/__smoke`, the proxy-diagnostics screen.
 * Nothing caught it because nothing asserted on it: the route table was only
 * ever exercised through the routes that exist. These tests go through the
 * real table so a future edit that reintroduces a redirect has to fail here.
 */
function renderAt(path: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("unmatched routes", () => {
  beforeEach(() => {
    // The public shell reads the session; an unauthenticated 401 is the state
    // a crawler or a stale bookmark arrives in, and the one that matters here.
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Unauthorized" }), {
        status: 401,
        headers: { "content-type": "application/json" },
      }),
    );
  });

  it("renders the not-found screen instead of redirecting to the smoke page", async () => {
    renderAt("/definitely-not-a-route");

    expect(await screen.findByRole("heading", { level: 1, name: "We couldn't find that page" })).toBeInTheDocument();
    // The specific regression: `/__smoke` is a developer tool and must never be
    // what a person lands on by mistake.
    expect(screen.queryByText("smoke.title")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /same-origin/i })).not.toBeInTheDocument();
  });

  it("tells a crawler not to index the 200 it just received", async () => {
    renderAt("/an-old-retired-url");

    await screen.findByRole("heading", { level: 1, name: "We couldn't find that page" });
    // Nginx has already answered 200 with the entry document by the time the
    // router knows this route does not exist, so `noindex` is the only signal
    // left that this is not a page. Runbook §9.
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute("content", "noindex");
  });

  it("echoes the path that failed, so an old bookmark is reportable", async () => {
    renderAt("/user-profile-typo");

    expect(await screen.findByText("/user-profile-typo")).toBeInTheDocument();
  });

  it("still resolves the routes that do exist", async () => {
    renderAt("/about");

    expect(await screen.findByRole("heading", { level: 1, name: /.+/ })).toBeInTheDocument();
    expect(screen.queryByText("We couldn't find that page")).not.toBeInTheDocument();
  });
});
