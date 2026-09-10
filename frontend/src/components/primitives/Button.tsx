import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand text-white hover:bg-brand-strong",
  secondary: "border border-border bg-surface text-ink hover:bg-canvas",
  ghost: "text-ink-soft hover:bg-canvas",
  danger: "bg-danger text-white hover:opacity-90",
};

/**
 * The tokens of ADR-002, not a new palette. A screen that needs a colour asks
 * for a variant; a screen that hard-codes a hex is how the product ended up
 * with 23 stylesheets and three names for one teal.
 */
export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      // `type` defaults to "submit" inside a form, which turns an unrelated
      // button into an accidental submit. Overridable, but never implicit.
      type="button"
      {...props}
      className={`inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${className}`}
    />
  );
}
