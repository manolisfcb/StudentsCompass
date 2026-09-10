/**
 * `role="status"` and the visually-hidden label are not decoration: a bare
 * spinning div announces nothing, so a screen reader reports an empty page
 * while the request is in flight.
 */
export function Spinner({ label }: { label: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-ink-soft">
      <span
        aria-hidden="true"
        className="size-4 animate-spin rounded-full border-2 border-border border-t-brand"
      />
      <span className="sr-only">{label}</span>
    </span>
  );
}
