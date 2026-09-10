/**
 * Communities, friendships, and messages (TASK-051, plan 08 §5.2).
 *
 * `POST /communities/{id}/join` and `DELETE /communities/{id}/leave` renamed
 * to the idempotent `PUT/DELETE /communities/{id}/members/me` — a second
 * `PUT` from someone already a member answers 200 with their existing
 * membership instead of the 409 the old verb gave. `POST
 * /friends/requests/{id}/accept` renamed to `PATCH /friend-requests/{id}`
 * with `{status: "accepted"}`; reject/cancel keep their existing paths, the
 * plan does not name them. Messages already used the cursor page shape
 * TASK-024/TASK-041 generalised — nothing to rename there.
 */

import { apiRequest } from "@/api/client";
import type { RequestOf, ResponseOf } from "@/api/types";

export type Community = ResponseOf<"communities_list_communities">[number];
export type CommunityMembership = ResponseOf<"communities_check_membership">;
export type CommunityMember = ResponseOf<"communities_join_community">;
export type CommunityPost = ResponseOf<"communities_list_community_posts_enriched">[number];
export type CommunityPostCreate = RequestOf<"communities_create_community_post">;
export type CommunityComment = ResponseOf<"communities_list_comments_enriched">[number];
export type CommunityCommentCreate = RequestOf<"communities_create_comment">;

export type FriendRequest = ResponseOf<"friendships_list_incoming_friend_requests">[number];
export type Friendship = ResponseOf<"friendships_list_friends">[number];

export type Conversation = ResponseOf<"messages_list_conversations">[number];
export type MessagePage = ResponseOf<"messages_list_message_page">;
export type Message = MessagePage["items"][number];

export async function fetchCommunities(tags: string[] = []): Promise<Community[]> {
  const query = tags.length > 0 ? `?tags=${encodeURIComponent(tags.join(","))}` : "";
  const { data } = await apiRequest<Community[]>(`/api/v1/communities${query}`);
  return data;
}

export async function fetchCommunity(communityId: string): Promise<Community> {
  const { data } = await apiRequest<Community>(`/api/v1/communities/${communityId}`);
  return data;
}

export async function fetchCommunityMembership(communityId: string): Promise<CommunityMembership> {
  const { data } = await apiRequest<CommunityMembership>(`/api/v1/communities/${communityId}/membership`);
  return data;
}

/** Idempotent: joining a second time just returns the existing membership. */
export async function joinCommunity(communityId: string): Promise<CommunityMember> {
  const { data } = await apiRequest<CommunityMember>(`/api/v1/communities/${communityId}/members/me`, {
    method: "PUT",
  });
  return data;
}

/** Idempotent: leaving when already not a member is a no-op, not an error. */
export async function leaveCommunity(communityId: string): Promise<void> {
  await apiRequest(`/api/v1/communities/${communityId}/members/me`, { method: "DELETE" });
}

export async function fetchCommunityPosts(communityId: string): Promise<CommunityPost[]> {
  const { data } = await apiRequest<CommunityPost[]>(`/api/v1/communities/${communityId}/posts/enriched`);
  return data;
}

export async function createCommunityPost(
  communityId: string,
  payload: CommunityPostCreate,
): Promise<CommunityPost> {
  const { data } = await apiRequest<CommunityPost>(`/api/v1/communities/${communityId}/posts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return data;
}

export async function likePost(postId: string): Promise<void> {
  await apiRequest(`/api/v1/community-posts/${postId}/likes`, { method: "POST" });
}

export async function unlikePost(postId: string): Promise<void> {
  await apiRequest(`/api/v1/community-posts/${postId}/likes`, { method: "DELETE" });
}

export async function fetchComments(postId: string): Promise<CommunityComment[]> {
  const { data } = await apiRequest<CommunityComment[]>(`/api/v1/community-posts/${postId}/comments/enriched`);
  return data;
}

export async function createComment(postId: string, payload: CommunityCommentCreate): Promise<CommunityComment> {
  const { data } = await apiRequest<CommunityComment>(`/api/v1/community-posts/${postId}/comments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return data;
}

export async function fetchIncomingFriendRequests(): Promise<FriendRequest[]> {
  const { data } = await apiRequest<FriendRequest[]>("/api/v1/friends/requests/incoming");
  return data;
}

export async function fetchOutgoingFriendRequests(): Promise<FriendRequest[]> {
  const { data } = await apiRequest<FriendRequest[]>("/api/v1/friends/requests/outgoing");
  return data;
}

export async function fetchFriends(): Promise<Friendship[]> {
  const { data } = await apiRequest<Friendship[]>("/api/v1/friends");
  return data;
}

export async function acceptFriendRequest(requestId: string): Promise<FriendRequest> {
  const { data } = await apiRequest<FriendRequest>(`/api/v1/friend-requests/${requestId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: "accepted" }),
  });
  return data;
}

export async function rejectFriendRequest(requestId: string): Promise<FriendRequest> {
  const { data } = await apiRequest<FriendRequest>(`/api/v1/friends/requests/${requestId}/reject`, {
    method: "POST",
  });
  return data;
}

export async function cancelFriendRequest(requestId: string): Promise<FriendRequest> {
  const { data } = await apiRequest<FriendRequest>(`/api/v1/friends/requests/${requestId}/cancel`, {
    method: "POST",
  });
  return data;
}

export async function removeFriend(friendId: string): Promise<void> {
  await apiRequest(`/api/v1/friends/${friendId}`, { method: "DELETE" });
}

export async function fetchConversations(): Promise<Conversation[]> {
  const { data } = await apiRequest<Conversation[]>("/api/v1/conversations");
  return data;
}

export async function startDirectConversation(friendId: string): Promise<Conversation> {
  const { data } = await apiRequest<Conversation>("/api/v1/conversations/direct", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ friend_id: friendId }),
  });
  return data;
}

export async function fetchMessagePage(conversationId: string, before?: string | null): Promise<MessagePage> {
  const query = before ? `?before=${encodeURIComponent(before)}` : "";
  const { data } = await apiRequest<MessagePage>(`/api/v1/conversations/${conversationId}/messages/page${query}`);
  return data;
}

export async function sendMessage(conversationId: string, content: string): Promise<Message> {
  const { data } = await apiRequest<Message>(`/api/v1/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  return data;
}

export async function markConversationRead(conversationId: string): Promise<void> {
  await apiRequest(`/api/v1/conversations/${conversationId}/read`, { method: "POST" });
}
