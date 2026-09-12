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

export function AsidePoint({
  icon,
  title,
  body,
  tone = "light",
}: {
  icon: string;
  title: string;
  body: string;
  /** "dark" matches `.auth-aside-point`: a translucent box on the gradient panel. */
  tone?: "light" | "dark";
}) {
  const isDark = tone === "dark";
  return (
    <div
      className={
        isDark
          ? "flex items-start gap-3 rounded-2xl border border-white/10 bg-white/10 p-4"
          : "flex gap-3"
      }
    >
      <span
        aria-hidden="true"
        className={
          isDark
            ? "flex size-10 shrink-0 items-center justify-center rounded-2xl bg-white/15 text-lg"
            : "text-xl"
        }
      >
        {icon}
      </span>
      <div>
        <strong className={`block text-sm ${isDark ? "text-white" : "text-ink"}`}>{title}</strong>
        <span className={`text-sm ${isDark ? "text-white/80" : "text-ink-soft"}`}>{body}</span>
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
      <div role="radiogroup" aria-label={t("auth.accountType.label")} className="grid grid-cols-2 gap-3">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={value === option.value}
            onClick={() => onChange(option.value)}
            className={`rounded-2xl border px-4 py-2.5 text-sm font-bold transition-colors ${
              value === option.value
                ? "border-transparent bg-gradient-to-r from-brand to-brand-soft text-white shadow-[0_10px_20px_rgba(15,118,110,0.28)]"
                : "border-border bg-canvas text-ink-soft hover:border-brand/30 hover:bg-white"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}
