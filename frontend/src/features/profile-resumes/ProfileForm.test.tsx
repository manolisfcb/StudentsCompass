import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import "@/i18n";
import { ProfileForm } from "@/features/profile-resumes/ProfileForm";
import type { Profile } from "@/features/profile-resumes/api";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body ?? {}), { status, headers: { "content-type": "application/json" } });
}

const PROFILE: Profile = {
  id: "u1" as unknown as Profile["id"],
  email: "ada@example.invalid",
  is_active: true,
  is_superuser: false,
  is_verified: true,
  first_name: "Ada",
  last_name: "Lovelace",
  nickname: null,
  phone: null,
  sex: null,
  age: null,
  address: null,
};

describe("ProfileForm", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("saves an edited field without touching privileged fields like is_active", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { ...PROFILE, nickname: "Ace" })));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });

    render(
      <QueryClientProvider client={client}>
        <ProfileForm profile={PROFILE} />
      </QueryClientProvider>,
    );

    await user.type(screen.getByLabelText("Nickname"), "Ace");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(screen.getByText("Profile updated.")).toBeInTheDocument());

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.nickname).toBe("Ace");
    expect(body).not.toHaveProperty("is_active");
    expect(body).not.toHaveProperty("is_superuser");
    expect(body).not.toHaveProperty("is_verified");
  });

  it("shows the email field as read-only", () => {
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <ProfileForm profile={PROFILE} />
      </QueryClientProvider>,
    );

    expect(screen.getByLabelText("Email")).toBeDisabled();
  });
});
