import type { ReactNode } from "react";

import { EmptyState } from "@/components/patterns/EmptyState";

export interface Column<Row> {
  /** Stable identity, so a reordered column list does not remount every cell. */
  key: string;
  header: string;
  cell: (row: Row) => ReactNode;
  /** Right-align numbers; text stays left. */
  numeric?: boolean;
}

/**
 * A table, not a grid framework.
 *
 * Two decisions it carries for every vertical. Cells return React nodes rather
 * than strings, so user-supplied text is rendered as text by React's own
 * escaping — the lesson of F-03, where a CV name was interpolated into HTML.
 * And an empty result renders `EmptyState` instead of a header with nothing
 * under it, which reads as a failed load.
 */
export function DataTable<Row>({
  rows,
  columns,
  rowKey,
  empty,
  caption,
}: {
  rows: readonly Row[];
  columns: readonly Column<Row>[];
  rowKey: (row: Row) => string;
  empty: { title: string; description?: string };
  caption: string;
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
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-border text-left text-ink-soft">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={`px-4 py-3 font-medium ${column.numeric ? "text-right" : ""}`}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} className="border-b border-border last:border-0">
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={`px-4 py-3 text-ink ${column.numeric ? "text-right tabular-nums" : ""}`}
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
