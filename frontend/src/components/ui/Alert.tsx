import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

export type AlertTone = "info" | "success" | "warning" | "danger";

const TONES: Record<AlertTone, string> = {
  info: "border-info-border bg-info-subtle",
  success: "border-success-border bg-success-subtle",
  warning: "border-warning-border bg-warning-subtle",
  danger: "border-danger-border bg-danger-subtle",
};

const ICON_TONES: Record<AlertTone, string> = {
  info: "text-info",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
};

const GLYPHS: Record<AlertTone, string> = {
  info: "i",
  success: "✓",
  warning: "!",
  danger: "!",
};

/**
 * A banner carrying one message.
 *
 * Tone drives the announcement as well as the colour: "alert" interrupts a
 * screen reader mid-sentence, which is right for a failure and wrong for a
 * saved confirmation. Colour is never the only signal — each tone has its own
 * glyph, so the meaning survives a colour-blind reader and a greyscale print.
 */
export function Alert({
  tone = "info",
  title,
  action,
  className,
  children,
}: {
  tone?: AlertTone;
  title?: string;
  /** A retry button, typically. */
  action?: ReactNode;
  className?: string;
  children?: ReactNode;
}) {
  const assertive = tone === "danger" || tone === "warning";

  return (
    <div
      role={assertive ? "alert" : "status"}
      className={cn("flex gap-3 rounded-lg border p-4", TONES[tone], className)}
    >
      <span
        aria-hidden="true"
        className={cn(
          "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border border-current text-overline",
          ICON_TONES[tone],
        )}
      >
        {GLYPHS[tone]}
      </span>

      <div className="min-w-0 flex-1">
        {title ? <p className="text-card-title text-ink">{title}</p> : null}
        {children ? <div className={cn("text-body-sm text-ink-soft", title && "mt-1")}>{children}</div> : null}
        {action ? <div className="mt-3">{action}</div> : null}
      </div>
    </div>
  );
}
