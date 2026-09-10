import type { ReactNode } from "react";

/** The input styling every form field in the app shares. */
export const INPUT_CLASS =
  "w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-muted focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand disabled:bg-canvas disabled:text-ink-muted";

export function FormField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium text-ink">{label}</span>
      {children}
    </label>
  );
}
