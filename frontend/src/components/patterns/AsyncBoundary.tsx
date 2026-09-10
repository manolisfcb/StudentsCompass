import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import { Spinner } from "@/components/primitives/Spinner";

/**
 * The three states of a remote read, in one place.
 *
 * `children` is a function of the *settled* value, so a screen cannot render
 * `data` while it is still `undefined` — the mistake that produces a flash of
 * a wrong empty state on every navigation. TypeScript enforces it here rather
 * than each screen remembering an `if (!data) return null`.
 */
export function AsyncBoundary<T>({
  query,
  children,
}: {
  query: UseQueryResult<T>;
  children: (data: T) => ReactNode;
}) {
  const { t } = useTranslation();

  if (query.isPending) {
    return (
      <div className="p-8">
        <Spinner label={t("async.loading")} />
      </div>
    );
  }

  if (query.isError) {
    return <QueryError error={query.error} onRetry={() => void query.refetch()} />;
  }

  return <>{children(query.data as T)}</>;
}

/**
 * An error the person can act on, plus the id that finds it in the logs.
 *
 * The message shown is the API's own (`ApiError.detail.message`), which
 * TASK-040 guarantees is safe to display; the raw `Error.message` of anything
 * else is not, so it is replaced by a generic line rather than leaked.
 */
export function QueryError({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useTranslation();
  const apiError = error instanceof ApiError ? error : null;

  return (
    <div className="p-8">
      <Alert tone="danger" title={t("async.error.title")}>
        <p>{apiError?.detail?.message ?? t("async.error.generic")}</p>
        {apiError?.requestId ? (
          <p className="mt-2 font-mono text-xs text-ink-muted">
            {t("async.error.requestId", { requestId: apiError.requestId })}
          </p>
        ) : null}
        {onRetry ? (
          <Button variant="secondary" className="mt-4" onClick={onRetry}>
            {t("async.error.retry")}
          </Button>
        ) : null}
      </Alert>
    </div>
  );
}
