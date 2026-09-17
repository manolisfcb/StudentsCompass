import type { ChangeEvent, RefObject } from "react";

import { Button } from "@/components/ui";

/**
 * The upload affordance shared by the resume list and the resume audit.
 *
 * Both rendered `.resume-upload-card > .resume-upload-picker` with their own
 * copy — the same control twice, which is how the two drifted apart in the
 * first place. The native input stays in the DOM and `sr-only` rather than
 * `display: none`, so the label still names it for a screen reader and the
 * file dialog can still be opened from the keyboard.
 */
export function FilePicker({
  title,
  hint,
  buttonLabel,
  accept,
  inputRef,
  busy,
  onChange,
}: {
  title: string;
  hint: string;
  buttonLabel: string;
  accept: string;
  inputRef: RefObject<HTMLInputElement | null>;
  busy: boolean;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <label className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-dashed border-border bg-surface-subtle p-4">
      <span className="min-w-0">
        <span className="block text-card-title text-ink">{title}</span>
        <span className="block text-caption text-ink-muted">{hint}</span>
      </span>

      <input ref={inputRef} type="file" accept={accept} className="sr-only" onChange={onChange} disabled={busy} />

      <Button variant="outline" size="sm" loading={busy} onClick={() => inputRef.current?.click()}>
        {buttonLabel}
      </Button>
    </label>
  );
}
