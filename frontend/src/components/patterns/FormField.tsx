import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from "react";

/**
 * A labelled control in the shape the ported sheets style: a wrapper carrying
 * the field class, a `<label>`, then the control as its sibling.
 *
 * `className` is the field class of whichever screen is rendering —
 * `profile-field` on the profile page, `form-field` on the company screens,
 * `admin-form-group` in the admin console. They differ in spacing and radius,
 * not in structure, which is why one component serves all three.
 */
export function FormField({
  label,
  className = "form-field",
  hint,
  children,
}: {
  label: string;
  className?: string;
  hint?: string;
  children: ReactNode;
}) {
  // The label and the control are siblings, so they are tied by id rather than
  // by nesting; generating it here keeps every call site from inventing one.
  const generatedId = useId();
  const child = isValidElement(children) ? (children as ReactElement<{ id?: string }>) : null;
  const controlId = child?.props.id ?? generatedId;
  const control = child ? cloneElement(child, { id: controlId }) : children;

  return (
    <div className={className}>
      <label htmlFor={controlId}>{label}</label>
      {control}
      {hint ? <span className="profile-field-hint">{hint}</span> : null}
    </div>
  );
}
