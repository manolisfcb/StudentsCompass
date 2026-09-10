import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

/**
 * The citation modal from `about.js`: three stat cards on `/about` open a
 * dialog naming the source. Reimplemented with the same keyboard contract
 * (Escape closes, Tab loops inside, focus returns to the card that opened it)
 * rather than `dangerouslySetInnerHTML` for the body — the citation text is
 * plain paragraphs, so there is nothing markup needs to carry.
 */
export function ReferenceModal({
  title,
  paragraphs,
  url,
  secondaryUrl,
  onClose,
}: {
  title: string;
  paragraphs: readonly string[];
  url: string;
  secondaryUrl?: string | undefined;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<Element | null>(null);

  useEffect(() => {
    previousFocus.current = document.activeElement;
    closeButtonRef.current?.focus();
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
      if (previousFocus.current instanceof HTMLElement) previousFocus.current.focus();
    };
  }, []);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab") return;

      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button, [href], [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable || focusable.length === 0) return;
      const first = focusable[0]!;
      const last = focusable[focusable.length - 1]!;

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 p-4"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="reference-modal-title"
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-surface p-6 shadow-lg"
      >
        <button
          ref={closeButtonRef}
          type="button"
          onClick={onClose}
          aria-label={t("about.stats.modal.close")}
          className="float-right text-xl text-ink-muted hover:text-ink"
        >
          &times;
        </button>
        <p className="text-xs font-semibold uppercase tracking-wide text-brand">
          {t("about.stats.modal.badge")}
        </p>
        <h3 id="reference-modal-title" className="mt-2 text-lg font-semibold text-ink">
          {title}
        </h3>
        <div className="mt-3 space-y-2 text-sm text-ink-soft">
          {paragraphs.map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-4 border-t border-border pt-4 text-sm">
          <a href={url} target="_blank" rel="noopener noreferrer" className="font-medium text-brand hover:underline">
            {t("about.stats.modal.viewSource")}
          </a>
          {secondaryUrl ? (
            <a
              href={secondaryUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-brand hover:underline"
            >
              {t("about.stats.modal.viewAdditionalSource")}
            </a>
          ) : null}
          <button type="button" onClick={onClose} className="ml-auto text-ink-soft hover:text-ink">
            {t("about.stats.modal.dismiss")}
          </button>
        </div>
      </div>
    </div>
  );
}
