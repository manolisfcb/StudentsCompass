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
      className="ref-modal-backdrop active"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="reference-modal-title" className="ref-modal">
        <button
          ref={closeButtonRef}
          type="button"
          onClick={onClose}
          aria-label={t("about.stats.modal.close")}
          className="ref-modal__close"
        >
          &times;
        </button>
        <div className="ref-modal__badge">{t("about.stats.modal.badge")}</div>
        <h3 id="reference-modal-title" className="ref-modal__title">
          {title}
        </h3>
        <div className="ref-modal__body">
          {paragraphs.map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
        </div>
        <div className="ref-modal__footer">
          <a href={url} target="_blank" rel="noopener noreferrer" className="ref-modal__link">
            {t("about.stats.modal.viewSource")}
          </a>
          {secondaryUrl ? (
            <a href={secondaryUrl} target="_blank" rel="noopener noreferrer" className="ref-modal__link">
              {t("about.stats.modal.viewAdditionalSource")}
            </a>
          ) : null}
          <button type="button" onClick={onClose} className="ref-modal__btn">
            {t("about.stats.modal.dismiss")}
          </button>
        </div>
      </div>
    </div>
  );
}
