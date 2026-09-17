import { useTranslation } from "react-i18next";

import { Badge, Button, Icon, Modal } from "@/components/ui";

/**
 * The citation dialog the three stat cards on `/about` open.
 *
 * This used to hand-roll everything a dialog needs: a focus trap that walked
 * `querySelectorAll('button, [href], …')` on every Tab, an Escape listener on
 * `document`, a `body.style.overflow` lock, and a ref to restore focus on
 * unmount — about forty lines that the native `<dialog>` behind the design
 * system's `Modal` provides correctly and for free.
 *
 * The citation text stays plain paragraphs rather than `dangerouslySetInnerHTML`.
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

  return (
    <Modal
      open
      onClose={onClose}
      title={title}
      footer={
        <Button variant="outline" onClick={onClose}>
          {t("about.stats.modal.dismiss")}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <Badge tone="brand" size="md" className="self-start">
          {t("about.stats.modal.badge")}
        </Badge>

        <div className="flex flex-col gap-2 text-body-sm text-ink-soft">
          {paragraphs.map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
        </div>

        <div className="flex flex-col gap-1.5">
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-body-sm font-medium text-primary underline underline-offset-2 hover:text-primary-hover"
          >
            {t("about.stats.modal.viewSource")}
            <Icon name="external" size={14} className="no-underline" />
          </a>
          {secondaryUrl ? (
            <a
              href={secondaryUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-body-sm font-medium text-primary underline underline-offset-2 hover:text-primary-hover"
            >
              {t("about.stats.modal.viewAdditionalSource")}
              <Icon name="external" size={14} className="no-underline" />
            </a>
          ) : null}
        </div>
      </div>
    </Modal>
  );
}
