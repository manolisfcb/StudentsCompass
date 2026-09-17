import { Icon } from "@/components/ui/Icon";
import { cn } from "@/lib/cn";

/**
 * A decorative direction marker for "back" and "continue" links.
 *
 * These used to be baked into the translation strings — `"← Back to home"`,
 * `"Start Hiring →"` — which meant a translator had to remember to carry the
 * glyph, and a right-to-left locale would have shipped an arrow pointing the
 * wrong way. As markup it flips with `dir="rtl"` and stays out of the
 * translator's hands.
 *
 * `aria-hidden` because the direction adds nothing to a link that already
 * says "Back to home"; announcing "left arrow" before it is noise.
 */
export function Arrow({ direction, className }: { direction: "back" | "forward"; className?: string }) {
  return (
    <Icon
      name={direction === "back" ? "arrow-left" : "arrow-right"}
      size={16}
      className={cn("inline-block align-text-bottom rtl:rotate-180", className)}
    />
  );
}
