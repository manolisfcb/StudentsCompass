import type { ReactNode } from "react";

type Tone = "danger" | "warning" | "info" | "success";

const TONES: Record<Tone, string> = {
  danger: "border-danger/40 bg-danger/10 text-ink",
  warning: "border-warning/40 bg-warning/10 text-ink",
  info: "border-info/40 bg-info/10 text-ink",
  success: "border-success/40 bg-success/10 text-ink",
};

export function Alert({
  tone = "info",
  title,
  children,
}: {
  tone?: Tone;
  title?: string;
  children: ReactNode;
}) {
  return (
    <div
      // "alert" interrupts; a success note should not. Only the two tones that
      // mean "something went wrong" get the assertive role.
      role={tone === "danger" || tone === "warning" ? "alert" : "status"}
      className={`rounded-md border p-4 text-sm ${TONES[tone]}`}
    >
      {title ? <p className="font-semibold">{title}</p> : null}
      <div className={title ? "mt-1 text-ink-soft" : "text-ink-soft"}>{children}</div>
    </div>
  );
}
