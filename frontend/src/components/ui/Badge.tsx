import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export type BadgeTone = "neutral" | "brand" | "success" | "warning" | "danger" | "info";
export type BadgeSize = "sm" | "md";

/**
 * Sixty-one badge, pill, chip and tag classes collapse to this.
 *
 * Tones are tints rather than fills: a row of saturated pills competes with
 * the content it is labelling, which is what made the resource cards read as
 * a wall of colour. The border carries the meaning and the text does the
 * reading.
 */
const TONES: Record<BadgeTone, string> = {
  neutral: "border-border bg-surface-subtle text-ink-soft",
  brand: "border-primary-muted bg-primary-subtle text-primary",
  success: "border-success-border bg-success-subtle text-success",
  warning: "border-warning-border bg-warning-subtle text-warning",
  danger: "border-danger-border bg-danger-subtle text-danger",
  info: "border-info-border bg-info-subtle text-info",
};

const SIZES: Record<BadgeSize, string> = {
  sm: "h-5 px-1.5 text-overline",
  md: "h-6 px-2 text-caption",
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  size?: BadgeSize;
}

export function Badge({ tone = "neutral", size = "sm", className, ...props }: BadgeProps) {
  return (
    <span
      {...props}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border font-medium whitespace-nowrap",
        TONES[tone],
        SIZES[size],
        className,
      )}
    />
  );
}
