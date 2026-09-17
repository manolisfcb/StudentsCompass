import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { Button, SectionHeader } from "@/components/ui";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import {
  acceptFriendRequest,
  cancelFriendRequest,
  fetchFriends,
  fetchIncomingFriendRequests,
  fetchOutgoingFriendRequests,
  rejectFriendRequest,
  removeFriend,
  startDirectConversation,
  type FriendRequest,
  type Friendship,
} from "@/features/community-messages/api";

const QUERY_KEYS = {
  incoming: ["friends", "requests", "incoming"],
  outgoing: ["friends", "requests", "outgoing"],
  friends: ["friends"],
};

/**
 * "Your student network" (`userProfile.html`'s `.network-card`). Legacy
 * reloaded all three lists after every action instead of patching state
 * locally; this keeps that shape (invalidate, not optimistic-update) because
 * accept/reject/cancel are not the idempotent relations plan 08 §8 scopes
 * optimistic UI to — only community membership and roadmap saves are.
 */
export function FriendsPanel() {
  const { t } = useTranslation();
  const incomingQuery = useQuery({ queryKey: QUERY_KEYS.incoming, queryFn: fetchIncomingFriendRequests });
  const outgoingQuery = useQuery({ queryKey: QUERY_KEYS.outgoing, queryFn: fetchOutgoingFriendRequests });
  const friendsQuery = useQuery({ queryKey: QUERY_KEYS.friends, queryFn: fetchFriends });

  return (
    <>
      <SectionHeader
        title={t("community.friends.title")}
        description={t("community.friends.subtitle")}
        className="mb-4"
      />

      <div className="grid gap-5 lg:grid-cols-3">
        <section className="flex flex-col gap-2">
          <h4 className="text-overline text-ink-muted uppercase">{t("community.friends.incoming")}</h4>
          <AsyncBoundary query={incomingQuery}>
            {(requests) =>
              requests.length === 0 ? (
                <p className="rounded-md bg-surface-subtle px-3 py-4 text-center text-caption text-ink-muted">{t("community.friends.noIncoming")}</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {requests.map((request) => (
                    <IncomingRequestRow key={request.id} request={request} />
                  ))}
                </ul>
              )
            }
          </AsyncBoundary>
        </section>

        <section className="flex flex-col gap-2">
          <h4 className="text-overline text-ink-muted uppercase">{t("community.friends.outgoing")}</h4>
          <AsyncBoundary query={outgoingQuery}>
            {(requests) =>
              requests.length === 0 ? (
                <p className="rounded-md bg-surface-subtle px-3 py-4 text-center text-caption text-ink-muted">{t("community.friends.noOutgoing")}</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {requests.map((request) => (
                    <OutgoingRequestRow key={request.id} request={request} />
                  ))}
                </ul>
              )
            }
          </AsyncBoundary>
        </section>

        <section className="flex flex-col gap-2">
          <h4 className="text-overline text-ink-muted uppercase">{t("community.friends.friends")}</h4>
          <AsyncBoundary query={friendsQuery}>
            {(friends) =>
              friends.length === 0 ? (
                <p className="rounded-md bg-surface-subtle px-3 py-4 text-center text-caption text-ink-muted">{t("community.friends.noFriends")}</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {friends.map((friendship) => (
                    <FriendRow key={friendship.friend.id} friendship={friendship} />
                  ))}
                </ul>
              )
            }
          </AsyncBoundary>
        </section>
      </div>
    </>
  );
}

/** One person in the network: an avatar, a name, and the row's actions. */
function NetworkRow({
  name,
  actions,
  error,
}: {
  name: string;
  actions: React.ReactNode;
  error?: React.ReactNode;
}) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-2.5">
      <div className="flex min-w-0 items-center gap-2.5">
        <span
          aria-hidden="true"
          className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary-subtle text-caption font-semibold text-primary"
        >
          {name.charAt(0).toUpperCase()}
        </span>
        <div className="min-w-0">
          <p className="truncate text-body-sm font-medium text-ink">{name}</p>
          {error ? (
            <p role="alert" className="text-caption text-danger">
              {error}
            </p>
          ) : null}
        </div>
      </div>
      <div className="flex shrink-0 gap-1.5">{actions}</div>
    </li>
  );
}

function useInvalidateNetwork() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.incoming }),
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.outgoing }),
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.friends }),
    ]);
}

function IncomingRequestRow({ request }: { request: FriendRequest }) {
  const { t } = useTranslation();
  const invalidate = useInvalidateNetwork();
  const acceptMutation = useMutation({ mutationFn: () => acceptFriendRequest(request.id), onSuccess: invalidate });
  const rejectMutation = useMutation({ mutationFn: () => rejectFriendRequest(request.id), onSuccess: invalidate });
  const error = acceptMutation.error ?? rejectMutation.error;

  return (
    <NetworkRow
      name={request.sender.display_name}
      error={
        error
          ? error instanceof ApiError && error.detail
            ? error.detail.message
            : t("community.friends.actionError")
          : undefined
      }
      actions={
        <>
          <Button
            size="sm"
            disabled={acceptMutation.isPending || rejectMutation.isPending}
            onClick={() => acceptMutation.mutate()}
          >
            {t("community.friends.accept")}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={acceptMutation.isPending || rejectMutation.isPending}
            onClick={() => rejectMutation.mutate()}
          >
            {t("community.friends.ignore")}
          </Button>
        </>
      }
    />
  );
}

function OutgoingRequestRow({ request }: { request: FriendRequest }) {
  const { t } = useTranslation();
  const invalidate = useInvalidateNetwork();
  const cancelMutation = useMutation({ mutationFn: () => cancelFriendRequest(request.id), onSuccess: invalidate });

  return (
    <NetworkRow
      name={request.receiver.display_name}
      actions={
        <Button
          variant="ghost"
          size="sm"
          disabled={cancelMutation.isPending}
          onClick={() => cancelMutation.mutate()}
        >
          {t("community.friends.cancel")}
        </Button>
      }
    />
  );
}

function FriendRow({ friendship }: { friendship: Friendship }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const invalidate = useInvalidateNetwork();
  const removeMutation = useMutation({
    mutationFn: () => removeFriend(friendship.friend.id),
    onSuccess: invalidate,
  });
  const messageMutation = useMutation({
    mutationFn: () => startDirectConversation(friendship.friend.id),
    onSuccess: (conversation) => navigate(`/messages/${conversation.id}`),
  });

  return (
    <NetworkRow
      name={friendship.friend.display_name}
      actions={
        <>
          <Button
            variant="ghost"
            size="sm"
            disabled={messageMutation.isPending}
            onClick={() => messageMutation.mutate()}
          >
            {t("community.friends.message")}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={removeMutation.isPending}
            onClick={() => {
              if (window.confirm(t("community.friends.confirmRemove"))) removeMutation.mutate();
            }}
          >
            {t("community.friends.remove")}
          </Button>
        </>
      }
    />
  );
}
