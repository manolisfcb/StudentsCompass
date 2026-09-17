import type { ReactNode } from "react";

import { EmptyState } from "@/components/ui/States";
import { cn } from "@/lib/cn";

export interface Column<Row> {
  /** Stable identity, so a reordered column list does not remount every cell. */
  key: string;
  header: string;
  cell: (row: Row) => ReactNode;
  /** Right-align numbers; text stays left. */
  numeric?: boolean;
  /**
   * Hides the column below `md`. A table with eight columns on a phone is
   * unreadable however it scrolls, so secondary columns drop out instead.
   */
  hideOnMobile?: boolean;
}

/**
 * A table, not a grid framework.
 *
 * Two decisions it carries for every vertical. Cells return React nodes rather
 * than strings, so user-supplied text is rendered as text by React's own
 * escaping — the lesson of F-03, where a CV name was interpolated into HTML.
 * And an empty result renders `EmptyState` instead of a header with nothing
 * under it, which reads as a failed load.
 *
 * The admin variant the ported version carried is gone: the console is a dark
 * token scope now, so the same markup renders correctly in both themes.
 */
export function DataTable<Row>({
  rows,
  columns,
  rowKey,
  empty,
  caption,
  className,
}: {
  rows: readonly Row[];
  columns: readonly Column<Row>[];
  rowKey: (row: Row) => string;
  empty: { title: string; description?: string };
  caption: string;
  className?: string;
}) {
  if (rows.length === 0) {
    return empty.description === undefined ? (
      <EmptyState title={empty.title} />
    ) : (
      <EmptyState title={empty.title} description={empty.description} />
    );
  }

  return (
    // Tables are the one element allowed to be wider than the page; the
    // scroller keeps the body itself from scrolling sideways on a phone.
    <div className={cn("overflow-x-auto rounded-lg border border-border bg-surface", className)}>
      <table className="w-full border-collapse text-body-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          {/* A sticky, tinted header row is what makes a long table readable
           * while it scrolls — the ported tables lost their headings at row 20. */}
          <tr className="border-b border-border bg-surface-subtle text-left">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={cn(
                  "px-4 py-2.5 text-overline text-ink-muted uppercase",
                  column.numeric && "text-right",
                  column.hideOnMobile && "hidden md:table-cell",
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              className="border-b border-border-subtle transition-colors last:border-0 hover:bg-surface-subtle"
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={cn(
                    "px-4 py-3 text-ink",
                    // Tabular figures stop digits from jittering column to
                    // column, which is most of why a numbers table looks messy.
                    column.numeric && "text-right tabular-nums",
                    column.hideOnMobile && "hidden md:table-cell",
                  )}
                >
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
