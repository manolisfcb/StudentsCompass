import type { ReactNode } from "react";

import { Icon } from "@/components/ui/Icon";
import type { IconName } from "@/components/ui/icons";
import { cn } from "@/lib/cn";

/**
 * `role="status"` and the visually-hidden label are not decoration: a bare
 * spinning div announces nothing, so a screen reader reports an empty page
 * while the request is in flight.
 */
export function Spinner({ label, className }: { label: string; className?: string }) {
  return (
    <span role="status" className={cn("inline-flex items-center gap-2 text-ink-soft", className)}>
      <span
        aria-hidden="true"
        className="size-4 animate-spin rounded-full border-2 border-border border-t-primary"
      />
      <span className="sr-only">{label}</span>
    </span>
  );
}

/**
 * The full-panel loading state.
 *
 * Skeleton rows rather than a centred spinner: they hold the height the
 * content will take, so the page does not jump when it arrives. `aria-hidden`
 * on the bars leaves the `Spinner`'s label as the only thing announced.
 */
export function LoadingState({ label, rows = 3, className }: { label: string; rows?: number; className?: string }) {
  return (
    <div className={cn("rounded-lg border border-border bg-surface p-6", className)}>
      <Spinner label={label} />
      <div aria-hidden="true" className="mt-4 space-y-3">
        {Array.from({ length: rows }, (_, index) => (
          <div key={index} className="flex gap-3">
            <div className="h-4 w-full animate-pulse rounded-sm bg-surface-hover" />
            <div className="h-4 w-16 shrink-0 animate-pulse rounded-sm bg-surface-hover" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * "No rows" is a legitimate answer and must not look like a broken screen.
 * Having one component for it is what stops eight verticals inventing eight
 * ways to render nothing.
 */
export function EmptyState({
  title,
  description,
  icon,
  action,
  className,
}: {
  title: string;
  description?: string;
  icon?: IconName;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center rounded-lg border border-dashed border-border bg-surface-subtle px-6 py-12 text-center",
        className,
      )}
    >
      {icon ? (
        <div
          aria-hidden="true"
          className="mb-3 flex size-10 items-center justify-center rounded-full bg-surface text-ink-muted"
        >
          <Icon name={icon} size={20} />
        </div>
      ) : null}
      <p className="text-card-title text-ink">{title}</p>
      {description ? <p className="mt-1 max-w-sm text-body-sm text-ink-soft">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
