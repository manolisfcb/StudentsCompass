import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { ActorKind } from "@/features/auth/api";

/**
 * Shared building blocks for the login and register cards (TASK-046), carrying
 * the classes `style.css` styles the auth screens by: `.form-group` for a
 * labelled field, `.auth-aside-point` for the panel's bullets, and
 * `.account-type-toggle > .toggle-option` for the student/company switch.
 *
 * The toggle was two hidden radios and two `<label for>`s in the template,
 * which is how a stylesheet with no JS reacts to a choice. Here it is a real
 * radio group: same classes, same `.active` presentation, but the state lives
 * in React like every other control on the page.
 */

export function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  /** Pass one when the control already has an id; otherwise one is generated. */
  htmlFor?: string;
  children: ReactNode;
}) {
  // `.form-group` puts the label and the control side by side rather than
  // nesting one in the other, which is what the sheet styles — so the pair has
  // to be tied together by id. Generating it here keeps every call site from
  // inventing one, and keeps the control reachable by its label.
  const generatedId = useId();
  const control = isValidElement(children)
    ? (() => {
        const element = children as ReactElement<{ id?: string }>;
        return cloneElement(element, { id: element.props.id ?? htmlFor ?? generatedId });
      })()
    : children;
  const controlId =
    isValidElement(children) && (children as ReactElement<{ id?: string }>).props.id
      ? (children as ReactElement<{ id?: string }>).props.id
      : (htmlFor ?? generatedId);

  return (
    <div className="form-group">
      <label htmlFor={controlId}>{label}</label>
      {control}
    </div>
  );
}

export function AsidePoint({ icon, title, body }: { icon: string; title: string; body: string }) {
  return (
    <div className="auth-aside-point">
      <div className="auth-aside-icon" aria-hidden="true">
        {icon}
      </div>
      <div>
        <strong>{title}</strong>
        <span>{body}</span>
      </div>
    </div>
  );
}

function StudentIcon() {
  return (
    <svg className="toggle-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function CompanyIcon() {
  return (
    <svg className="toggle-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
      <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
      <path d="M16 4h2a2 2 0 0 1 2 2v2H2V6a2 2 0 0 1 2-2h2m12 10v4M2 17v4" />
    </svg>
  );
}

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
    <div className="form-group">
      <span className="auth-section-label">{t("auth.accountType.label")}</span>
      <div className="account-type-toggle">
        {/* Radios first, then labels: the selected presentation is
            `#type-student:checked ~ label[for="type-student"]` in the shipped
            sheet, and `~` only reaches later siblings. They are `sr-only`
            rather than the template's `hidden`, which is the one change — a
            `hidden` radio cannot be reached with the keyboard at all. */}
        {options.map((option) => (
          <input
            key={option.value}
            type="radio"
            className="sr-only"
            name={name}
            id={`${idPrefix}-${option.value}`}
            value={option.value}
            checked={value === option.value}
            onChange={() => onChange(option.value)}
          />
        ))}
        {options.map((option) => (
          <label key={option.value} htmlFor={`${idPrefix}-${option.value}`} className="toggle-option">
            {option.icon}
            <span className="toggle-text">{option.label}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
