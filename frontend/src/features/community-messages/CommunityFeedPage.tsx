import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import {
  Alert,
  Arrow,
  Badge,
  Button,
  Card,
  EmptyState,
  Icon,
  Input,
  Select,
  Textarea,
  toIconName,
} from "@/components/ui";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
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

  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-4">
      <Link to="/community" className="text-body-sm text-ink-soft transition-colors hover:text-ink">
        <Arrow direction="back" />
        {t("community.feed.backToCommunities")}
      </Link>
      <AsyncBoundary query={communityQuery}>
        {(community) => (
          <>
            <DocumentMeta title={community.name} description={community.description ?? ""} path={`/community/${communityId}`} />
            <CommunityHeader community={community} />
            <AsyncBoundary query={membershipQuery}>
              {(membership) => (
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
                  <div className="flex min-w-0 flex-1 flex-col gap-4">
                    <CommunityBody communityId={communityId} membership={membership} />
                  </div>

                  {/* The rail is secondary reading, so on a phone it follows
                    * the feed rather than pushing it below the fold. */}
                  <aside className="flex w-full shrink-0 flex-col gap-3 lg:w-72">
                    <Card>
                      <h3 className="text-card-title text-ink">{t("community.feed.about")}</h3>
                      <p className="mt-1.5 text-body-sm text-ink-soft">
                        {community.description ?? t("community.list.noDescription")}
                      </p>
                    </Card>
                    <Card>
                      <h3 className="text-card-title text-ink">{t("community.feed.rules.title")}</h3>
                      <ul className="mt-1.5 list-disc space-y-1 pl-5 text-body-sm text-ink-soft">
                        <li>{t("community.feed.rules.0")}</li>
                        <li>{t("community.feed.rules.1")}</li>
                        <li>{t("community.feed.rules.2")}</li>
                        <li>{t("community.feed.rules.3")}</li>
                      </ul>
                    </Card>
                  </aside>
                </div>
              )}
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
    <Card className="flex flex-col gap-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 gap-3">
          <span
            aria-hidden="true"
            className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-primary-subtle text-primary"
          >
            <Icon name={toIconName(community.icon, "users")} size={24} />
          </span>
          <div className="min-w-0">
            <h1 className="text-page-title text-ink">{community.name}</h1>
            {community.description ? (
              <p className="mt-1 text-body-sm text-ink-soft">{community.description}</p>
            ) : null}
            <Badge className="mt-2">{t("community.feed.memberCount", { count: community.member_count })}</Badge>
          </div>
        </div>

        {membership?.is_member ? (
          <Button
            variant="outline"
            loading={leaveMutation.isPending}
            onClick={() => {
              if (window.confirm(t("community.feed.confirmLeave"))) leaveMutation.mutate();
            }}
          >
            {t("community.feed.leave")}
          </Button>
        ) : (
          <Button loading={joinMutation.isPending} onClick={() => joinMutation.mutate()}>
            {t("community.feed.join")}
          </Button>
        )}
      </div>

      {error ? (
        <Alert tone="danger">
          {error instanceof ApiError && error.detail ? error.detail.message : t("community.feed.membershipError")}
        </Alert>
      ) : null}
    </Card>
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
    return (
      <EmptyState title={t("community.feed.joinToView")} icon="lock" />
    );
  }

  return (
    <>
      <ComposePost communityId={communityId} />
      <AsyncBoundary query={postsQuery}>
        {(posts) =>
          posts.length === 0 ? (
            <EmptyState title={t("community.feed.empty")} icon="message" />
          ) : (
            <>
              {posts.map((post) => (
                <PostCard key={post.id} communityId={communityId} post={post} />
              ))}
            </>
          )
        }
      </AsyncBoundary>
    </>
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
    <Card>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <Textarea
          required
          rows={3}
          value={content}
          onChange={(event) => setContent(event.target.value)}
          placeholder={t("community.feed.composePlaceholder")}
          aria-label={t("community.feed.composePlaceholder")}
        />

        {mutation.isError ? (
          <Alert tone="danger">
            {mutation.error instanceof ApiError && mutation.error.detail
              ? mutation.error.detail.message
              : t("community.feed.postError")}
          </Alert>
        ) : null}

        <div className="flex flex-wrap items-center justify-between gap-2">
          <label className="flex items-center gap-2 text-label text-ink-soft">
            {t("community.feed.postType")}
            <Select
              value={postType}
              onChange={(event) => setPostType(event.target.value as CommunityPostCreate["post_type"])}
              className="h-8 w-auto text-caption"
            >
              {POST_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </Select>
          </label>

          <Button type="submit" disabled={content.trim() === ""} loading={mutation.isPending}>
            {mutation.isPending ? t("community.feed.posting") : t("community.feed.post")}
          </Button>
        </div>
      </form>
    </Card>
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

  const initials = post.author_name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? "")
    .join("");

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <span
          aria-hidden="true"
          className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary-subtle text-label text-primary"
        >
          {initials}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-card-title text-ink">{post.author_name}</p>
          <time dateTime={post.created_at} className="text-caption text-ink-muted">
            {new Date(post.created_at).toLocaleDateString()}
          </time>
        </div>
        <Badge>{post.post_type}</Badge>
      </div>

      <div className="min-w-0">
        {post.title ? <h3 className="text-card-title text-ink">{post.title}</h3> : null}
        <p className="text-body-sm whitespace-pre-wrap text-ink-soft">{post.content}</p>
      </div>

      <div className="flex items-center gap-2 border-t border-border pt-3">
        {/* `aria-pressed` plus a filled variant: the like state is both
          * announced and visible, which a colour change alone was not. */}
        <Button
          variant={post.liked_by_me ? "secondary" : "ghost"}
          size="sm"
          aria-pressed={post.liked_by_me}
          disabled={likeMutation.isPending}
          onClick={() => likeMutation.mutate()}
        >
          {t("community.feed.like")} · {post.like_count}
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setShowComments((value) => !value)}>
          {t("community.feed.comment")} · {post.comment_count}
        </Button>
      </div>

      {showComments ? <CommentsSection postId={post.id} /> : null}
    </Card>
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
    <div className="flex flex-col gap-3 border-t border-border pt-3">
      <AsyncBoundary query={query}>
        {(comments) => (
          <ul className="flex flex-col gap-3">
            {comments.map((comment) => (
              <li key={comment.id} className="flex gap-2.5">
                <span
                  aria-hidden="true"
                  className="flex size-7 shrink-0 items-center justify-center rounded-full bg-surface-hover text-caption text-ink-soft"
                >
                  {comment.author_name.charAt(0).toUpperCase()}
                </span>
                <div className="min-w-0 rounded-md bg-surface-subtle px-3 py-2">
                  <p className="text-label text-ink">{comment.author_name}</p>
                  <p className="text-body-sm text-ink-soft">{comment.content}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </AsyncBoundary>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <Input
          required
          value={content}
          onChange={(event) => setContent(event.target.value)}
          placeholder={t("community.feed.commentPlaceholder")}
          aria-label={t("community.feed.commentPlaceholder")}
        />
        <Button type="submit" loading={mutation.isPending}>
          {t("community.feed.reply")}
        </Button>
      </form>
    </div>
  );
}
