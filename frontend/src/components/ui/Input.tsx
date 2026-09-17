import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

/**
 * The shared shape of every text-entry control: same height as a `md` Button,
 * same radius, same border, same focus treatment.
 *
 * The ported sheets styled inputs separately on the profile, company, admin
 * and auth screens — four radii and three borders for one control. Anything
 * that takes typing now reads from this one string.
 */
const CONTROL = [
  "w-full rounded-md border border-border-strong bg-surface px-3 text-body-sm text-ink",
  "transition-colors duration-150",
  "placeholder:text-ink-muted",
  // The ring is drawn with border + ring rather than the global outline so the
  // focused field reads as active, not just as focused.
  "focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20",
  "disabled:cursor-not-allowed disabled:bg-surface-subtle disabled:text-ink-muted",
  // `aria-invalid` drives the error look, so a field cannot be announced as
  // invalid to a screen reader while still looking fine to everyone else.
  "aria-[invalid=true]:border-danger aria-[invalid=true]:ring-danger/20",
].join(" ");

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cn(CONTROL, "h-10", className)} />;
}

export function Textarea({ className, rows = 4, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea rows={rows} {...props} className={cn(CONTROL, "resize-y py-2 leading-relaxed", className)} />;
}

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select {...props} className={cn(CONTROL, "h-10 cursor-pointer pr-8", className)}>
      {children}
    </select>
  );
}

/**
 * A checkbox or radio sized to the type next to it. Browsers render these at a
 * fixed 13px that no longer matches a 15px body, and `accent-color` is the one
 * way to tint the native control without rebuilding it — which would cost the
 * keyboard and screen-reader behaviour it already has.
 */
export function Checkbox({ className, type = "checkbox", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      type={type}
      {...props}
      className={cn(
        "size-4 shrink-0 cursor-pointer accent-primary",
        type === "checkbox" && "rounded-xs",
        "disabled:cursor-not-allowed disabled:opacity-60",
        className,
      )}
    />
  );
}
