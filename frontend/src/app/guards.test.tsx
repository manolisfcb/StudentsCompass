import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RequireActor, RequireAnonymous } from "@/app/guards";
import type { Session } from "@/api/session";
import "@/i18n";

function sessionFor(actorType: "student" | "recruiter"): Session {
  const actor = {
    id: "00000000-0000-0000-0000-000000000001",
    actor_type: actorType,
    email: "person@example.invalid",
    display_name: null,
    is_active: true,
    is_verified: true,
  };
  return { actor, actors: [actor], csrf_token: "t" } as unknown as Session;
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function renderAt(path: string, element: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={path} element={element} />
          <Route path="/login" element={<p>sign in</p>} />
          <Route path="/dashboard" element={<p>student home</p>} />
          <Route path="/company" element={<p>company home</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RequireActor", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders the route for an actor of an allowed type", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(200, sessionFor("student")))));

    renderAt("/protected", <RequireActor allow={["student"]}><p>secret</p></RequireActor>);

    expect(await screen.findByText("secret")).toBeInTheDocument();
  });

  it("sends an anonymous visitor to sign in", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(401, null))));

    renderAt("/protected", <RequireActor allow={["student"]}><p>secret</p></RequireActor>);

    expect(await screen.findByText("sign in")).toBeInTheDocument();
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });

  it("sends a signed-in actor of the wrong type to their own home, not to sign in", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(200, sessionFor("recruiter")))));

    renderAt("/protected", <RequireActor allow={["student"]}><p>secret</p></RequireActor>);

    expect(await screen.findByText("company home")).toBeInTheDocument();
  });

  it("admits a person holding both identities to either surface", async () => {
    const student = sessionFor("student");
    const recruiter = sessionFor("recruiter");
    const both = {
      ...student,
      actors: [student.actor, recruiter.actor],
    } as unknown as Session;
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(200, both))));

    renderAt("/protected", <RequireActor allow={["recruiter"]}><p>secret</p></RequireActor>);

    expect(await screen.findByText("secret")).toBeInTheDocument();
  });

  it("shows the error state, not the route, when the session cannot be read", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(500, { detail: "boom" }))));

    renderAt("/protected", <RequireActor allow={["student"]}><p>secret</p></RequireActor>);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });
});

describe("RequireAnonymous", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders for a visitor with no session", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(401, null))));

    renderAt("/login-page", <RequireAnonymous><p>sign-in form</p></RequireAnonymous>);

    expect(await screen.findByText("sign-in form")).toBeInTheDocument();
  });

  it("bounces a signed-in student to their home", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(200, sessionFor("student")))));

    renderAt("/login-page", <RequireAnonymous><p>sign-in form</p></RequireAnonymous>);

    expect(await screen.findByText("student home")).toBeInTheDocument();
  });
});
