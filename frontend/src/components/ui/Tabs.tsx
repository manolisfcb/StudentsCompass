import { cn } from "@/lib/cn";

export interface TabItem {
  value: string;
  label: string;
  /** Rendered as a count pill after the label. */
  count?: number;
}

/**
 * The filter row the resources, roadmaps, jobs and applications screens each
 * built their own version of (`.filter-btn`, `.filter-chip`, `.tag-filter-chip`,
 * `.course-toolbar-pill`).
 *
 * It is a real tablist: arrow keys move between tabs, `aria-selected` says
 * which is active, and `role="tab"` tells a screen reader this is a filter and
 * not five unrelated buttons. The ported versions were `<button>`s in a `<div>`
 * with a colour change, which announced nothing.
 */
export function Tabs({
  items,
  value,
  onChange,
  label,
  className,
}: {
  items: readonly TabItem[];
  value: string;
  onChange: (value: string) => void;
  /** Names the group for assistive tech — "Filter by category". */
  label: string;
  className?: string;
}) {
  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const delta = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (delta === 0) return;
    event.preventDefault();
    const index = items.findIndex((item) => item.value === value);
    // Wraps, which is what a tablist is expected to do.
    const next = items[(index + delta + items.length) % items.length];
    if (next) onChange(next.value);
  }

  return (
    <div
      role="tablist"
      aria-label={label}
      onKeyDown={onKeyDown}
      className={cn(
        // Scrolls rather than wraps on a phone: a filter row that becomes three
        // stacked lines pushes the content it filters off the screen.
        "flex gap-1 overflow-x-auto rounded-lg bg-surface-subtle p-1",
        className,
      )}
    >
      {items.map((item) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={active}
            // Only the active tab is in the tab order; the arrow keys reach
            // the rest. That is the roving-tabindex pattern a tablist wants.
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(item.value)}
            className={cn(
              "inline-flex h-8 shrink-0 items-center gap-1.5 rounded-md px-3 text-body-sm font-medium transition-colors",
              active
                ? "bg-surface text-ink shadow-xs"
                : "text-ink-soft hover:bg-surface hover:text-ink",
            )}
          >
            {item.label}
            {item.count === undefined ? null : (
              <span
                className={cn(
                  "rounded-full px-1.5 text-overline tabular-nums",
                  active ? "bg-primary-subtle text-primary" : "bg-surface-hover text-ink-muted",
                )}
              >
                {item.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
