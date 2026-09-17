import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { Alert, Badge, Button, Card, EmptyState, Input, PageHeader } from "@/components/ui";
import { cn } from "@/lib/cn";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import {
  fetchConversations,
  fetchMessagePage,
  markConversationRead,
  sendMessage,
  type Conversation,
  type Message,
} from "@/features/community-messages/api";

/**
 * The messaging inbox. There is no legacy screen to reproduce — `jobs.html`'s
 * "Messages" tab was a static stub with no backend calls — so this screen has
 * no ported sheet behind it and borrows the shipped vocabulary instead: the
 * community feed's two-column frame, and the `messages-*` rules in
 * `styles/app.css` written to match it. It is the first real consumer of
 * `GET /conversations` and the cursor-paged
 * `GET /conversations/{id}/messages/page` TASK-024 built. No polling: plan
 * 08 §8 is explicit that real-time is added only on demand, not by default.
 */
export function MessagesPage() {
  const { conversationId } = useParams();
  const { t } = useTranslation();
  const query = useQuery({ queryKey: ["conversations"], queryFn: fetchConversations });

  return (
    <div className="flex flex-col gap-4">
      <DocumentMeta title={t("messages.seoTitle")} description={t("messages.seoDescription")} path="/messages" />

      <PageHeader title={t("messages.title")} />

      {/* A fixed-height two-pane layout: the thread scrolls inside itself so
        * the composer stays put instead of being pushed off the bottom of the
        * page as the conversation grows.
        *
        * On a phone the two panes are alternatives rather than columns, which
        * is a visibility decision, not a rendering one — each pane is mounted
        * exactly once, so there is never a second composer or a second "load
        * older" button in the document. */}
      <div className="flex h-[calc(100vh-14rem)] min-h-96 gap-4">
        <aside
          className={cn(
            "w-full shrink-0 overflow-y-auto md:block md:w-72",
            conversationId && "hidden",
          )}
        >
          <AsyncBoundary query={query}>
            {(conversations) => <ConversationList conversations={conversations} activeId={conversationId} />}
          </AsyncBoundary>
        </aside>

        <div className={cn("min-w-0 flex-1", conversationId ? "flex" : "hidden md:flex")}>
          {conversationId ? (
            <ConversationView conversationId={conversationId} />
          ) : (
            <EmptyState title={t("messages.selectConversation")} icon="💬" className="w-full" />
          )}
        </div>
      </div>
    </div>
  );
}

function ConversationList({
  conversations,
  activeId,
}: {
  conversations: Conversation[];
  activeId?: string | undefined;
}) {
  const { t } = useTranslation();
  if (conversations.length === 0) {
    return <EmptyState title={t("messages.noConversations")} icon="📬" />;
  }

  return (
    <ul className="flex flex-col gap-1">
      {conversations.map((conversation) => {
        const active = conversation.id === activeId;
        return (
          <li key={conversation.id}>
            <Link
              to={`/messages/${conversation.id}`}
              aria-current={active ? "page" : undefined}
              className={
                active
                  ? "block rounded-md border border-primary bg-primary-subtle p-3"
                  : "block rounded-md border border-transparent p-3 transition-colors hover:bg-surface-hover"
              }
            >
              <div className="flex items-center justify-between gap-2">
                <span className={active ? "truncate text-body-sm font-medium text-primary" : "truncate text-body-sm font-medium text-ink"}>
                  {conversation.other_user.display_name}
                </span>
                {conversation.unread_count > 0 ? (
                  <Badge tone="brand">{conversation.unread_count}</Badge>
                ) : null}
              </div>
              <p className="mt-0.5 truncate text-caption text-ink-muted">
                {conversation.last_message_preview ?? t("messages.noMessagesYet")}
              </p>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function ConversationView({ conversationId }: { conversationId: string }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const messagesKey = ["conversations", conversationId, "messages"];

  // `useInfiniteQuery` owns page accumulation — no effect syncing a page
  // fetch into a second, hand-rolled array. Each page is oldest-first
  // internally (the schema's own contract); pages arrive newest-batch-first,
  // so the full transcript is the page list reversed, then flattened.
  const messagesQuery = useInfiniteQuery({
    queryKey: messagesKey,
    queryFn: ({ pageParam }) => fetchMessagePage(conversationId, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  });

  const allMessages: Message[] = messagesQuery.data
    ? [...messagesQuery.data.pages].reverse().flatMap((page) => page.items)
    : [];

  const readMutation = useMutation({
    mutationFn: () => markConversationRead(conversationId),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["conversations"] }),
  });
  const markRead = readMutation.mutate;
  useEffect(() => {
    markRead();
  }, [conversationId, markRead]);

  const sendMutation = useMutation({
    mutationFn: (content: string) => sendMessage(conversationId, content),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: messagesKey }),
        queryClient.invalidateQueries({ queryKey: ["conversations"] }),
      ]);
    },
  });

  return (
    <Card padding="none" className="flex min-w-0 flex-1 flex-col overflow-hidden">
      <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
        {messagesQuery.hasNextPage ? (
          <Button
            variant="ghost"
            size="sm"
            className="self-center"
            loading={messagesQuery.isFetchingNextPage}
            onClick={() => messagesQuery.fetchNextPage()}
          >
            {t("messages.loadOlder")}
          </Button>
        ) : null}

        {allMessages.map((message) => (
          <div
            key={message.id}
            className={message.is_mine ? "flex flex-col items-end gap-0.5" : "flex flex-col items-start gap-0.5"}
          >
            <div
              className={
                message.is_mine
                  ? "max-w-[75%] rounded-lg rounded-br-xs bg-primary px-3 py-2 text-body-sm whitespace-pre-wrap text-primary-fg"
                  : "max-w-[75%] rounded-lg rounded-bl-xs bg-surface-hover px-3 py-2 text-body-sm whitespace-pre-wrap text-ink"
              }
            >
              {message.content}
            </div>
            <time dateTime={message.created_at} className="text-overline text-ink-muted">
              {new Date(message.created_at).toLocaleString()}
            </time>
          </div>
        ))}
      </div>

      <MessageComposer
        onSend={(content) => sendMutation.mutate(content)}
        pending={sendMutation.isPending}
        error={sendMutation.error}
      />
    </Card>
  );
}

function MessageComposer({
  onSend,
  pending,
  error,
}: {
  onSend: (content: string) => void;
  pending: boolean;
  error: unknown;
}) {
  const { t } = useTranslation();
  const [content, setContent] = useState("");

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!content.trim()) return;
    onSend(content);
    setContent("");
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2 border-t border-border p-3">
      {error ? (
        <Alert tone="danger">
          {error instanceof ApiError && error.detail ? error.detail.message : t("messages.sendError")}
        </Alert>
      ) : null}
      <div className="flex gap-2">
        <Input
          value={content}
          onChange={(event) => setContent(event.target.value)}
          placeholder={t("messages.composePlaceholder")}
          aria-label={t("messages.composePlaceholder")}
        />
        <Button type="submit" loading={pending}>
          {t("messages.send")}
        </Button>
      </div>
    </form>
  );
}
