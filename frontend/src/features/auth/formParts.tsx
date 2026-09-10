import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { ActorKind } from "@/features/auth/api";

/** Shared building blocks for the login and register cards (TASK-046). */

export const INPUT_CLASS =
  "w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-muted focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand";

export function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor?: string;
  children: ReactNode;
}) {
  return (
    <label className="block space-y-1" htmlFor={htmlFor}>
      <span className="text-sm font-medium text-ink">{label}</span>
      {children}
    </label>
  );
}

export function AsidePoint({ icon, title, body }: { icon: string; title: string; body: string }) {
  return (
    <div className="flex gap-3">
      <span aria-hidden="true" className="text-xl">
        {icon}
      </span>
      <div>
        <strong className="block text-sm text-ink">{title}</strong>
        <span className="text-sm text-ink-soft">{body}</span>
      </div>
    </div>
  );
}

export function AccountTypeToggle({
  value,
  onChange,
}: {
  value: ActorKind;
  onChange: (kind: ActorKind) => void;
}) {
  const { t } = useTranslation();
  const options: { value: ActorKind; label: string }[] = [
    { value: "student", label: t("auth.accountType.student") },
    { value: "company", label: t("auth.accountType.company") },
  ];

  return (
    <div>
      <span className="mb-1 block text-sm font-medium text-ink">{t("auth.accountType.label")}</span>
      <div
        role="radiogroup"
        aria-label={t("auth.accountType.label")}
        className="inline-flex rounded-md border border-border p-1"
      >
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={value === option.value}
            onClick={() => onChange(option.value)}
            className={`rounded px-4 py-1.5 text-sm font-medium transition-colors ${
              value === option.value ? "bg-brand text-white" : "text-ink-soft hover:bg-canvas"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}
