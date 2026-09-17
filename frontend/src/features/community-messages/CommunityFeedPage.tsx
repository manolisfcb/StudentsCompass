import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { PageScope } from "@/components/layout/PageScope";
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
    <PageScope name="community-feed" className="feed-page">
      <Link to="/community" className="back-link">
        {t("community.feed.backToCommunities")}
      </Link>
      <AsyncBoundary query={communityQuery}>
        {(community) => (
          <>
            <DocumentMeta title={community.name} description={community.description ?? ""} path={`/community/${communityId}`} />
            <CommunityHeader community={community} />
            <AsyncBoundary query={membershipQuery}>
              {(membership) => (
                <div className="feed-layout">
                  <div className="feed-main">
                    <CommunityBody communityId={communityId} membership={membership} />
                  </div>
                  <aside className="feed-sidebar">
                    <div className="sidebar-card">
                      <h3>{t("community.feed.about")}</h3>
                      <p>{community.description ?? t("community.list.noDescription")}</p>
                    </div>
                    <div className="sidebar-card">
                      <h3>{t("community.feed.rules.title")}</h3>
                      <ul>
                        <li>{t("community.feed.rules.0")}</li>
                        <li>{t("community.feed.rules.1")}</li>
                        <li>{t("community.feed.rules.2")}</li>
                        <li>{t("community.feed.rules.3")}</li>
                      </ul>
                    </div>
                  </aside>
                </div>
              )}
            </AsyncBoundary>
          </>
        )}
      </AsyncBoundary>
    </PageScope>
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
    <div className="community-banner">
      <div className="banner-icon" aria-hidden="true">
        {community.icon ?? "👥"}
      </div>
      <div className="banner-info">
        <h1>{community.name}</h1>
        {community.description ? <p className="banner-desc">{community.description}</p> : null}
        <div className="banner-meta">
          <span className="banner-stat">{t("community.feed.memberCount", { count: community.member_count })}</span>
        </div>
        {error ? (
          <p className="banner-desc" role="alert">
            {error instanceof ApiError && error.detail ? error.detail.message : t("community.feed.membershipError")}
          </p>
        ) : null}
      </div>
      <div className="banner-actions">
        {membership?.is_member ? (
          <button
            type="button"
            className="btn-leave"
            disabled={leaveMutation.isPending}
            onClick={() => {
              if (window.confirm(t("community.feed.confirmLeave"))) leaveMutation.mutate();
            }}
          >
            {t("community.feed.leave")}
          </button>
        ) : (
          <button type="button" className="btn-join" disabled={joinMutation.isPending} onClick={() => joinMutation.mutate()}>
            {t("community.feed.join")}
          </button>
        )}
      </div>
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
    return (
      <div className="gate-card">
        <h2>{t("community.feed.joinToView")}</h2>
      </div>
    );
  }

  return (
    <>
      <ComposePost communityId={communityId} />
      <AsyncBoundary query={postsQuery}>
        {(posts) =>
          posts.length === 0 ? (
            <div className="empty-feed">
              <h3>{t("community.feed.empty")}</h3>
            </div>
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
    <form onSubmit={handleSubmit} className="composer">
      <div className="composer-toolbar">
        <label className="composer-select-wrap">
          <span>{t("community.feed.postType")}</span>
          <select
            className="composer-select"
            value={postType}
            onChange={(event) => setPostType(event.target.value as CommunityPostCreate["post_type"])}
          >
            {POST_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>
        {mutation.isError ? (
          <p className="composer-hint" role="alert">
            {mutation.error instanceof ApiError && mutation.error.detail
              ? mutation.error.detail.message
              : t("community.feed.postError")}
          </p>
        ) : null}
      </div>
      <textarea
        required
        rows={3}
        className="composer-body"
        value={content}
        onChange={(event) => setContent(event.target.value)}
        placeholder={t("community.feed.composePlaceholder")}
        aria-label={t("community.feed.composePlaceholder")}
      />
      <div className="composer-footer">
        <button type="submit" className="btn-primary" disabled={mutation.isPending || content.trim() === ""}>
          {mutation.isPending ? t("community.feed.posting") : t("community.feed.post")}
        </button>
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

  const initials = post.author_name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? "")
    .join("");

  return (
    <article className="post-card">
      <div className="post-card__body">
        <div className="post-author">
          <div className="post-avatar" aria-hidden="true">
            {initials}
          </div>
          <div className="post-author-info">
            <h4>{post.author_name}</h4>
            <time dateTime={post.created_at}>{new Date(post.created_at).toLocaleDateString()}</time>
          </div>
        </div>
        <div className="post-meta-row">
          <span className={`post-type-badge post-type-badge--${post.post_type}`}>{post.post_type}</span>
        </div>
        {post.title ? <h3 className="post-title">{post.title}</h3> : null}
        <p className="post-content">{post.content}</p>
      </div>
      <div className="post-counters">
        <span>{t("community.feed.likes", { count: post.like_count })}</span>
        <span>{t("community.feed.comments", { count: post.comment_count })}</span>
      </div>
      <div className="post-actions">
        <button
          type="button"
          className={`btn-ghost${post.liked_by_me ? " active" : ""}`}
          aria-pressed={post.liked_by_me}
          onClick={() => likeMutation.mutate()}
          disabled={likeMutation.isPending}
        >
          {t("community.feed.like")}
        </button>
        <button type="button" className="btn-ghost" onClick={() => setShowComments((value) => !value)}>
          {t("community.feed.comment")}
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
    <div className="comments-section open">
      <AsyncBoundary query={query}>
        {(comments) => (
          <div>
            {comments.map((comment) => (
              <div key={comment.id} className="comment-item">
                <div className="comment-avatar" aria-hidden="true">
                  {comment.author_name.charAt(0).toUpperCase()}
                </div>
                <div className="comment-body">
                  <strong>{comment.author_name}</strong>
                  <p>{comment.content}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </AsyncBoundary>
      <form onSubmit={handleSubmit} className="comment-form">
        <input
          required
          value={content}
          onChange={(event) => setContent(event.target.value)}
          placeholder={t("community.feed.commentPlaceholder")}
          aria-label={t("community.feed.commentPlaceholder")}
        />
        <button type="submit" disabled={mutation.isPending}>
          {t("community.feed.reply")}
        </button>
      </form>
    </div>
  );
}
