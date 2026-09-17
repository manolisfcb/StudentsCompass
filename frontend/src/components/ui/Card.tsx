import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

/**
 * The container the audit found seventy-four names for — `.job-card`,
 * `.resource-card`, `.stat-card`, `.post-card`, `.roadmap-card` and the rest,
 * visually the same object with different padding and radius.
 *
 * They are one component now. A "StudentCard" and a "CourseCard" differ in
 * what they contain, not in what they are, so the family is expressed by
 * composing this rather than by writing another surface.
 */
export type CardPadding = "none" | "sm" | "md" | "lg";

const PADDING: Record<CardPadding, string> = {
  none: "",
  sm: "p-3",
  md: "p-4",
  lg: "p-6",
};

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  padding?: CardPadding;
  /**
   * Lifts on hover. Only for a card that is itself a link or a button —
   * a card that rises under the cursor and then does nothing is a bug report.
   */
  interactive?: boolean;
  /** Draws the border in the brand colour, for a selected or featured row. */
  selected?: boolean;
}

export function Card({ padding = "md", interactive = false, selected = false, className, ...props }: CardProps) {
  return (
    <div
      {...props}
      className={cn(
        "rounded-lg border border-border bg-surface",
        // Resting elevation is deliberately almost nothing. The ported sheets
        // put 38px-blur shadows on static cards, which is what gave the
        // product its foggy look; depth here comes from the border.
        "shadow-xs",
        interactive &&
          "cursor-pointer transition-[box-shadow,border-color,transform] duration-150 hover:-translate-y-0.5 hover:border-border-strong hover:shadow-md",
        selected && "border-primary ring-1 ring-primary",
        PADDING[padding],
        className,
      )}
    />
  );
}

/**
 * A card's title row. `action` is the slot for the control that belongs to the
 * card — an overflow menu, a "view all" link — kept on the baseline of the
 * title rather than floated, which is what kept the ported headers misaligned.
 */
export function CardHeader({
  title,
  description,
  action,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    // Wraps rather than squeezes: on a phone a title and a "view all" link
    // side by side left the title breaking across three lines. Below `sm` the
    // action drops onto its own row instead.
    <div className={cn("flex flex-wrap items-start justify-between gap-x-3 gap-y-1.5", className)}>
      <div className="min-w-0 flex-1">
        <h3 className="text-card-title text-ink">{title}</h3>
        {description ? <p className="mt-0.5 text-caption text-ink-soft">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

/** Divider-separated footer for a card's actions. */
export function CardFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div {...props} className={cn("mt-4 flex items-center gap-2 border-t border-border pt-4", className)} />;
}
