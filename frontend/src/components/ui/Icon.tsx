import type { SVGProps } from "react";

import { ICON_ART } from "@/components/ui/icons.generated";
import { ROTATED, type IconName, type IconVariant } from "@/components/ui/icons";
import { cn } from "@/lib/cn";

/**
 * What every path of a variant shares, set once on the `<svg>` so the
 * generated artwork carries outlines and nothing else. These are presentation
 * attributes, so each path inherits them unless it says otherwise.
 */
const VARIANTS: Record<IconVariant, SVGProps<SVGSVGElement>> = {
  Linear: {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5,
    strokeLinecap: "round",
    strokeLinejoin: "round",
  },
  Bold: { fill: "currentColor" },
};

export function Icon({
  name,
  size = 20,
  variant = "Linear",
  className,
  label,
}: {
  name: IconName;
  size?: number;
  /** `Bold` fills the shape — for a glyph sitting alone on a tinted chip. */
  variant?: IconVariant;
  className?: string;
  /**
   * Only for an icon that is the *sole* content of a control. Everywhere else
   * a label already sits beside it, and a second announcement is noise — so
   * the default is `aria-hidden`.
   */
  label?: string;
}) {
  const decorative = label === undefined;

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      {...VARIANTS[variant]}
      className={cn("shrink-0", ROTATED[name], className)}
      aria-hidden={decorative || undefined}
      role={decorative ? undefined : "img"}
      aria-label={label}
      focusable="false"
    >
      {/* The index is a safe key here and nowhere else: this list is
        * generated, fixed at build time, and never reordered or filtered. */}
      {ICON_ART[name][variant].map((path, index) => (
        <path key={index} {...path} />
      ))}
    </svg>
  );
}
