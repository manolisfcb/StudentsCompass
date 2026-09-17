import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

export type ButtonVariant = "primary" | "secondary" | "outline" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

/**
 * The audit found fifty button classes across the ported sheets — three of
 * them "the primary button", with radii of 10px, 16px and 8px and three
 * different paddings. These five variants replace all of them.
 *
 * Colours are token references, never hexes, which is what makes a rebrand a
 * one-file change.
 */
const VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-primary text-primary-fg shadow-xs hover:bg-primary-hover active:bg-primary-active",
  secondary: "bg-primary-subtle text-primary hover:bg-primary-muted",
  outline: "border border-border-strong bg-surface text-ink shadow-xs hover:bg-surface-hover",
  ghost: "text-ink-soft hover:bg-surface-hover hover:text-ink",
  danger: "bg-danger text-white shadow-xs hover:bg-danger-hover",
};

/**
 * Heights are fixed rather than derived from padding so a button always lines
 * up with the input next to it — the misalignment the audit found on every
 * filter bar came from padding-sized controls wrapping different text.
 */
const SIZES: Record<ButtonSize, string> = {
  sm: "h-8 gap-1.5 px-3 text-body-sm",
  md: "h-10 gap-2 px-4 text-body-sm",
  lg: "h-12 gap-2 px-6 text-body",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Renders a leading icon at the size's optical weight. */
  icon?: ReactNode;
  /** Stretches to the container, for form submits and mobile actions. */
  block?: boolean;
  /**
   * Swaps the label for a spinner and disables the control. The button keeps
   * its width while busy so the layout does not jump on submit.
   */
  loading?: boolean;
}

export function Button({
  variant = "primary",
  size = "md",
  icon,
  block = false,
  loading = false,
  disabled,
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      // `type` defaults to "submit" inside a form, which turns an unrelated
      // button into an accidental submit. Overridable, but never implicit.
      type="button"
      {...props}
      disabled={disabled ?? loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-md font-medium whitespace-nowrap",
        "transition-colors duration-150",
        VARIANTS[variant],
        SIZES[size],
        // Disabled drops the variant's colour entirely rather than fading it.
        // A teal fill at 60% opacity still reads as a button you can press —
        // it just looks like a slightly paler button. A flat neutral does not.
        // These come after the variant so the `disabled:` utilities win.
        "disabled:pointer-events-none disabled:border-border disabled:bg-surface-hover",
        "disabled:text-ink-muted disabled:shadow-none",
        block && "w-full",
        className,
      )}
    >
      {loading ? (
        <span
          aria-hidden="true"
          className="size-4 animate-spin rounded-full border-2 border-current/30 border-t-current"
        />
      ) : (
        icon
      )}
      {children}
    </button>
  );
}
