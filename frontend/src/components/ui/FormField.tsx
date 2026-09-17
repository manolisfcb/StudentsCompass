import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from "react";

import { cn } from "@/lib/cn";

interface ControlProps {
  id?: string;
  "aria-describedby"?: string;
  "aria-invalid"?: boolean;
  required?: boolean;
}

/**
 * A labelled control: label, the control, then its hint or error.
 *
 * The wiring is the point. The label is tied to the control by id, the hint
 * and the error are tied to it by `aria-describedby`, and an error also sets
 * `aria-invalid` — so the red border and the screen-reader announcement can
 * never disagree. Doing that by hand at every call site is how forms end up
 * with labels that click through to nothing.
 */
export function FormField({
  label,
  hint,
  error,
  required = false,
  className,
  children,
}: {
  label: string;
  hint?: string;
  /** Present means invalid: it styles the control and is announced. */
  error?: string;
  required?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const generatedId = useId();
  const child = isValidElement(children) ? (children as ReactElement<ControlProps>) : null;
  const controlId = child?.props.id ?? generatedId;
  const hintId = `${controlId}-hint`;
  const errorId = `${controlId}-error`;

  // An error replaces the hint as the description rather than joining it —
  // hearing the formatting rule and the failure back to back is noise at the
  // moment you most need the failure.
  const describedBy = error ? errorId : hint ? hintId : undefined;

  // Built key by key rather than as a literal: under `exactOptionalPropertyTypes`
  // an explicit `undefined` is not the same as an absent prop, and passing one
  // would overwrite whatever the child already set.
  const injected: ControlProps = { id: controlId };
  if (describedBy) injected["aria-describedby"] = describedBy;
  if (error) injected["aria-invalid"] = true;
  if (required || child?.props.required) injected.required = true;

  const control = child ? cloneElement(child, injected) : children;

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {/* The asterisk is a sibling of the <label>, not inside it. Nested, it
        * becomes part of the label's text, so the field's accessible name turns
        * into "Title *" — which is what a screen reader then announces, and
        * what a test looking for "Title" stops finding. The `required`
        * attribute on the control is what actually conveys the requirement. */}
      <div className="flex items-center gap-0.5">
        <label htmlFor={controlId} className="text-label text-ink">
          {label}
        </label>
        {required ? (
          <span className="text-danger" aria-hidden="true">
            *
          </span>
        ) : null}
      </div>

      {control}

      {error ? (
        <p id={errorId} className="text-caption text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-caption text-ink-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
