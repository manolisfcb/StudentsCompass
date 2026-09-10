import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { EmptyState } from "@/components/patterns/EmptyState";
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
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-ink">{t("community.friends.title")}</h2>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold text-ink">{t("community.friends.incoming")}</h3>
        <AsyncBoundary query={incomingQuery}>
          {(requests) =>
            requests.length === 0 ? (
              <p className="text-sm text-ink-muted">{t("community.friends.noIncoming")}</p>
            ) : (
              <ul className="space-y-2">
                {requests.map((request) => (
                  <IncomingRequestRow key={request.id} request={request} />
                ))}
              </ul>
            )
          }
        </AsyncBoundary>
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold text-ink">{t("community.friends.outgoing")}</h3>
        <AsyncBoundary query={outgoingQuery}>
          {(requests) =>
            requests.length === 0 ? (
              <p className="text-sm text-ink-muted">{t("community.friends.noOutgoing")}</p>
            ) : (
              <ul className="space-y-2">
                {requests.map((request) => (
                  <OutgoingRequestRow key={request.id} request={request} />
                ))}
              </ul>
            )
          }
        </AsyncBoundary>
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold text-ink">{t("community.friends.friends")}</h3>
        <AsyncBoundary query={friendsQuery}>
          {(friends) =>
            friends.length === 0 ? (
              <EmptyState title={t("community.friends.noFriends")} />
            ) : (
              <ul className="space-y-2">
                {friends.map((friendship) => (
                  <FriendRow key={friendship.friend.id} friendship={friendship} />
                ))}
              </ul>
            )
          }
        </AsyncBoundary>
      </section>
    </div>
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
    <li className="space-y-1 rounded-md border border-border p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm text-ink">{request.sender.display_name}</span>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            disabled={acceptMutation.isPending || rejectMutation.isPending}
            onClick={() => acceptMutation.mutate()}
          >
            {t("community.friends.accept")}
          </Button>
          <Button
            variant="ghost"
            disabled={acceptMutation.isPending || rejectMutation.isPending}
            onClick={() => rejectMutation.mutate()}
          >
            {t("community.friends.ignore")}
          </Button>
        </div>
      </div>
      {error ? (
        <Alert tone="danger">
          {error instanceof ApiError && error.detail ? error.detail.message : t("community.friends.actionError")}
        </Alert>
      ) : null}
    </li>
  );
}

function OutgoingRequestRow({ request }: { request: FriendRequest }) {
  const { t } = useTranslation();
  const invalidate = useInvalidateNetwork();
  const cancelMutation = useMutation({ mutationFn: () => cancelFriendRequest(request.id), onSuccess: invalidate });

  return (
    <li className="flex items-center justify-between gap-2 rounded-md border border-border p-3">
      <span className="text-sm text-ink">{request.receiver.display_name}</span>
      <Button variant="ghost" disabled={cancelMutation.isPending} onClick={() => cancelMutation.mutate()}>
        {t("community.friends.cancel")}
      </Button>
    </li>
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
    <li className="flex items-center justify-between gap-2 rounded-md border border-border p-3">
      <span className="text-sm text-ink">{friendship.friend.display_name}</span>
      <div className="flex gap-2">
        <Button variant="secondary" disabled={messageMutation.isPending} onClick={() => messageMutation.mutate()}>
          {t("community.friends.message")}
        </Button>
        <Button
          variant="ghost"
          disabled={removeMutation.isPending}
          onClick={() => {
            if (window.confirm(t("community.friends.confirmRemove"))) removeMutation.mutate();
          }}
        >
          {t("community.friends.remove")}
        </Button>
      </div>
    </li>
  );
}
