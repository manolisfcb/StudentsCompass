import { useEffect, useRef, type ReactNode } from "react";

import { cn } from "@/lib/cn";

export type ModalSize = "sm" | "md" | "lg";

const SIZES: Record<ModalSize, string> = {
  sm: "max-w-sm",
  md: "max-w-lg",
  lg: "max-w-2xl",
};

/**
 * A dialog built on `<dialog showModal()>`.
 *
 * The native element is doing real work here: it traps focus, it restores
 * focus to whatever opened it on close, it renders on the top layer so no
 * z-index on the page can cover it, it makes the rest of the document inert,
 * and it closes on Escape. Every one of those is something the hand-rolled
 * modals in the ported sheets did not do.
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  size = "md",
  footer,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  size?: ModalSize;
  footer?: ReactNode;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    // `showModal()` throws if the dialog is already open, and `close()` on an
    // already-closed dialog fires a spurious `cancel`.
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  const titleId = `${title.replace(/\W+/g, "-").toLowerCase()}-title`;

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      // Escape fires `cancel`, not `close`; without this the dialog would hide
      // itself while the caller still believed it was open.
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClose={onClose}
      // Clicking the backdrop targets the dialog itself — the panel inside
      // stops the event from ever reaching here.
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
      className={cn(
        "m-auto w-[calc(100vw-2rem)] rounded-xl border border-border bg-surface p-0 text-ink shadow-lg",
        "backdrop:bg-ink/40 backdrop:backdrop-blur-sm",
        SIZES[size],
      )}
    >
      <div onClick={(event) => event.stopPropagation()}>
        <header className="flex items-start justify-between gap-4 border-b border-border px-6 py-4">
          <div className="min-w-0">
            <h2 id={titleId} className="text-section-title text-ink">
              {title}
            </h2>
            {description ? <p className="mt-1 text-body-sm text-ink-soft">{description}</p> : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="-mr-2 -mt-1 flex size-8 shrink-0 items-center justify-center rounded-md text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink"
          >
            <span aria-hidden="true">✕</span>
          </button>
        </header>

        <div className="max-h-[70vh] overflow-y-auto px-6 py-5 text-body-sm">{children}</div>

        {footer ? (
          <footer className="flex flex-wrap justify-end gap-2 border-t border-border bg-surface-subtle px-6 py-4">
            {footer}
          </footer>
        ) : null}
      </div>
    </dialog>
  );
}
