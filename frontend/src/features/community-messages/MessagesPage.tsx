import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { EmptyState } from "@/components/patterns/EmptyState";
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
 * "Messages" tab was a static stub with no backend calls — so this is the
 * first real consumer of `GET /conversations` and the cursor-paged
 * `GET /conversations/{id}/messages/page` TASK-024 built. No polling: plan
 * 08 §8 is explicit that real-time is added only on demand, not by default.
 */
export function MessagesPage() {
  const { conversationId } = useParams();
  const { t } = useTranslation();
  const query = useQuery({ queryKey: ["conversations"], queryFn: fetchConversations });

  return (
    <div className="space-y-6">
      <DocumentMeta
        title={t("messages.seoTitle")}
        description={t("messages.seoDescription")}
        path="/messages"
      />
      <h1 className="text-2xl font-bold text-ink">{t("messages.title")}</h1>
      <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
        <AsyncBoundary query={query}>
          {(conversations) => <ConversationList conversations={conversations} activeId={conversationId} />}
        </AsyncBoundary>
        {conversationId ? (
          <ConversationView conversationId={conversationId} />
        ) : (
          <div className="hidden lg:block">
            <EmptyState title={t("messages.selectConversation")} />
          </div>
        )}
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
  if (conversations.length === 0) return <EmptyState title={t("messages.noConversations")} />;

  return (
    <ul className="space-y-2">
      {conversations.map((conversation) => (
        <li key={conversation.id}>
          <Link
            to={`/messages/${conversation.id}`}
            className={`block rounded-md border p-3 text-sm ${
              conversation.id === activeId ? "border-brand bg-brand/10" : "border-border bg-surface hover:bg-canvas"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-medium text-ink">{conversation.other_user.display_name}</span>
              {conversation.unread_count > 0 ? (
                <span className="rounded-full bg-brand px-2 py-0.5 text-xs font-medium text-white">
                  {conversation.unread_count}
                </span>
              ) : null}
            </div>
            {conversation.last_message_preview ? (
              <p className="mt-1 truncate text-ink-muted">{conversation.last_message_preview}</p>
            ) : (
              <p className="mt-1 text-ink-muted">{t("messages.noMessagesYet")}</p>
            )}
          </Link>
        </li>
      ))}
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
    <div className="flex flex-col rounded-lg border border-border bg-surface">
      <div className="flex-1 space-y-2 overflow-y-auto p-4">
        {messagesQuery.hasNextPage ? (
          <div className="text-center">
            <Button
              variant="ghost"
              disabled={messagesQuery.isFetchingNextPage}
              onClick={() => messagesQuery.fetchNextPage()}
            >
              {t("messages.loadOlder")}
            </Button>
          </div>
        ) : null}
        {allMessages.map((message) => (
          <div key={message.id} className={`max-w-[75%] ${message.is_mine ? "ml-auto text-right" : ""}`}>
            <div
              className={`inline-block rounded-lg px-3 py-2 text-sm ${
                message.is_mine ? "bg-brand text-white" : "bg-canvas text-ink"
              }`}
            >
              {message.content}
            </div>
            <p className="mt-0.5 text-xs text-ink-muted">{new Date(message.created_at).toLocaleString()}</p>
          </div>
        ))}
      </div>
      <MessageComposer onSend={(content) => sendMutation.mutate(content)} pending={sendMutation.isPending} error={sendMutation.error} />
    </div>
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
    <form onSubmit={handleSubmit} className="space-y-2 border-t border-border p-3">
      {error ? (
        <Alert tone="danger">
          {error instanceof ApiError && error.detail ? error.detail.message : t("messages.sendError")}
        </Alert>
      ) : null}
      <div className="flex gap-2">
        <input
          value={content}
          onChange={(event) => setContent(event.target.value)}
          placeholder={t("messages.composePlaceholder")}
          className="flex-1 rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink"
        />
        <Button type="submit" disabled={pending}>
          {t("messages.send")}
        </Button>
      </div>
    </form>
  );
}
