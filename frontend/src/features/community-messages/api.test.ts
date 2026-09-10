import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSessionRefreshState } from "@/api/client";
import {
  acceptFriendRequest,
  fetchCommunities,
  fetchMessagePage,
  joinCommunity,
  leaveCommunity,
  sendMessage,
  startDirectConversation,
} from "@/features/community-messages/api";

function jsonResponse(status: number, body: unknown): Response {
  const hasBody = status !== 204;
  return new Response(hasBody ? JSON.stringify(body ?? {}) : null, {
    status,
    headers: hasBody ? { "content-type": "application/json" } : {},
  });
}

describe("community-messages api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetSessionRefreshState();
  });

  it("joins a community with PUT on the renamed idempotent path", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { id: "m1", community_id: "c1", user_id: "u1", joined_at: "2026-01-01T00:00:00Z" })));
    vi.stubGlobal("fetch", fetchMock);
    await joinCommunity("c1");
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/communities/c1/members/me");
    expect(init.method).toBe("PUT");
  });

  it("leaves a community with DELETE on the renamed idempotent path", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(204, null)));
    vi.stubGlobal("fetch", fetchMock);
    await leaveCommunity("c1");
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/communities/c1/members/me");
    expect(init.method).toBe("DELETE");
  });

  it("lists communities, optionally filtered by tags", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, [])));
    vi.stubGlobal("fetch", fetchMock);
    await fetchCommunities(["react", "career"]);
    const [path] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/communities?tags=react%2Ccareer");
  });

  it("accepts a friend request with PATCH on the renamed path, sending {status: accepted}", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        jsonResponse(200, {
          id: "r1",
          status: "accepted",
          created_at: "2026-01-01T00:00:00Z",
          sender: { id: "u1", display_name: "Ada" },
          receiver: { id: "u2", display_name: "Grace" },
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    await acceptFriendRequest("r1");
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/friend-requests/r1");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ status: "accepted" });
  });

  it("starts a direct conversation with a friend", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(201, { id: "conv1" })));
    vi.stubGlobal("fetch", fetchMock);
    await startDirectConversation("u2");
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/conversations/direct");
    expect(JSON.parse(init.body as string)).toEqual({ friend_id: "u2" });
  });

  it("fetches a cursor page of messages, with and without a cursor", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { items: [], has_more: false, limit: 20 })));
    vi.stubGlobal("fetch", fetchMock);
    await fetchMessagePage("conv1", null);
    await fetchMessagePage("conv1", "cursor-1");
    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    expect(calls.map(([path]) => path)).toEqual([
      "/api/v1/conversations/conv1/messages/page",
      "/api/v1/conversations/conv1/messages/page?before=cursor-1",
    ]);
  });

  it("sends a message", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(201, { id: "msg1" })));
    vi.stubGlobal("fetch", fetchMock);
    await sendMessage("conv1", "hello");
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/conversations/conv1/messages");
    expect(JSON.parse(init.body as string)).toEqual({ content: "hello" });
  });
});
