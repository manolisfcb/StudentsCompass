import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
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
      <div className="network-card__header">
        <div>
          <h3>{t("community.friends.title")}</h3>
          <p>{t("community.friends.subtitle")}</p>
        </div>
      </div>

      <div className="network-grid">
        <section className="network-column">
          <div className="network-column__header">
            <h4>{t("community.friends.incoming")}</h4>
          </div>
          <AsyncBoundary query={incomingQuery}>
            {(requests) =>
              requests.length === 0 ? (
                <p className="network-empty">{t("community.friends.noIncoming")}</p>
              ) : (
                <ul className="network-list">
                  {requests.map((request) => (
                    <IncomingRequestRow key={request.id} request={request} />
                  ))}
                </ul>
              )
            }
          </AsyncBoundary>
        </section>

        <section className="network-column">
          <div className="network-column__header">
            <h4>{t("community.friends.outgoing")}</h4>
          </div>
          <AsyncBoundary query={outgoingQuery}>
            {(requests) =>
              requests.length === 0 ? (
                <p className="network-empty">{t("community.friends.noOutgoing")}</p>
              ) : (
                <ul className="network-list">
                  {requests.map((request) => (
                    <OutgoingRequestRow key={request.id} request={request} />
                  ))}
                </ul>
              )
            }
          </AsyncBoundary>
        </section>

        <section className="network-column">
          <div className="network-column__header">
            <h4>{t("community.friends.friends")}</h4>
          </div>
          <AsyncBoundary query={friendsQuery}>
            {(friends) =>
              friends.length === 0 ? (
                <p className="network-empty">{t("community.friends.noFriends")}</p>
              ) : (
                <ul className="network-list">
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

/** `.network-item` — an avatar, a name, and the row's actions. */
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
    <li className="network-item">
      <div className="network-item__identity">
        <span className="network-avatar" aria-hidden="true">
          {name.charAt(0).toUpperCase()}
        </span>
        <div>
          <h5>{name}</h5>
          {error ? <p role="alert">{error}</p> : null}
        </div>
      </div>
      <div className="network-item__actions">{actions}</div>
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
          <button
            type="button"
            className="network-action"
            disabled={acceptMutation.isPending || rejectMutation.isPending}
            onClick={() => acceptMutation.mutate()}
          >
            {t("community.friends.accept")}
          </button>
          <button
            type="button"
            className="network-action"
            disabled={acceptMutation.isPending || rejectMutation.isPending}
            onClick={() => rejectMutation.mutate()}
          >
            {t("community.friends.ignore")}
          </button>
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
        <button
          type="button"
          className="network-action"
          disabled={cancelMutation.isPending}
          onClick={() => cancelMutation.mutate()}
        >
          {t("community.friends.cancel")}
        </button>
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
          <button
            type="button"
            className="network-action"
            disabled={messageMutation.isPending}
            onClick={() => messageMutation.mutate()}
          >
            {t("community.friends.message")}
          </button>
          <button
            type="button"
            className="network-action"
            disabled={removeMutation.isPending}
            onClick={() => {
              if (window.confirm(t("community.friends.confirmRemove"))) removeMutation.mutate();
            }}
          >
            {t("community.friends.remove")}
          </button>
        </>
      }
    />
  );
}
