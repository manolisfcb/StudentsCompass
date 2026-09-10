import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { EmptyState } from "@/components/patterns/EmptyState";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import {
  createComment,
  createCommunityPost,
  fetchComments,
  fetchCommunity,
  fetchCommunityMembership,
  fetchCommunityPosts,
  joinCommunity,
  leaveCommunity,
  likePost,
  unlikePost,
  type Community,
  type CommunityMembership,
  type CommunityPost,
  type CommunityPostCreate,
} from "@/features/community-messages/api";

const POST_TYPES: CommunityPostCreate["post_type"][] = [
  "discussion",
  "question",
  "resource",
  "win",
  "accountability",
  "introduction",
];

/**
 * `community_feed.html`/`.js`. Joining/leaving is optimistic — the only
 * operations in this vertical idempotent enough to earn it (plan 08 §8) —
 * but the count shown is always what the next `GET /communities/{id}`
 * confirms, exactly like the legacy JS: it never increments `member_count`
 * itself, it reloads the authoritative row after the mutation settles.
 */
export function CommunityFeedPage() {
  const { communityId = "" } = useParams();
  const communityQuery = useQuery({
    queryKey: ["community", communityId],
    queryFn: () => fetchCommunity(communityId),
  });
  const membershipQuery = useQuery({
    queryKey: ["community", communityId, "membership"],
    queryFn: () => fetchCommunityMembership(communityId),
  });

  return (
    <div className="space-y-6">
      <AsyncBoundary query={communityQuery}>
        {(community) => (
          <>
            <DocumentMeta title={community.name} description={community.description ?? ""} path={`/community/${communityId}`} />
            <CommunityHeader community={community} />
            <AsyncBoundary query={membershipQuery}>
              {(membership) => <CommunityBody communityId={communityId} membership={membership} />}
            </AsyncBoundary>
          </>
        )}
      </AsyncBoundary>
    </div>
  );
}

function CommunityHeader({ community }: { community: Community }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const joinMutation = useMutation({
    mutationFn: () => joinCommunity(community.id),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ["community", community.id, "membership"] });
      const previous = queryClient.getQueryData<CommunityMembership>(["community", community.id, "membership"]);
      queryClient.setQueryData(["community", community.id, "membership"], { is_member: true });
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(["community", community.id, "membership"], context.previous);
    },
    onSettled: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["community", community.id, "membership"] }),
        // Re-fetched, not incremented locally — `member_count` comes back
        // from this request, the same pattern `community_feed.js` used.
        queryClient.invalidateQueries({ queryKey: ["community", community.id] }),
      ]);
    },
  });

  const leaveMutation = useMutation({
    mutationFn: () => leaveCommunity(community.id),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ["community", community.id, "membership"] });
      const previous = queryClient.getQueryData<CommunityMembership>(["community", community.id, "membership"]);
      queryClient.setQueryData(["community", community.id, "membership"], { is_member: false });
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(["community", community.id, "membership"], context.previous);
    },
    onSettled: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["community", community.id, "membership"] }),
        queryClient.invalidateQueries({ queryKey: ["community", community.id] }),
      ]);
    },
  });

  const membership = queryClient.getQueryData<CommunityMembership>(["community", community.id, "membership"]);
  const error = joinMutation.error ?? leaveMutation.error;

  return (
    <div className="space-y-3 rounded-lg border border-border bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span aria-hidden="true" className="text-3xl">
            {community.icon ?? "👥"}
          </span>
          <div>
            <h1 className="text-xl font-bold text-ink">{community.name}</h1>
            <p className="text-sm text-ink-muted">
              {t("community.feed.memberCount", { count: community.member_count })}
            </p>
          </div>
        </div>
        {membership?.is_member ? (
          <Button
            variant="secondary"
            disabled={leaveMutation.isPending}
            onClick={() => {
              if (window.confirm(t("community.feed.confirmLeave"))) leaveMutation.mutate();
            }}
          >
            {t("community.feed.leave")}
          </Button>
        ) : (
          <Button disabled={joinMutation.isPending} onClick={() => joinMutation.mutate()}>
            {t("community.feed.join")}
          </Button>
        )}
      </div>
      {community.description ? <p className="text-sm text-ink-soft">{community.description}</p> : null}
      {error ? (
        <Alert tone="danger">
          {error instanceof ApiError && error.detail ? error.detail.message : t("community.feed.membershipError")}
        </Alert>
      ) : null}
    </div>
  );
}

function CommunityBody({ communityId, membership }: { communityId: string; membership: CommunityMembership }) {
  const { t } = useTranslation();
  const postsQuery = useQuery({
    queryKey: ["community", communityId, "posts"],
    queryFn: () => fetchCommunityPosts(communityId),
    enabled: membership.is_member,
  });

  if (!membership.is_member) {
    return <EmptyState title={t("community.feed.joinToView")} />;
  }

  return (
    <div className="space-y-6">
      <ComposePost communityId={communityId} />
      <AsyncBoundary query={postsQuery}>
        {(posts) =>
          posts.length === 0 ? (
            <EmptyState title={t("community.feed.empty")} />
          ) : (
            <div className="space-y-4">
              {posts.map((post) => (
                <PostCard key={post.id} communityId={communityId} post={post} />
              ))}
            </div>
          )
        }
      </AsyncBoundary>
    </div>
  );
}

function ComposePost({ communityId }: { communityId: string }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [content, setContent] = useState("");
  const [postType, setPostType] = useState<CommunityPostCreate["post_type"]>("discussion");

  const mutation = useMutation({
    mutationFn: () => createCommunityPost(communityId, { content, post_type: postType }),
    onSuccess: async () => {
      setContent("");
      await queryClient.invalidateQueries({ queryKey: ["community", communityId, "posts"] });
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-2 rounded-lg border border-border bg-surface p-4">
      {mutation.isError ? (
        <Alert tone="danger">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("community.feed.postError")}
        </Alert>
      ) : null}
      <textarea
        required
        rows={3}
        value={content}
        onChange={(event) => setContent(event.target.value)}
        placeholder={t("community.feed.composePlaceholder")}
        className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink"
      />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <select
          value={postType}
          onChange={(event) => setPostType(event.target.value as CommunityPostCreate["post_type"])}
          className="rounded-md border border-border bg-surface px-2 py-1 text-xs text-ink"
        >
          {POST_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? t("community.feed.posting") : t("community.feed.post")}
        </Button>
      </div>
    </form>
  );
}

function PostCard({ communityId, post }: { communityId: string; post: CommunityPost }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [showComments, setShowComments] = useState(false);

  const likeMutation = useMutation({
    mutationFn: () => (post.liked_by_me ? unlikePost(post.id) : likePost(post.id)),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["community", communityId, "posts"] }),
  });

  return (
    <article className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-ink">{post.author_name}</span>
        <span className="rounded-full bg-brand/10 px-2 py-0.5 text-xs font-medium text-brand">{post.post_type}</span>
      </div>
      {post.title ? <h3 className="mt-1 font-semibold text-ink">{post.title}</h3> : null}
      <p className="mt-1 whitespace-pre-wrap text-sm text-ink-soft">{post.content}</p>
      <div className="mt-3 flex items-center gap-4 text-sm text-ink-muted">
        <button
          type="button"
          onClick={() => likeMutation.mutate()}
          disabled={likeMutation.isPending}
          className={post.liked_by_me ? "font-medium text-brand" : ""}
        >
          {t("community.feed.likes", { count: post.like_count })}
        </button>
        <button type="button" onClick={() => setShowComments((value) => !value)}>
          {t("community.feed.comments", { count: post.comment_count })}
        </button>
      </div>
      {showComments ? <CommentsSection postId={post.id} /> : null}
    </article>
  );
}

function CommentsSection({ postId }: { postId: string }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [content, setContent] = useState("");
  const query = useQuery({ queryKey: ["community-posts", postId, "comments"], queryFn: () => fetchComments(postId) });

  const mutation = useMutation({
    mutationFn: () => createComment(postId, { content }),
    onSuccess: async () => {
      setContent("");
      await queryClient.invalidateQueries({ queryKey: ["community-posts", postId, "comments"] });
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <div className="mt-3 space-y-2 border-t border-border pt-3">
      <AsyncBoundary query={query}>
        {(comments) => (
          <ul className="space-y-2">
            {comments.map((comment) => (
              <li key={comment.id} className="text-sm">
                <span className="font-medium text-ink">{comment.author_name}</span>{" "}
                <span className="text-ink-soft">{comment.content}</span>
              </li>
            ))}
          </ul>
        )}
      </AsyncBoundary>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          required
          value={content}
          onChange={(event) => setContent(event.target.value)}
          placeholder={t("community.feed.commentPlaceholder")}
          className="flex-1 rounded-md border border-border bg-surface px-2 py-1 text-sm text-ink"
        />
        <Button type="submit" variant="secondary" disabled={mutation.isPending}>
          {t("community.feed.reply")}
        </Button>
      </form>
    </div>
  );
}
