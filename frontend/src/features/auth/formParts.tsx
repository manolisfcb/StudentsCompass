import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "@/lib/cn";
import type { ActorKind } from "@/features/auth/api";

/**
 * Shared building blocks for the login and register cards.
 *
 * The labelled field the auth screens used to need is gone: they use the
 * design system's `FormField` now, like every other form in the app. What is
 * left here is the two pieces that are genuinely specific to these two
 * screens — the marketing panel's bullets and the account-type switch.
 */

/** A selling point in the panel beside the form. */
export function AsidePoint({ icon, title, body }: { icon: string; title: string; body: string }) {
  return (
    <div className="flex gap-3">
      <span
        aria-hidden="true"
        className="flex size-9 shrink-0 items-center justify-center rounded-md bg-white/15 text-lg"
      >
        {icon}
      </span>
      <div className="min-w-0">
        <p className="text-card-title text-white">{title}</p>
        <p className="mt-0.5 text-body-sm text-white/70">{body}</p>
      </div>
    </div>
  );
}

function StudentIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
      className="size-5"
    >
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function CompanyIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
      className="size-5"
    >
      <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
      <path d="M16 4h2a2 2 0 0 1 2 2v2H2V6a2 2 0 0 1 2-2h2m12 10v4M2 17v4" />
    </svg>
  );
}

/**
 * The student/company switch.
 *
 * A real radio group in a `fieldset`, so a screen reader announces "Account
 * type, Student, 1 of 2" rather than reading two unrelated labels. The radios
 * are `sr-only` rather than `hidden` — a `hidden` radio cannot be reached with
 * the keyboard at all — and `peer-checked` draws the selected state, which is
 * what the template's `:checked ~ label` trick was doing.
 */
export function AccountTypeToggle({
  idPrefix,
  name,
  value,
  onChange,
}: {
  /** `type` on the login card, `reg-type` on the register card. */
  idPrefix: "type" | "reg-type";
  name: string;
  value: ActorKind;
  onChange: (kind: ActorKind) => void;
}) {
  const { t } = useTranslation();
  const options: { value: ActorKind; label: string; icon: ReactNode }[] = [
    { value: "student", label: t("auth.accountType.student"), icon: <StudentIcon /> },
    { value: "company", label: t("auth.accountType.company"), icon: <CompanyIcon /> },
  ];

  return (
    <fieldset className="flex flex-col gap-1.5">
      <legend className="mb-1.5 text-label text-ink">{t("auth.accountType.label")}</legend>
      <div className="grid grid-cols-2 gap-2">
        {options.map((option) => (
          <div key={option.value} className="contents">
            <input
              type="radio"
              className="peer sr-only"
              name={name}
              id={`${idPrefix}-${option.value}`}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            <label
              htmlFor={`${idPrefix}-${option.value}`}
              className={cn(
                "flex cursor-pointer items-center justify-center gap-2 rounded-md border px-3 py-2.5 text-body-sm font-medium transition-colors",
                "border-border-strong text-ink-soft hover:bg-surface-hover",
                // The ring follows the hidden radio's own focus, so tabbing to
                // the group still shows where you are.
                "peer-checked:border-primary peer-checked:bg-primary-subtle peer-checked:text-primary",
                "peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-primary",
              )}
            >
              {option.icon}
              {option.label}
            </label>
          </div>
        ))}
      </div>
    </fieldset>
  );
}
