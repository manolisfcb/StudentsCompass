import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/**
 * The KPI tile. `.stat-card` meant a student metric in `dashboard.css` and a
 * company metric in `company-dashboard.css` — two sheets, two looks, one name,
 * which is exactly why the page scopes had to exist at all.
 *
 * One component, so a number means the same thing on both dashboards.
 */
export function StatCard({
  label,
  value,
  hint,
  icon,
  trend,
  className,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  icon?: ReactNode;
  /** A period-over-period change. Direction picks the colour and the arrow. */
  trend?: { direction: "up" | "down"; label: string };
  className?: string;
}) {
  return (
    <div className={cn("rounded-lg border border-border bg-surface p-4 shadow-xs", className)}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-overline text-ink-muted uppercase">{label}</p>
        {icon ? (
          <span
            aria-hidden="true"
            className="flex size-7 items-center justify-center rounded-md bg-primary-subtle text-primary"
          >
            {icon}
          </span>
        ) : null}
      </div>

      {/* Tabular figures keep a row of tiles optically aligned even when the
       * numbers have different digit widths. */}
      <p className="mt-2 text-page-title text-ink tabular-nums">{value}</p>

      {trend ? (
        <p className={cn("mt-1 text-caption", trend.direction === "up" ? "text-success" : "text-danger")}>
          {/* The arrow carries the direction for anyone who cannot use the
           * colour to tell up from down. */}
          <span aria-hidden="true">{trend.direction === "up" ? "↑" : "↓"}</span> {trend.label}
        </p>
      ) : hint ? (
        <p className="mt-1 text-caption text-ink-muted">{hint}</p>
      ) : null}
    </div>
  );
}

/**
 * A labelled progress bar. The ported sheets drew these five different ways
 * across the dashboard, the roadmaps and the career lab.
 */
export function ProgressBar({
  value,
  label,
  showValue = true,
  className,
}: {
  /** 0–100. Clamped, because a backend that reports 104% should not overflow. */
  value: number;
  label: string;
  showValue?: boolean;
  className?: string;
}) {
  const pct = Math.max(0, Math.min(100, Math.round(value)));

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-body-sm text-ink-soft">{label}</span>
        {showValue ? <span className="text-label text-ink tabular-nums">{pct}%</span> : null}
      </div>
      <div
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
        className="h-1.5 overflow-hidden rounded-full bg-surface-hover"
      >
        <div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
